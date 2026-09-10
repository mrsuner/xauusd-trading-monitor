<?php

namespace App\Services\Channels;

use App\Exceptions\ChannelException;
use App\Models\Channel;
use App\Models\Subscriber;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\Str;

class ChannelService
{
    /** @return list<array<string, mixed>> */
    public function list(string $accountUserId): array
    {
        $subscriber = Subscriber::query()->where('account_user_id', $accountUserId)->first();
        if ($subscriber === null) {
            return [];
        }

        return $subscriber->channels()->orderBy('type')->get()->map($this->serialize(...))->all();
    }

    /** @return array{deep_link: string, expires_at: string} */
    public function createTelegramLink(string $accountUserId, bool $hasActiveAccess): array
    {
        if (! $hasActiveAccess) {
            throw new ChannelException('upgrade_required', 'An active News subscription is required.', 403);
        }

        $botUsername = trim((string) config('notification.telegram.bot_username'), '@ ');
        $fingerprintKey = (string) config('notification.channel_fingerprint_key');
        if ($botUsername === '' || $fingerprintKey === '') {
            throw new ChannelException('service_unavailable', 'Telegram linking is not configured.', 503);
        }

        $rateKey = 'telegram-link:'.$accountUserId;
        if (RateLimiter::tooManyAttempts($rateKey, 5)) {
            throw new ChannelException('rate_limited', 'Too many Telegram link requests.', 429);
        }
        RateLimiter::hit($rateKey, 600);

        $plainCode = Str::of(base64_encode(random_bytes(32)))
            ->replace(['+', '/', '='], ['-', '_', ''])
            ->toString();
        $expiresAt = now('UTC')->addMinutes((int) config('notification.telegram.link_ttl_minutes', 10));

        DB::transaction(function () use ($accountUserId, $plainCode, $expiresAt): void {
            $subscriber = $this->subscriber($accountUserId);
            $channel = $subscriber->channels()->where('type', 'telegram')->lockForUpdate()->first();

            if ($channel?->verified) {
                throw new ChannelException('channel_already_linked', 'Delete the existing Telegram binding before relinking.', 409);
            }

            $values = [
                'enabled' => false,
                'verified' => false,
                'link_code_hash' => hash('sha256', $plainCode),
                'link_expires_at' => $expiresAt,
                'last_error_code' => null,
            ];

            if ($channel === null) {
                $subscriber->channels()->create(['type' => 'telegram', 'revision' => 1, ...$values]);
            } else {
                $channel->fill($values);
                $channel->revision++;
                $channel->save();
            }
        });

        return [
            'deep_link' => "https://t.me/{$botUsername}?start={$plainCode}",
            'expires_at' => $expiresAt->toIso8601String(),
        ];
    }

    /** @return array<string, mixed> */
    public function setEnabled(string $accountUserId, string $type, bool $enabled, bool $hasActiveAccess): array
    {
        $this->ensureTelegram($type);
        if ($enabled && ! $hasActiveAccess) {
            throw new ChannelException('upgrade_required', 'An active News subscription is required.', 403);
        }

        return DB::transaction(function () use ($accountUserId, $enabled): array {
            $subscriber = Subscriber::query()->where('account_user_id', $accountUserId)->lockForUpdate()->first();
            $channel = $subscriber?->channels()->where('type', 'telegram')->lockForUpdate()->first();
            if ($channel === null || ! $channel->verified) {
                throw new ChannelException('channel_unverified', 'Telegram must be linked before it can be enabled.', 409);
            }

            if ($channel->enabled !== $enabled) {
                $channel->enabled = $enabled;
                $channel->enabled_from = $enabled ? now('UTC') : null;
                $channel->revision++;
                $channel->save();
                if (! $enabled) {
                    $this->cancelPending($channel->id, 'channel_disabled');
                }
            }

            return $this->serialize($channel);
        });
    }

    public function unlink(string $accountUserId, string $type): void
    {
        $this->ensureTelegram($type);

        DB::transaction(function () use ($accountUserId): void {
            $subscriber = Subscriber::query()->where('account_user_id', $accountUserId)->lockForUpdate()->first();
            $channel = $subscriber?->channels()->where('type', 'telegram')->lockForUpdate()->first();
            if ($channel === null) {
                return;
            }

            $channel->fill([
                'enabled' => false,
                'verified' => false,
                'enabled_from' => null,
                'encrypted_target' => null,
                'target_fingerprint' => null,
                'target_hint' => null,
                'link_code_hash' => null,
                'link_expires_at' => null,
                'linked_at' => null,
                'last_error_code' => null,
            ]);
            $channel->revision++;
            $channel->save();
            $this->cancelPending($channel->id, 'channel_unlinked');
        });
    }

    /** Called by the singleton Telegram poller after validating a private /start command. */
    public function consumeTelegramLink(string $plainCode, string $chatId): bool
    {
        $fingerprintKey = (string) config('notification.channel_fingerprint_key');
        if ($fingerprintKey === '') {
            throw new ChannelException('service_unavailable', 'Channel encryption is not configured.', 503);
        }

        return DB::transaction(function () use ($plainCode, $chatId, $fingerprintKey): bool {
            $channel = Channel::query()
                ->where('link_code_hash', hash('sha256', $plainCode))
                ->lockForUpdate()
                ->first();
            if ($channel === null || $channel->link_expires_at?->isPast()) {
                return false;
            }

            $fingerprint = hash_hmac('sha256', $chatId, $fingerprintKey);
            $occupied = Channel::query()
                ->where('type', 'telegram')
                ->where('target_fingerprint', $fingerprint)
                ->whereKeyNot($channel->id)
                ->exists();
            if ($occupied) {
                throw new ChannelException('target_in_use', 'This Telegram chat is already linked.', 409);
            }

            $channel->fill([
                'enabled' => false,
                'verified' => true,
                'encrypted_target' => Crypt::encryptString($chatId),
                'target_fingerprint' => $fingerprint,
                'target_hint' => $this->hint($chatId),
                'link_code_hash' => null,
                'link_expires_at' => null,
                'linked_at' => now('UTC'),
                'last_error_code' => null,
            ]);
            $channel->revision++;
            $channel->save();

            return true;
        });
    }

    public function stopTelegramChat(string $chatId): bool
    {
        $fingerprintKey = (string) config('notification.channel_fingerprint_key');
        if ($fingerprintKey === '') {
            throw new ChannelException('service_unavailable', 'Channel encryption is not configured.', 503);
        }

        return DB::transaction(function () use ($chatId, $fingerprintKey): bool {
            $channel = Channel::query()
                ->where('type', 'telegram')
                ->where('target_fingerprint', hash_hmac('sha256', $chatId, $fingerprintKey))
                ->lockForUpdate()
                ->first();
            if ($channel === null) {
                return false;
            }

            if ($channel->enabled) {
                $channel->enabled = false;
                $channel->enabled_from = null;
                $channel->revision++;
                $channel->save();
                $this->cancelPending($channel->id, 'telegram_stop');
            }

            return true;
        });
    }

    public function revokeForMissingAccount(string $subscriberId): void
    {
        DB::transaction(function () use ($subscriberId): void {
            Channel::query()->where('subscriber_id', $subscriberId)->lockForUpdate()->get()
                ->each(function (Channel $channel): void {
                    $channel->fill([
                        'enabled' => false,
                        'verified' => false,
                        'enabled_from' => null,
                        'encrypted_target' => null,
                        'target_fingerprint' => null,
                        'target_hint' => null,
                        'link_code_hash' => null,
                        'link_expires_at' => null,
                        'last_error_code' => 'account_missing',
                    ]);
                    $channel->revision++;
                    $channel->save();
                    $this->cancelPending($channel->id, 'account_missing');
                });
        });
    }

    /** @return array<string, mixed> */
    private function serialize(Channel $channel): array
    {
        return [
            'type' => $channel->type,
            'enabled' => $channel->enabled,
            'verified' => $channel->verified,
            'target_hint' => $channel->target_hint,
            'last_error_code' => $channel->last_error_code,
            'linked_at' => $channel->linked_at?->toIso8601String(),
            'revision' => $channel->revision,
        ];
    }

    private function subscriber(string $accountUserId): Subscriber
    {
        return Subscriber::query()->firstOrCreate(
            ['account_user_id' => $accountUserId],
            [
                'master_enabled' => false,
                'match_all_categories' => false,
                'min_severity' => 'A',
                'content_language' => (string) config('notification.default_language', 'zh-Hant'),
                'revision' => 1,
                'effective_from' => now('UTC'),
            ],
        );
    }

    private function cancelPending(string $channelId, string $reason): void
    {
        DB::table('deliveries')->where('channel_id', $channelId)
            ->whereIn('status', ['pending', 'retry'])
            ->update(['status' => 'canceled', 'error_code' => $reason, 'updated_at' => now('UTC')]);
    }

    private function ensureTelegram(string $type): void
    {
        if ($type !== 'telegram') {
            throw new ChannelException('channel_not_supported', 'Only Telegram is supported.', 422);
        }
    }

    private function hint(string $chatId): string
    {
        return '***'.substr($chatId, -4);
    }
}
