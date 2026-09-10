<?php

namespace App\Services\Delivery;

use App\ValueObjects\PublicEventData;
use Carbon\CarbonImmutable;

class ContentSchedule
{
    public function notBefore(PublicEventData $event, string $requestedLanguage, CarbonImmutable $now): CarbonImmutable
    {
        if (isset($event->summaries[$requestedLanguage])) {
            return $now;
        }

        $hasAlternative = $event->summaries !== [];
        if ($event->severity === 'S' && $hasAlternative) {
            return $now;
        }

        if ($event->severity === 'A') {
            $deadline = $event->receivedAt->addMinutes(2);
            if ($hasAlternative && $now->greaterThanOrEqualTo($deadline)) {
                return $now;
            }

            return $deadline->greaterThan($now) ? $deadline : $now->addMinute();
        }

        return $now->addMinute();
    }
}
