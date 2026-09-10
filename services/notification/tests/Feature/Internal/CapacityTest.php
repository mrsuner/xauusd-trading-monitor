<?php

namespace Tests\Feature\Internal;

use App\Models\RuntimeState;
use Carbon\CarbonImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class CapacityTest extends TestCase
{
    use RefreshDatabase;

    private CarbonImmutable $now;

    protected function setUp(): void
    {
        parent::setUp();
        $this->now = CarbonImmutable::parse('2026-09-11T12:00:00Z');
        CarbonImmutable::setTestNow($this->now);
        config([
            'services.notification_internal.secret' => 'test-internal-secret',
            'notification.admission_enabled' => false,
        ]);
    }

    protected function tearDown(): void
    {
        CarbonImmutable::setTestNow();
        parent::tearDown();
    }

    public function test_capacity_is_private_and_closed_by_default(): void
    {
        $this->getJson('/internal/capacity')->assertUnauthorized();

        $this->withHeader('X-Internal-Secret', 'test-internal-secret')->getJson('/internal/capacity')
            ->assertOk()
            ->assertJsonPath('data.status', 'closed')
            ->assertJsonPath('data.reasons.0', 'operator_closed')
            ->assertJsonPath('data.activated_subscribers', 0)
            ->assertJsonPath('data.initial_paid_cap', 100);
    }

    public function test_admission_requires_fifteen_continuous_healthy_minutes(): void
    {
        config(['notification.admission_enabled' => true]);
        $this->recordScan($this->now);

        $this->capacity()->assertOk()
            ->assertJsonPath('data.status', 'closed')
            ->assertJsonPath('data.reasons.0', 'recovery_window');

        $later = $this->now->addMinutes(15);
        CarbonImmutable::setTestNow($later);
        $this->recordScan($later);
        $this->capacity()->assertOk()
            ->assertJsonPath('data.status', 'accepting')
            ->assertJsonPath('data.reasons', []);
    }

    private function recordScan(CarbonImmutable $at): void
    {
        RuntimeState::query()->updateOrCreate(
            ['key' => 'scanner'],
            ['value' => ['last_scan_at' => $at->toIso8601String()]],
        );
    }

    private function capacity(): TestResponse
    {
        return $this->withHeader('X-Internal-Secret', 'test-internal-secret')->getJson('/internal/capacity');
    }
}
