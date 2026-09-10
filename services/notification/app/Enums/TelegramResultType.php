<?php

namespace App\Enums;

enum TelegramResultType: string
{
    case Accepted = 'accepted';
    case RateLimited = 'rate_limited';
    case TransientFailure = 'transient_failure';
    case TargetInvalid = 'target_invalid';
    case ProviderInvalid = 'provider_invalid';
    case PayloadInvalid = 'payload_invalid';
}
