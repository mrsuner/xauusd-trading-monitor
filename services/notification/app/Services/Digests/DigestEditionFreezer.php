<?php

namespace App\Services\Digests;

use App\Jobs\GenerateDigestEdition;
use App\Models\DigestEdition;
use App\ValueObjects\DigestInput;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;

class DigestEditionFreezer
{
    public function __construct(private DigestInputRepository $inputs) {}

    /** @return list<DigestEdition> */
    public function freezePreviousDay(?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now('UTC');
        $windowEnd = $now->startOfDay();
        $windowStart = $windowEnd->subDay();
        $editions = [];
        foreach (config('notification.digest.topics', []) as $topic) {
            $editions[] = $this->freeze((string) $topic, $windowStart, $windowEnd);
        }

        return $editions;
    }

    public function freeze(
        string $topic,
        CarbonImmutable $windowStart,
        CarbonImmutable $windowEnd,
        bool $dispatchGeneration = true,
    ): DigestEdition {
        $existing = DigestEdition::query()->where('topic', $topic)->where('window_start', $windowStart)->first();
        if ($existing !== null) {
            return $existing;
        }

        $selection = $this->inputs->select(
            $topic,
            $windowStart,
            $windowEnd,
            (int) config('notification.digest.input_limit', 20),
        );
        $events = $selection['events'];
        $hash = hash('sha256', json_encode(array_map($this->payload(...), $events), JSON_THROW_ON_ERROR));

        $edition = DB::transaction(function () use ($topic, $windowStart, $windowEnd, $events, $selection, $hash): DigestEdition {
            $edition = DigestEdition::query()->create([
                'topic' => $topic,
                'window_start' => $windowStart,
                'window_end' => $windowEnd,
                'cutoff_at' => $windowEnd->addMinutes((int) config('notification.digest.freeze_minute', 15)),
                'deadline_at' => $windowEnd->addMinutes((int) config('notification.digest.deadline_minute', 60)),
                'status' => $events === [] ? 'no_content' : 'frozen',
                'input_hash' => $hash,
                'input_count' => count($events),
                'coverage_truncated' => $selection['truncated'],
                'prompt_version' => (string) config('notification.digest.prompt_version'),
            ]);
            foreach ($events as $position => $event) {
                $edition->events()->create([
                    'public_event_id' => $event->id,
                    'upstream_event_id' => $event->upstreamEventId,
                    'position' => $position + 1,
                    'input_payload' => $this->payload($event),
                ]);
            }

            return $edition;
        });

        if ($dispatchGeneration && $edition->status === 'frozen') {
            GenerateDigestEdition::dispatch($edition->id)->afterCommit();
        }

        return $edition;
    }

    /** @return array<string, mixed> */
    private function payload(DigestInput $event): array
    {
        return [
            'event_id' => $event->id,
            'severity' => $event->severity,
            'relevance_score' => $event->relevanceScore,
            'public_content_ready_at' => $event->readyAt->toIso8601String(),
            'event_time' => $event->eventTime?->toIso8601String(),
            'summaries' => $event->summaries,
        ];
    }
}
