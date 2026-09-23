<?php

namespace App\ValueObjects;

use Carbon\CarbonImmutable;

readonly class DigestInput
{
    /** @param list<string> $domains @param array<string, string> $summaries */
    public function __construct(
        public string $id,
        public string $upstreamEventId,
        public string $severity,
        public ?int $relevanceScore,
        public CarbonImmutable $readyAt,
        public ?CarbonImmutable $eventTime,
        public array $domains,
        public array $summaries,
    ) {}
}
