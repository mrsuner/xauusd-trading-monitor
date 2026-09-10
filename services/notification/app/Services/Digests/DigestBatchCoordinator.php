<?php

namespace App\Services\Digests;

use App\Jobs\SendDigestBatch;
use App\Models\DigestBatch;
use App\Models\DigestEdition;
use App\Models\DigestPreference;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;

class DigestBatchCoordinator
{
    public function scan(?CarbonImmutable $now = null): int
    {
        $now ??= CarbonImmutable::now('UTC');
        $windowStart = $now->startOfDay()->subDay();
        $deadline = $now->startOfDay()->addMinutes((int) config('notification.digest.deadline_minute', 60));
        $created = 0;

        DigestPreference::query()->with(['topics', 'subscriber.channels'])
            ->where('enabled', true)->orderBy('subscriber_id')->chunkById(100, function ($preferences) use ($now, $windowStart, $deadline, &$created): void {
                foreach ($preferences as $preference) {
                    if (DigestBatch::query()->where('subscriber_id', $preference->subscriber_id)->where('window_start', $windowStart)->exists()) {
                        continue;
                    }
                    $topics = $preference->topics->pluck('topic')->all();
                    $editions = DigestEdition::query()->with(['translations' => fn ($query) => $query->where('language', $preference->subscriber->content_language)])
                        ->where('window_start', $windowStart)->whereIn('topic', $topics)->get();
                    $allTerminal = count($topics) === $editions->count()
                        && $editions->every(fn (DigestEdition $edition): bool => in_array($edition->status, ['published', 'no_content', 'failed', 'invalidated'], true));
                    if (! $allTerminal && $now->lt($deadline)) {
                        continue;
                    }
                    $ready = $editions->filter(fn (DigestEdition $edition): bool => $edition->status === 'published' && $edition->translations->isNotEmpty());
                    $hasUnavailable = count($topics) !== $editions->count()
                        || $editions->contains(fn (DigestEdition $edition): bool => in_array($edition->status, ['failed', 'invalidated'], true)
                            || ($edition->status === 'published' && $edition->translations->isEmpty()));
                    $channel = $preference->subscriber->channels->first(fn ($channel): bool => $channel->type === 'telegram' && $channel->enabled && $channel->verified);
                    if ($channel === null) {
                        continue;
                    }

                    $batch = DB::transaction(function () use ($preference, $channel, $windowStart, $deadline, $now, $ready, $hasUnavailable): DigestBatch {
                        $batch = DigestBatch::query()->firstOrCreate([
                            'subscriber_id' => $preference->subscriber_id,
                            'window_start' => $windowStart,
                        ], [
                            'channel_id' => $channel->id,
                            'preference_revision' => $preference->revision,
                            'channel_revision' => $channel->revision,
                            'content_language' => $preference->subscriber->content_language,
                            'status' => $ready->isEmpty() ? 'no_content' : 'pending',
                            'attempt_count' => 0,
                            'not_before' => $now,
                            'deadline_at' => $deadline,
                            'error_code' => $hasUnavailable ? 'partial_coverage' : null,
                        ]);
                        if ($batch->wasRecentlyCreated && $ready->isNotEmpty()) {
                            $batch->editions()->sync($ready->pluck('id')->all());
                        }

                        return $batch;
                    });
                    if ($batch->wasRecentlyCreated) {
                        $created++;
                        if ($batch->status === 'pending') {
                            SendDigestBatch::dispatch($batch->id)->afterCommit();
                        }
                    }
                }
            }, 'subscriber_id');

        return $created;
    }
}
