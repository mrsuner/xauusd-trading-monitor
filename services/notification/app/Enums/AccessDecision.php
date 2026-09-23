<?php

namespace App\Enums;

enum AccessDecision: string
{
    case Active = 'active';
    case Inactive = 'inactive';
    case Missing = 'missing';
    case Unknown = 'unknown';
}
