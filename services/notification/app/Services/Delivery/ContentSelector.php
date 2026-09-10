<?php

namespace App\Services\Delivery;

use App\ValueObjects\ContentSelection;
use App\ValueObjects\PublicEventData;
use Carbon\CarbonImmutable;

class ContentSelector
{
    public function select(PublicEventData $event, string $requestedLanguage, CarbonImmutable $now): ?ContentSelection
    {
        if (isset($event->summaries[$requestedLanguage])) {
            return new ContentSelection($requestedLanguage, $event->summaries[$requestedLanguage], false);
        }

        $fallbackAllowed = $event->severity === 'S'
            || ($event->severity === 'A' && $now->greaterThanOrEqualTo($event->receivedAt->addMinutes(2)));
        if (! $fallbackAllowed || $event->summaries === []) {
            return null;
        }

        if (isset($event->summaries['en'])) {
            return new ContentSelection('en', $event->summaries['en'], true);
        }

        $summaries = $event->summaries;
        ksort($summaries);
        $language = array_key_first($summaries);

        return $language === null ? null : new ContentSelection($language, $summaries[$language], true);
    }
}
