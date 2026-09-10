<?php

namespace App\Services\Digests;

use App\Exceptions\PreferenceException;
use App\Models\DigestPreference;
use App\Models\Subscriber;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class DigestPreferencesService
{
    /** @return array<string, mixed> */
    public function get(string $accountUserId): array
    {
        $preference = DigestPreference::query()->with('topics')
            ->whereHas('subscriber', fn ($query) => $query->where('account_user_id', $accountUserId))
            ->first();

        return $preference === null ? $this->defaults() : $this->serialize($preference);
    }

    /** @param list<string> $topics @return array<string, mixed> */
    public function replace(string $accountUserId, bool $enabled, array $topics, bool $hasActiveAccess): array
    {
        $topics = array_values(array_unique($topics));
        sort($topics);
        $current = $this->get($accountUserId);
        if (! $hasActiveAccess && ! ($current['enabled'] && ! $enabled && $current['topics'] === $topics)) {
            throw new PreferenceException('upgrade_required', 'An active News subscription is required.', 403);
        }
        if ($current['enabled'] === $enabled && $current['topics'] === $topics) {
            return $current;
        }

        return DB::transaction(function () use ($accountUserId, $enabled, $topics): array {
            $subscriber = Subscriber::query()->where('account_user_id', $accountUserId)->lockForUpdate()->first();
            if ($subscriber === null) {
                $subscriber = Subscriber::query()->create([
                    'id' => (string) Str::uuid(),
                    'account_user_id' => $accountUserId,
                    'master_enabled' => false,
                    'match_all_categories' => false,
                    'min_severity' => 'A',
                    'content_language' => (string) config('notification.default_language', 'zh-Hant'),
                    'revision' => 1,
                    'effective_from' => now('UTC'),
                ]);
            }
            $preference = DigestPreference::query()->whereKey($subscriber->id)->lockForUpdate()->first();
            if ($preference === null) {
                $preference = DigestPreference::query()->create([
                    'subscriber_id' => $subscriber->id,
                    'enabled' => $enabled,
                    'revision' => 1,
                    'effective_from' => now('UTC'),
                ]);
            } else {
                if ($preference->enabled && ! $enabled) {
                    DB::table('digest_batches')->where('subscriber_id', $subscriber->id)
                        ->whereIn('status', ['pending', 'retry'])
                        ->update(['status' => 'canceled', 'error_code' => 'digest_disabled', 'updated_at' => now('UTC')]);
                }
                $preference->enabled = $enabled;
                $preference->revision++;
                $preference->effective_from = now('UTC');
                $preference->save();
            }
            $preference->topics()->delete();
            $preference->topics()->createMany(array_map(fn (string $topic): array => ['topic' => $topic], $topics));

            return $this->serialize($preference->load('topics'));
        });
    }

    /** @return array{enabled: bool, topics: list<string>, revision: int, effective_from: string|null} */
    private function defaults(): array
    {
        return ['enabled' => false, 'topics' => [], 'revision' => 0, 'effective_from' => null];
    }

    /** @return array<string, mixed> */
    private function serialize(DigestPreference $preference): array
    {
        return [
            'enabled' => $preference->enabled,
            'topics' => $preference->topics->pluck('topic')->sort()->values()->all(),
            'revision' => $preference->revision,
            'effective_from' => $preference->effective_from?->toIso8601String(),
        ];
    }
}
