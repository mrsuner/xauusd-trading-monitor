<?php

namespace App\Services\Delivery;

use App\Enums\AccessDecision;
use App\Enums\DeliveryStatus;
use App\Enums\TelegramResultType;
use App\Models\Channel;
use App\Models\Delivery;
use App\Models\RuntimeState;
use App\Models\Subscriber;
use App\Services\Account\AccountAccessClient;
use App\Services\Channels\ChannelService;
use App\Services\Preferences\EventMatcher;
use App\Services\Preferences\TaxonomyCatalog;
use App\Services\Telegram\TelegramApi;
use App\ValueObjects\PublicEventData;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\RateLimiter;

class DeliveryProcessor
{
    public function __construct(
        private PublicEventRepository $events,
        private TaxonomyCatalog $taxonomy,
        private EventMatcher $matcher,
        private AccountAccessClient $access,
        private ChannelService $channels,
        private ContentSelector $content,
        private TelegramMessageFormatter $formatter,
        private TelegramApi $telegram,
    ) {}

    /** Return the number of seconds before this job should be released, or null when resolved. */
    public function process(string $deliveryId): ?int
    {
        $now = CarbonImmutable::now('UTC');
        $delivery = Delivery::query()->with(['subscriber.categories', 'subscriber.tags', 'channel'])->find($deliveryId);
        if ($delivery === null || $delivery->status->terminal()) {
            return null;
        }
        if ($delivery->expires_at->lessThanOrEqualTo($now)) {
            $this->resolve($delivery, DeliveryStatus::Expired, 'freshness_expired');

            return null;
        }
        if ($delivery->not_before->isFuture()) {
            return max(1, (int) ceil($now->diffInSeconds($delivery->not_before)));
        }

        $subscriber = $delivery->subscriber;
        $channel = $delivery->channel;
        if ($subscriber === null || $channel === null
            || ! $subscriber->master_enabled || ! $channel->enabled || ! $channel->verified
            || $subscriber->revision !== $delivery->subscriber_revision
            || $channel->revision !== $delivery->channel_revision) {
            $this->resolve($delivery, DeliveryStatus::Canceled, 'configuration_changed');

            return null;
        }

        $access = $this->access->check($subscriber->account_user_id);
        if ($access === AccessDecision::Unknown) {
            return $this->wait($delivery, 60, 'account_unavailable');
        }
        if ($access !== AccessDecision::Active) {
            if ($access === AccessDecision::Missing) {
                $this->channels->revokeForMissingAccount($subscriber->id);
            }
            $this->resolve($delivery->fresh(), DeliveryStatus::Canceled, 'access_inactive');

            return null;
        }

        $event = $this->events->findVisible($delivery->public_event_id);
        if ($event === null || ! $this->stillMatches($subscriber, $event)) {
            $this->resolve($delivery, DeliveryStatus::Canceled, 'event_unavailable');

            return null;
        }
        $content = $this->content->select($event, $subscriber->content_language, $now);
        if ($content === null) {
            return $this->wait($delivery, 60, 'content_wait');
        }

        $cooldown = $this->providerCooldown($now);
        if ($cooldown > 0) {
            return $this->wait($delivery, $cooldown, 'provider_cooldown');
        }

        $target = Crypt::decryptString((string) $channel->encrypted_target);
        $rateDelay = $this->claimRateLimit($channel);
        if ($rateDelay > 0) {
            return $this->wait($delivery, $rateDelay, 'provider_rate_wait');
        }

        $attempt = DB::transaction(function () use ($deliveryId, $now): ?int {
            $current = Delivery::query()->with(['subscriber', 'channel'])->lockForUpdate()->find($deliveryId);
            if ($current === null || $current->status->terminal()
                || $current->expires_at->lessThanOrEqualTo($now)
                || ! $current->subscriber?->master_enabled || ! $current->channel?->enabled
                || ! $current->channel?->verified
                || $current->subscriber_revision !== $current->subscriber?->revision
                || $current->channel_revision !== $current->channel?->revision) {
                return null;
            }

            $current->status = DeliveryStatus::Sending;
            $current->attempt_count++;
            $current->last_attempt_at = $now;
            $current->error_code = null;
            $current->save();

            return $current->attempt_count;
        });
        if ($attempt === null) {
            return null;
        }

        $result = $this->telegram->sendMessage(
            $target,
            $this->formatter->format($event, $content, $subscriber->content_language),
        );
        $delivery = Delivery::query()->findOrFail($deliveryId);

        return match ($result->type) {
            TelegramResultType::Accepted => $this->accepted($delivery, $result->messageId),
            TelegramResultType::RateLimited => $this->rateLimited($delivery, $result->retryAfter ?? 1),
            TelegramResultType::TargetInvalid => $this->targetInvalid($delivery, $channel),
            TelegramResultType::ProviderInvalid => $this->providerInvalid($delivery),
            TelegramResultType::TransientFailure => $this->retryOrFail($delivery, $this->backoff($delivery), 'provider_transient'),
            TelegramResultType::PayloadInvalid => $this->permanentFailure($delivery, 'payload_invalid'),
        };
    }

    private function stillMatches(Subscriber $subscriber, PublicEventData $event): bool
    {
        $catalog = $this->taxonomy->keys();

        return $this->matcher->matches(
            $subscriber->match_all_categories,
            $subscriber->categories->pluck('key')->all(),
            $subscriber->tags->pluck('key')->all(),
            $subscriber->min_severity,
            $catalog['categories'],
            $catalog['tags'],
            $event->category,
            $event->tags,
            $event->severity,
        );
    }

    private function claimRateLimit(Channel $channel): int
    {
        $keys = ['telegram:bot-send', 'telegram:chat-send:'.$channel->target_fingerprint];
        foreach ($keys as $key) {
            if (RateLimiter::tooManyAttempts($key, 1)) {
                return max(1, RateLimiter::availableIn($key));
            }
        }
        foreach ($keys as $key) {
            RateLimiter::hit($key, 1);
        }

        return 0;
    }

    private function providerCooldown(CarbonImmutable $now): int
    {
        $until = RuntimeState::query()->find('telegram_provider')?->value['cooldown_until'] ?? null;
        if (! is_string($until)) {
            return 0;
        }
        $cooldown = CarbonImmutable::parse($until, 'UTC');

        return $cooldown->isFuture() ? max(1, (int) ceil($now->diffInSeconds($cooldown))) : 0;
    }

    private function wait(Delivery $delivery, int $seconds, string $reason): int
    {
        $delivery->status = DeliveryStatus::Retry;
        $delivery->not_before = now('UTC')->addSeconds($seconds)->min($delivery->expires_at);
        $delivery->error_code = $reason;
        $delivery->save();

        return max(1, $seconds);
    }

    private function accepted(Delivery $delivery, ?string $messageId): ?int
    {
        $delivery->status = DeliveryStatus::Sent;
        $delivery->sent_at = now('UTC');
        $delivery->provider_message_id = $messageId;
        $delivery->error_code = null;
        $delivery->save();
        RuntimeState::query()->updateOrCreate(
            ['key' => 'telegram_last_send'],
            ['value' => ['sent_at' => now('UTC')->toIso8601String()]],
        );

        return null;
    }

    private function rateLimited(Delivery $delivery, int $seconds): int
    {
        RuntimeState::query()->updateOrCreate(
            ['key' => 'telegram_provider'],
            ['value' => ['cooldown_until' => now('UTC')->addSeconds($seconds)->toIso8601String()]],
        );

        return $this->retryOrFail($delivery, $seconds, 'provider_429') ?? $seconds;
    }

    private function targetInvalid(Delivery $delivery, Channel $channel): ?int
    {
        $this->resolve($delivery, DeliveryStatus::Failed, 'target_invalid');
        $channel->enabled = false;
        $channel->enabled_from = null;
        $channel->last_error_code = 'target_invalid';
        $channel->revision++;
        $channel->save();
        DB::table('deliveries')->where('channel_id', $channel->id)
            ->whereIn('status', ['pending', 'retry'])
            ->update(['status' => 'canceled', 'error_code' => 'target_invalid', 'updated_at' => now('UTC')]);

        return null;
    }

    private function providerInvalid(Delivery $delivery): ?int
    {
        RuntimeState::query()->updateOrCreate(
            ['key' => 'telegram_provider'],
            ['value' => ['cooldown_until' => now('UTC')->addMinutes(5)->toIso8601String()]],
        );

        return $this->retryOrFail($delivery, 300, 'provider_invalid');
    }

    private function permanentFailure(Delivery $delivery, string $reason): ?int
    {
        $this->resolve($delivery, DeliveryStatus::Failed, $reason);

        return null;
    }

    private function retryOrFail(Delivery $delivery, int $seconds, string $reason): ?int
    {
        if ($delivery->attempt_count >= (int) config('notification.delivery.max_provider_attempts', 5)) {
            return $this->permanentFailure($delivery, $reason.'_exhausted');
        }

        return $this->wait($delivery, $seconds, $reason);
    }

    private function backoff(Delivery $delivery): int
    {
        $schedule = config('notification.delivery.http_backoff_seconds', [30, 120, 300, 600]);
        $base = (int) $schedule[min(max(0, $delivery->attempt_count - 1), count($schedule) - 1)];
        $jitterPercent = abs(crc32($delivery->id.':'.$delivery->attempt_count)) % 21;

        return $base + (int) floor($base * $jitterPercent / 100);
    }

    private function resolve(Delivery $delivery, DeliveryStatus $status, string $reason): void
    {
        $delivery->status = $status;
        $delivery->error_code = $reason;
        $delivery->save();
    }
}
