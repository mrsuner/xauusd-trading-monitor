<?php

namespace App\Services\Digests;

use App\ValueObjects\DigestInput;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;

class DigestInputRepository
{
    /** @return array{events: list<DigestInput>, truncated: bool} */
    public function select(string $topic, CarbonImmutable $windowStart, CarbonImmutable $windowEnd, int $limit): array
    {
        $table = DB::getDriverName() === 'pgsql' ? 'public.public_events' : 'public_events';
        $translations = DB::getDriverName() === 'pgsql'
            ? 'public.public_events_translations'
            : 'public_events_translations';
        $rows = DB::table($table)
            ->where('is_visible', true)
            ->whereNull('invalidated_at')
            ->whereNotNull('public_content_ready_at')
            ->whereIn('id', DB::table($translations)
                ->select('public_event_id')
                ->whereNotNull('summary')
                ->whereRaw("trim(summary) <> ''"))
            ->where('public_content_ready_at', '>=', $windowStart)
            ->where('public_content_ready_at', '<', $windowEnd)
            ->orderByRaw("case severity when 'S' then 0 when 'A' then 1 when 'B' then 2 else 3 end")
            ->orderByRaw('coalesce(relevance_score, -1) desc')
            ->orderBy('public_content_ready_at')
            ->orderBy('id')
            ->get(['id', 'upstream_event_id', 'severity', 'relevance_score', 'event_time', 'public_content_ready_at', 'route_metadata', 'content_category']);

        $seen = [];
        $matched = [];
        foreach ($rows as $row) {
            $domains = $this->domains($row->route_metadata, $row->content_category);
            $eventTime = $row->event_time === null ? null : CarbonImmutable::parse($row->event_time, 'UTC');
            if (! in_array($topic, $domains, true)
                || isset($seen[(string) $row->upstream_event_id])
                || ($eventTime !== null && $eventTime->lt($windowStart->subDay()))) {
                continue;
            }
            $seen[(string) $row->upstream_event_id] = true;
            $matched[] = new DigestInput(
                id: (string) $row->id,
                upstreamEventId: (string) $row->upstream_event_id,
                severity: (string) $row->severity,
                relevanceScore: $row->relevance_score === null ? null : (int) $row->relevance_score,
                readyAt: CarbonImmutable::parse($row->public_content_ready_at, 'UTC'),
                eventTime: $eventTime,
                domains: $domains,
                summaries: $this->summaries((string) $row->id),
            );
        }

        return ['events' => array_slice($matched, 0, $limit), 'truncated' => count($matched) > $limit];
    }

    /** @return list<string> */
    private function domains(mixed $value, ?string $contentCategory): array
    {
        $metadata = is_array($value) ? $value : json_decode((string) $value, true);
        if (! is_array($metadata)) {
            $metadata = [];
        }
        $domains = array_merge(
            isset($metadata['primary_domain']) ? [(string) $metadata['primary_domain']] : [],
            is_array($metadata['matched_domains'] ?? null) ? array_map('strval', $metadata['matched_domains']) : [],
        );

        $domains = array_values(array_unique(array_filter($domains)));
        if ($domains !== []) {
            return $domains;
        }

        // Events published before domain routing have no domain metadata. Only
        // unambiguous legacy categories are mapped; the new routed domain wins.
        return match ($contentCategory) {
            'military', 'diplomacy', 'sanctions' => ['geopolitics'],
            'fed', 'central_bank' => ['monetary'],
            'energy' => ['energy'],
            'economy' => ['macro_data'],
            default => [],
        };
    }

    /** @return array<string, string> */
    private function summaries(string $eventId): array
    {
        $table = DB::getDriverName() === 'pgsql' ? 'public.public_events_translations' : 'public_events_translations';

        return DB::table($table)->where('public_event_id', $eventId)
            ->whereNotNull('summary')
            ->whereRaw("trim(summary) <> ''")
            ->orderBy('language')->get(['language', 'summary'])
            ->mapWithKeys(fn (object $row): array => [
                (string) $row->language => mb_substr(trim((string) $row->summary), 0, 2000),
            ])->all();
    }
}
