<?php

namespace App\ValueObjects;

use Carbon\CarbonImmutable;

readonly class PublicEventData
{
    /** @param list<string> $tags @param array<string, string> $summaries */
    public function __construct(
        public string $id,
        public string $upstreamEventId,
        public CarbonImmutable $receivedAt,
        public CarbonImmutable $effectiveEventTime,
        public string $severity,
        public ?string $category,
        public array $tags,
        public array $summaries,
    ) {}
}
