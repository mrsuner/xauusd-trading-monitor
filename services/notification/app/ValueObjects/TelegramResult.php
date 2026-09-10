<?php

namespace App\ValueObjects;

use App\Enums\TelegramResultType;

readonly class TelegramResult
{
    public function __construct(
        public TelegramResultType $type,
        public ?string $messageId = null,
        public ?int $retryAfter = null,
    ) {}
}
