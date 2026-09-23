<?php

namespace App\ValueObjects;

readonly class ContentSelection
{
    public function __construct(
        public string $language,
        public string $summary,
        public bool $isFallback,
    ) {}
}
