<?php

namespace Tests\Unit\Delivery;

use App\Services\Delivery\ContentSchedule;
use App\ValueObjects\PublicEventData;
use Carbon\CarbonImmutable;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class ContentScheduleTest extends TestCase
{
    /** @return iterable<string, array{string, array<string, string>, int}> */
    public static function cases(): iterable
    {
        yield 'requested language ready' => ['B', ['zh-Hant' => '摘要'], 0];
        yield 'S alternative immediate' => ['S', ['en' => 'Summary'], 0];
        yield 'A alternative waits to deadline' => ['A', ['en' => 'Summary'], 120];
        yield 'B alternative still waits' => ['B', ['en' => 'Summary'], 60];
        yield 'no S content waits' => ['S', [], 60];
    }

    #[DataProvider('cases')]
    public function test_language_schedule(string $severity, array $summaries, int $seconds): void
    {
        $now = CarbonImmutable::parse('2026-09-11T00:00:00Z');
        $event = new PublicEventData(
            id: 'event',
            upstreamEventId: 'upstream',
            receivedAt: $now,
            effectiveEventTime: $now,
            severity: $severity,
            category: 'macro_data',
            tags: [],
            summaries: $summaries,
        );

        self::assertSame(
            $now->addSeconds($seconds)->toIso8601String(),
            (new ContentSchedule)->notBefore($event, 'zh-Hant', $now)->toIso8601String(),
        );
    }

    public function test_a_alternative_is_immediate_after_deadline(): void
    {
        $received = CarbonImmutable::parse('2026-09-11T00:00:00Z');
        $now = $received->addMinutes(3);
        $event = new PublicEventData('event', 'upstream', $received, $received, 'A', 'macro_data', [], ['en' => 'Summary']);

        self::assertSame($now->toIso8601String(), (new ContentSchedule)->notBefore($event, 'zh-Hant', $now)->toIso8601String());
    }
}
