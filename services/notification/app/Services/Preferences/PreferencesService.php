<?php

namespace App\Services\Preferences;

use App\Enums\Severity;
use App\Exceptions\PreferenceException;
use App\Models\Subscriber;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;

class PreferencesService
{
    public function __construct(private TaxonomyCatalog $taxonomy) {}

    /** @return array<string, mixed> */
    public function get(string $accountUserId): array
    {
        $subscriber = Subscriber::query()
            ->with(['categories:key,subscriber_id', 'tags:key,subscriber_id'])
            ->where('account_user_id', $accountUserId)
            ->first();

        return $subscriber === null ? $this->defaults() : $this->serialize($subscriber);
    }

    /**
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    public function replace(string $accountUserId, array $input, bool $hasActiveAccess): array
    {
        $candidate = $this->canonicalize($input);
        $current = Subscriber::query()
            ->with(['categories:key,subscriber_id', 'tags:key,subscriber_id'])
            ->where('account_user_id', $accountUserId)
            ->first();
        $currentValues = $current === null ? $this->defaults() : $this->serialize($current);

        if (! $hasActiveAccess && ! $this->isUnpaidDisableOnly($currentValues, $candidate)) {
            throw new PreferenceException('upgrade_required', 'An active News subscription is required.', 403);
        }

        if ($candidate['master_enabled']) {
            if (! $candidate['match_all_categories'] && $candidate['categories'] === []) {
                throw new PreferenceException(
                    'validation_failed',
                    'At least one category is required before notifications can be enabled.',
                    422,
                    ['categories' => ['Select a category or enable all categories.']],
                );
            }

            $hasChannel = $current?->channels()->where('verified', true)->where('enabled', true)->exists() ?? false;
            if (! $hasChannel) {
                throw new PreferenceException('channel_required', 'A verified and enabled channel is required.', 409);
            }
        }

        if ($candidate === Arr::only($currentValues, array_keys($candidate))) {
            return $currentValues;
        }

        $this->validateTaxonomy($candidate['categories'], $candidate['tags']);

        return DB::transaction(function () use ($accountUserId, $candidate): array {
            $subscriber = Subscriber::query()
                ->where('account_user_id', $accountUserId)
                ->lockForUpdate()
                ->first();

            if ($subscriber === null) {
                $subscriber = Subscriber::query()->create([
                    'id' => (string) Str::uuid(),
                    'account_user_id' => $accountUserId,
                    ...Arr::except($candidate, ['categories', 'tags']),
                    'revision' => 1,
                    'effective_from' => now('UTC'),
                ]);
            } else {
                $subscriber->fill(Arr::except($candidate, ['categories', 'tags']));
                $subscriber->revision++;
                $subscriber->effective_from = now('UTC');
                $subscriber->save();

                DB::table('deliveries')
                    ->where('subscriber_id', $subscriber->id)
                    ->whereIn('status', ['pending', 'retry'])
                    ->update(['status' => 'canceled', 'error_code' => 'preferences_changed', 'updated_at' => now('UTC')]);
            }

            $subscriber->categories()->delete();
            $subscriber->tags()->delete();
            $subscriber->categories()->createMany(array_map(fn (string $key): array => ['key' => $key], $candidate['categories']));
            $subscriber->tags()->createMany(array_map(fn (string $key): array => ['key' => $key], $candidate['tags']));

            return $this->serialize($subscriber->load(['categories:key,subscriber_id', 'tags:key,subscriber_id']));
        });
    }

    /** @return array<string, mixed> */
    private function defaults(): array
    {
        return [
            'master_enabled' => false,
            'match_all_categories' => false,
            'min_severity' => Severity::A->value,
            'content_language' => (string) config('notification.default_language', 'zh-Hant'),
            'categories' => [],
            'tags' => [],
            'revision' => 0,
            'effective_from' => null,
        ];
    }

    /** @return array<string, mixed> */
    private function serialize(Subscriber $subscriber): array
    {
        return [
            'master_enabled' => $subscriber->master_enabled,
            'match_all_categories' => $subscriber->match_all_categories,
            'min_severity' => $subscriber->min_severity->value,
            'content_language' => $subscriber->content_language,
            'categories' => $subscriber->categories->pluck('key')->sort()->values()->all(),
            'tags' => $subscriber->tags->pluck('key')->sort()->values()->all(),
            'revision' => $subscriber->revision,
            'effective_from' => $subscriber->effective_from?->toIso8601String(),
        ];
    }

    /** @param array<string, mixed> $input */
    private function canonicalize(array $input): array
    {
        $categories = array_values(array_unique($input['categories']));
        $tags = array_values(array_unique($input['tags']));
        sort($categories);
        sort($tags);

        return [
            'master_enabled' => (bool) $input['master_enabled'],
            'match_all_categories' => (bool) $input['match_all_categories'],
            'min_severity' => (string) $input['min_severity'],
            'content_language' => (string) $input['content_language'],
            'categories' => $categories,
            'tags' => $tags,
        ];
    }

    /** @param list<string> $categories @param list<string> $tags */
    private function validateTaxonomy(array $categories, array $tags): void
    {
        try {
            $catalog = $this->taxonomy->keys();
        } catch (RuntimeException) {
            throw new PreferenceException('taxonomy_unavailable', 'Subscription taxonomy is unavailable.', 503);
        }

        $unknownCategories = array_values(array_diff($categories, $catalog['categories']));
        $unknownTags = array_values(array_diff($tags, $catalog['tags']));
        if ($unknownCategories !== [] || $unknownTags !== []) {
            throw new PreferenceException(
                'validation_failed',
                'One or more subscription keys are unavailable.',
                422,
                array_filter([
                    'categories' => $unknownCategories === [] ? null : ['Unknown categories: '.implode(', ', $unknownCategories).'.'],
                    'tags' => $unknownTags === [] ? null : ['Unknown tags: '.implode(', ', $unknownTags).'.'],
                ]),
            );
        }
    }

    /** @param array<string, mixed> $current @param array<string, mixed> $candidate */
    private function isUnpaidDisableOnly(array $current, array $candidate): bool
    {
        $expected = Arr::only($current, array_keys($candidate));
        $expected['master_enabled'] = false;

        return $candidate === $expected;
    }
}
