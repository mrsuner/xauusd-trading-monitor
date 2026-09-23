<?php

namespace App\Services\Digests;

use App\Enums\AccessDecision;
use App\Enums\TelegramResultType;
use App\Models\DigestBatch;
use App\Models\RuntimeState;
use App\Services\Account\AccountAccessClient;
use App\Services\Telegram\TelegramApi;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\RateLimiter;

class DigestBatchProcessor
{
    public function __construct(
        private AccountAccessClient $access,
        private DigestMessageFormatter $formatter,
        private TelegramApi $telegram,
    ) {}

    public function process(string $batchId): ?int
    {
        $batch = DigestBatch::query()->with(['subscriber.digestPreference', 'channel', 'editions'])->find($batchId);
        if ($batch === null || in_array($batch->status, ['sent', 'no_content', 'failed', 'canceled', 'expired'], true)) {
            return null;
        }
        $batch->editions->each(fn ($edition) => $edition->load([
            'translations' => fn ($query) => $query->where('language', $batch->content_language),
        ]));
        if ($batch->not_before->isFuture()) {
            return max(1, (int) ceil(now('UTC')->diffInSeconds($batch->not_before)));
        }
        $preference = $batch->subscriber?->digestPreference;
        $channel = $batch->channel;
        if ($preference === null || ! $preference->enabled || $preference->revision !== $batch->preference_revision
            || $channel === null || ! $channel->enabled || ! $channel->verified || $channel->revision !== $batch->channel_revision) {
            return $this->resolve($batch, 'canceled', 'configuration_changed');
        }

        $access = $this->access->check($batch->subscriber->account_user_id);
        if ($access === AccessDecision::Unknown) {
            return $this->wait($batch, 60, 'account_unavailable');
        }
        if ($access !== AccessDecision::Active) {
            return $this->resolve($batch, 'canceled', 'access_inactive');
        }
        if ($batch->editions->isEmpty() || $batch->editions->contains(fn ($edition): bool => $edition->status !== 'published')) {
            return $this->resolve($batch, 'canceled', 'edition_unavailable');
        }

        $cooldown = $this->cooldown();
        if ($cooldown > 0) {
            return $this->wait($batch, $cooldown, 'provider_cooldown');
        }
        foreach (['telegram:bot-send', 'telegram:chat-send:'.$channel->target_fingerprint] as $key) {
            if (RateLimiter::tooManyAttempts($key, 1)) {
                return $this->wait($batch, max(1, RateLimiter::availableIn($key)), 'provider_rate_wait');
            }
        }
        RateLimiter::hit('telegram:bot-send', 1);
        RateLimiter::hit('telegram:chat-send:'.$channel->target_fingerprint, 1);

        $batch->update(['status' => 'sending', 'attempt_count' => $batch->attempt_count + 1, 'last_attempt_at' => now('UTC')]);
        $result = $this->telegram->sendMessage(
            Crypt::decryptString((string) $channel->encrypted_target),
            $this->formatter->format($batch),
        );

        return match ($result->type) {
            TelegramResultType::Accepted => $this->accepted($batch, $result->messageId),
            TelegramResultType::RateLimited => $this->rateLimited($batch, $result->retryAfter ?? 1),
            TelegramResultType::TargetInvalid => $this->targetInvalid($batch),
            TelegramResultType::ProviderInvalid => $this->providerInvalid($batch),
            TelegramResultType::TransientFailure => $this->retryOrFail($batch, 'provider_transient'),
            TelegramResultType::PayloadInvalid => $this->resolve($batch, 'failed', 'payload_invalid'),
        };
    }

    private function accepted(DigestBatch $batch, ?string $messageId): ?int
    {
        $batch->update(['status' => 'sent', 'sent_at' => now('UTC'), 'provider_message_id' => $messageId, 'error_code' => null]);

        return null;
    }

    private function rateLimited(DigestBatch $batch, int $seconds): ?int
    {
        RuntimeState::query()->updateOrCreate(['key' => 'telegram_provider'], [
            'value' => ['cooldown_until' => now('UTC')->addSeconds($seconds)->toIso8601String()],
        ]);

        return $batch->attempt_count >= (int) config('notification.delivery.max_provider_attempts', 5)
            ? $this->resolve($batch, 'failed', 'provider_429_exhausted')
            : $this->wait($batch, $seconds, 'provider_429');
    }

    private function providerInvalid(DigestBatch $batch): ?int
    {
        RuntimeState::query()->updateOrCreate(['key' => 'telegram_provider'], [
            'value' => ['cooldown_until' => now('UTC')->addMinutes(5)->toIso8601String()],
        ]);

        return $batch->attempt_count >= (int) config('notification.delivery.max_provider_attempts', 5)
            ? $this->resolve($batch, 'failed', 'provider_invalid_exhausted')
            : $this->wait($batch, 300, 'provider_invalid');
    }

    private function targetInvalid(DigestBatch $batch): ?int
    {
        $batch->channel->update(['enabled' => false, 'enabled_from' => null, 'last_error_code' => 'target_invalid', 'revision' => $batch->channel->revision + 1]);

        return $this->resolve($batch, 'failed', 'target_invalid');
    }

    private function retryOrFail(DigestBatch $batch, string $reason): ?int
    {
        if ($batch->attempt_count >= (int) config('notification.delivery.max_provider_attempts', 5)) {
            return $this->resolve($batch, 'failed', $reason.'_exhausted');
        }
        $schedule = config('notification.delivery.http_backoff_seconds', [30, 120, 300, 600]);
        $seconds = (int) $schedule[min($batch->attempt_count - 1, count($schedule) - 1)];

        return $this->wait($batch, $seconds, $reason);
    }

    private function wait(DigestBatch $batch, int $seconds, string $reason): int
    {
        $batch->update(['status' => 'retry', 'not_before' => now('UTC')->addSeconds($seconds), 'error_code' => $reason]);

        return max(1, $seconds);
    }

    private function resolve(DigestBatch $batch, string $status, string $reason): ?int
    {
        $batch->update(['status' => $status, 'error_code' => $reason]);

        return null;
    }

    private function cooldown(): int
    {
        $until = RuntimeState::query()->find('telegram_provider')?->value['cooldown_until'] ?? null;
        if (! is_string($until) || ! CarbonImmutable::now('UTC')->lt(CarbonImmutable::parse($until, 'UTC'))) {
            return 0;
        }

        return max(1, (int) ceil(CarbonImmutable::now('UTC')->diffInSeconds(CarbonImmutable::parse($until, 'UTC'))));
    }
}
