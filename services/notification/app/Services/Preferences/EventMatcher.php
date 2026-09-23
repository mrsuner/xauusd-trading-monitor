<?php

namespace App\Services\Preferences;

use App\Enums\Severity;

class EventMatcher
{
    /**
     * @param  list<string>  $selectedCategories
     * @param  list<string>  $selectedTags
     * @param  list<string>  $activeCategories
     * @param  list<string>  $activeTags
     * @param  list<string>  $eventTags
     */
    public function matches(
        bool $matchAllCategories,
        array $selectedCategories,
        array $selectedTags,
        Severity $minimumSeverity,
        array $activeCategories,
        array $activeTags,
        ?string $eventCategory,
        array $eventTags,
        ?string $eventSeverity,
    ): bool {
        if ($eventCategory === null || ! in_array($eventCategory, $activeCategories, true)) {
            return false;
        }

        $severity = Severity::tryFrom((string) $eventSeverity);
        if ($severity === null || $severity->rank() < $minimumSeverity->rank()) {
            return false;
        }

        if (! $matchAllCategories && ! in_array($eventCategory, $selectedCategories, true)) {
            return false;
        }

        if ($selectedTags === []) {
            return true;
        }

        $selectableTags = array_values(array_intersect($selectedTags, $activeTags));
        if ($selectableTags === []) {
            return false;
        }

        return array_intersect($eventTags, $selectableTags) !== [];
    }
}
