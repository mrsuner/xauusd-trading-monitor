<?php

namespace Tests\Unit\Delivery;

use App\Services\Delivery\NotificationDeduplicator;
use Tests\TestCase;

class NotificationDeduplicatorTest extends TestCase
{
    public function test_only_consistent_high_confidence_duplicate_qualifies(): void
    {
        $service = app(NotificationDeduplicator::class);
        $answer = ['type' => 'choice', 'choice' => 'duplicate', 'confidence' => 0.99,
            'probabilities' => ['duplicate' => 0.99, 'material_update' => 0.01, 'unrelated' => 0, 'insufficient_evidence' => 0]];
        self::assertTrue($service->clearDuplicate($answer));
        foreach ([['confidence' => 0.7], ['confidence' => NAN], ['confidence' => true],
            ['choice' => 'material_update'], ['type' => 'other'], ['probabilities' => ['duplicate' => 1]],
            ['probabilities' => ['duplicate' => 1, 'material_update' => 1, 'unrelated' => 0, 'insufficient_evidence' => 0]]] as $change) {
            self::assertFalse($service->clearDuplicate(array_replace($answer, $change)));
        }
    }

    public function test_figures_periods_and_status_changes_veto_merges(): void
    {
        $service = app(NotificationDeduplicator::class);
        foreach ([['CPI 3.25%', 'CPI 3.5%'], ['August CPI 3.25%', 'September CPI 3.25%'],
            ['Minister arrived for talks', 'Minister has met the counterpart'],
            ['Rumors of gold sales', 'Bank denied gold sales'], ['168 children', '198 children']] as [$left, $right]) {
            self::assertTrue($service->conflictingFacts(['content' => $left], ['content' => $right]));
        }
        self::assertFalse($service->conflictingFacts(['content' => 'CPI 3.25% @source1'],
            ['content' => 'CPI is 3.25 percent @source2']));
        self::assertFalse($service->conflictingFacts(['content' => 'CPI ۳.۲۵%'], ['content' => 'CPI 3.25%']));
    }
}
