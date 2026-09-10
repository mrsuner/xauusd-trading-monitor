<?php

namespace Tests\Unit\Preferences;

use App\Enums\Severity;
use App\Services\Preferences\EventMatcher;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class EventMatcherTest extends TestCase
{
    /** @return iterable<string, array{bool, list<string>, list<string>, Severity, ?string, list<string>, ?string, bool}> */
    public static function cases(): iterable
    {
        yield 'category and tag match' => [false, ['macro_data'], ['fed'], Severity::A, 'macro_data', ['fed'], 'S', true];
        yield 'selected categories are OR' => [false, ['macro_data', 'energy'], [], Severity::A, 'energy', [], 'A', true];
        yield 'category and tag are AND' => [false, ['macro_data'], ['fed'], Severity::A, 'macro_data', ['ecb'], 'S', false];
        yield 'all categories supports tag only' => [true, [], ['fed'], Severity::A, 'macro_data', ['fed'], 'A', true];
        yield 'empty categories match nothing' => [false, [], [], Severity::C, 'macro_data', [], 'S', false];
        yield 'null category is rejected' => [true, [], [], Severity::C, null, [], 'S', false];
        yield 'inactive category is rejected' => [true, [], [], Severity::C, 'unknown', [], 'S', false];
        yield 'disabled selected tags do not become unrestricted' => [true, [], ['retired'], Severity::C, 'macro_data', ['retired'], 'S', false];
        yield 'severity below threshold is rejected' => [true, [], [], Severity::A, 'macro_data', [], 'B', false];
        yield 'unknown severity is rejected' => [true, [], [], Severity::C, 'macro_data', [], 'X', false];
    }

    #[DataProvider('cases')]
    public function test_contract(
        bool $allCategories,
        array $categories,
        array $tags,
        Severity $minimum,
        ?string $eventCategory,
        array $eventTags,
        ?string $eventSeverity,
        bool $expected,
    ): void {
        $actual = (new EventMatcher)->matches(
            $allCategories,
            $categories,
            $tags,
            $minimum,
            ['macro_data', 'energy'],
            ['fed', 'ecb'],
            $eventCategory,
            $eventTags,
            $eventSeverity,
        );

        self::assertSame($expected, $actual);
    }
}
