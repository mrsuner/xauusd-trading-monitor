<?php

namespace App\Services\Digests;

use App\Models\DigestEdition;

class DigestReader
{
    /** @return list<array<string, mixed>> */
    public function list(string $language): array
    {
        return DigestEdition::query()
            ->with(['translations' => fn ($query) => $query->where('language', $language)])
            ->whereIn('status', ['published', 'invalidated'])
            ->where('window_start', '>=', now('UTC')->subDays((int) config('notification.digest.retention_days', 90)))
            ->orderByDesc('window_start')->orderBy('topic')->limit(100)->get()
            ->map(fn (DigestEdition $edition): array => $this->serialize($edition, false))->all();
    }

    /** @return array<string, mixed>|null */
    public function find(string $id, string $language): ?array
    {
        $edition = DigestEdition::query()->with([
            'translations' => fn ($query) => $query->where('language', $language),
            'events',
        ])->whereKey($id)
            ->whereIn('status', ['published', 'invalidated'])
            ->where('window_start', '>=', now('UTC')->subDays((int) config('notification.digest.retention_days', 90)))
            ->first();

        return $edition === null ? null : $this->serialize($edition, true);
    }

    /** @return array<string, mixed> */
    private function serialize(DigestEdition $edition, bool $detail): array
    {
        $invalidated = $edition->status === 'invalidated';
        $translation = $invalidated ? null : $edition->translations->first();
        $result = [
            'id' => $edition->id,
            'topic' => $edition->topic,
            'window_start' => $edition->window_start->toIso8601String(),
            'window_end' => $edition->window_end->toIso8601String(),
            'status' => $invalidated ? 'invalidated' : ($translation === null ? 'language_unavailable' : 'ready'),
            'language' => $translation?->language,
            'title' => $translation?->title,
            'published_at' => $edition->published_at?->toIso8601String(),
            'coverage_truncated' => $edition->coverage_truncated,
            'invalidation_kind' => $invalidated ? $edition->invalidation_kind : null,
            'invalidation_reason' => $invalidated ? $edition->invalidation_reason : null,
        ];
        if ($detail) {
            $result['overview'] = $translation?->overview;
            $result['developments'] = $translation?->developments;
            $result['event_ids'] = $edition->events->pluck('public_event_id')->values()->all();
        }

        return $result;
    }
}
