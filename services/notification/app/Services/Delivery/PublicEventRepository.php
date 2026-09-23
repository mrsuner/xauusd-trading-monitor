<?php

namespace App\Services\Delivery;

use App\ValueObjects\PublicEventData;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;

class PublicEventRepository
{
    public function findVisible(string $id): ?PublicEventData
    {
        $tags = DB::getDriverName() === 'pgsql'
            ? DB::raw('to_json(pe.topic_tags)::text as topic_tags_json')
            : 'pe.topic_tags as topic_tags_json';
        $row = DB::table($this->table('public_events').' as pe')
            ->select([
                'pe.id', 'pe.upstream_event_id', 'pe.received_at', 'pe.event_time',
                'pe.generated_at', 'pe.severity', 'pe.content_category', $tags,
            ])
            ->where('pe.id', $id)
            ->where('pe.is_visible', true)
            ->first();

        return $row === null ? null : $this->hydrate($row);
    }

    /** @return list<PublicEventData> */
    public function recent(CarbonImmutable $startedAt, CarbonImmutable $now, int $limit): array
    {
        $eventsTable = $this->table('public_events');
        $tags = DB::getDriverName() === 'pgsql'
            ? DB::raw('to_json(pe.topic_tags)::text as topic_tags_json')
            : 'pe.topic_tags as topic_tags_json';
        $rows = DB::table($eventsTable.' as pe')
            ->select([
                'pe.id', 'pe.upstream_event_id', 'pe.received_at', 'pe.event_time',
                'pe.generated_at', 'pe.severity', 'pe.content_category', $tags,
            ])
            ->where('pe.is_visible', true)
            ->where('pe.received_at', '>=', $startedAt)
            ->where('pe.received_at', '>', $now->subMinutes((int) config('notification.scan.freshness_minutes', 60)))
            ->orderBy('pe.received_at')->orderBy('pe.id')
            ->limit($limit * 2)
            ->get();

        $seen = [];
        $events = [];
        foreach ($rows as $row) {
            $upstreamId = (string) $row->upstream_event_id;
            if (isset($seen[$upstreamId])) {
                continue;
            }
            $seen[$upstreamId] = true;

            $receivedAt = CarbonImmutable::parse($row->received_at, 'UTC');
            $effectiveTime = CarbonImmutable::parse($row->event_time ?? $row->generated_at ?? $row->received_at, 'UTC');
            if ($effectiveTime->lt($now->subMinutes((int) config('notification.scan.freshness_minutes', 60)))
                || $effectiveTime->gt($now->addMinutes((int) config('notification.scan.future_tolerance_minutes', 5)))) {
                continue;
            }

            $events[] = $this->hydrate($row);
            if (count($events) >= $limit) {
                break;
            }
        }

        return $events;
    }

    private function hydrate(object $row): PublicEventData
    {
        return new PublicEventData(
            id: (string) $row->id,
            upstreamEventId: (string) $row->upstream_event_id,
            receivedAt: CarbonImmutable::parse($row->received_at, 'UTC'),
            effectiveEventTime: CarbonImmutable::parse($row->event_time ?? $row->generated_at ?? $row->received_at, 'UTC'),
            severity: (string) $row->severity,
            category: $row->content_category === null ? null : (string) $row->content_category,
            tags: $this->decodeList($row->topic_tags_json),
            summaries: $this->summaries((string) $row->id),
        );
    }

    /** @return array<string, string> */
    private function summaries(string $publicEventId): array
    {
        return DB::table($this->table('public_events_translations'))
            ->where('public_event_id', $publicEventId)
            ->whereNotNull('summary')
            ->orderBy('language')
            ->get(['language', 'summary'])
            ->mapWithKeys(function (object $row): array {
                $summary = preg_replace('/\s+/u', ' ', trim((string) $row->summary)) ?? '';

                return $summary === '' ? [] : [(string) $row->language => $summary];
            })
            ->all();
    }

    /** @return list<string> */
    private function decodeList(mixed $value): array
    {
        if (is_array($value)) {
            return array_values(array_map('strval', $value));
        }
        $decoded = json_decode((string) $value, true);

        return is_array($decoded) ? array_values(array_map('strval', $decoded)) : [];
    }

    private function table(string $table): string
    {
        return DB::getDriverName() === 'pgsql' ? 'public.'.$table : $table;
    }
}
