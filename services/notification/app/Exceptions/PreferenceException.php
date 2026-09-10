<?php

namespace App\Exceptions;

use RuntimeException;

class PreferenceException extends RuntimeException
{
    public function __construct(
        public readonly string $errorCode,
        string $message,
        public readonly int $httpStatus,
        public readonly array $fields = [],
    ) {
        parent::__construct($message);
    }
}
