<?php

namespace App\Enums;

enum DeliveryStatus: string
{
    case Pending = 'pending';
    case Sending = 'sending';
    case Sent = 'sent';
    case Retry = 'retry';
    case Failed = 'failed';
    case Canceled = 'canceled';
    case Expired = 'expired';

    public function terminal(): bool
    {
        return in_array($this, [self::Sent, self::Failed, self::Canceled, self::Expired], true);
    }
}
