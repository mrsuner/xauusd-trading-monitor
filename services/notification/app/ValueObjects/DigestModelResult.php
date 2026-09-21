<?php

namespace App\ValueObjects;

readonly class DigestModelResult
{
    /** @param array<string, mixed> $content */
    public function __construct(
        public array $content,
        public ?string $requestId,
        public int $promptTokens,
        public int $completionTokens,
        public int $latencyMs,
    ) {}
}
