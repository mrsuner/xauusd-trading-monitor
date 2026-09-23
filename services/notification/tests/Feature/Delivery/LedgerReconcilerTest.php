<?php

namespace Tests\Feature\Delivery;

use App\Enums\DeliveryStatus;
use App\Jobs\SendTelegramDelivery;
use App\Models\Delivery;
use App\Models\Subscriber;
use App\Services\Delivery\LedgerReconciler;
use Carbon\CarbonImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Str;
use Tests\TestCase;

class LedgerReconcilerTest extends TestCase
{
    use RefreshDatabase;

    private CarbonImmutable $now;

    protected function setUp(): void
    {
        parent::setUp();
        $this->now = CarbonImmutable::parse('2026-09-11T12:00:00Z');
        CarbonImmutable::setTestNow($this->now);
        Queue::fake();
    }

    protected function tearDown(): void
    {
        CarbonImmutable::setTestNow();
        parent::tearDown();
    }

    public function test_reconciler_expires_old_work_and_redispatches_only_stale_nonterminal_rows(): void
    {
        $stalePending = $this->delivery('pending', [
            'dispatch_requested_at' => $this->now->subMinutes(3),
        ]);
        $freshPending = $this->delivery('pending', [
            'dispatch_requested_at' => $this->now,
            'dispatch_confirmed_at' => $this->now,
        ]);
        $staleSending = $this->delivery('sending', [
            'last_attempt_at' => $this->now->subMinute(),
            'attempt_count' => 1,
        ]);
        $expired = $this->delivery('retry', ['expires_at' => $this->now]);
        $sent = $this->delivery('sent');

        $result = app(LedgerReconciler::class)->reconcile();

        self::assertSame(['expired' => 1, 'recovered_sending' => 1, 'dispatched' => 2], $result);
        self::assertSame(DeliveryStatus::Expired, $expired->fresh()->status);
        self::assertSame(DeliveryStatus::Sent, $sent->fresh()->status);
        self::assertSame(DeliveryStatus::Pending, $freshPending->fresh()->status);
        self::assertSame(1, $staleSending->fresh()->attempt_count);
        self::assertSame('provider_outcome_ambiguous', $staleSending->fresh()->error_code);
        self::assertNotNull($stalePending->fresh()->dispatch_requested_at);
        Queue::assertPushed(SendTelegramDelivery::class, 2);
    }

    /** @param array<string, mixed> $overrides */
    private function delivery(string $status, array $overrides = []): Delivery
    {
        $subscriber = Subscriber::query()->create([
            'account_user_id' => (string) Str::ulid(),
            'master_enabled' => true,
            'match_all_categories' => true,
            'min_severity' => 'A',
            'content_language' => 'zh-Hant',
            'revision' => 1,
            'effective_from' => $this->now->subHour(),
        ]);
        $channel = $subscriber->channels()->create([
            'type' => 'telegram',
            'enabled' => true,
            'verified' => true,
            'revision' => 1,
            'enabled_from' => $this->now->subHour(),
        ]);

        return Delivery::query()->create([
            'subscriber_id' => $subscriber->id,
            'channel_id' => $channel->id,
            'upstream_event_id' => (string) Str::uuid(),
            'public_event_id' => (string) Str::uuid(),
            'channel_type' => 'telegram',
            'priority' => 'standard',
            'subscriber_revision' => 1,
            'channel_revision' => 1,
            'status' => $status,
            'attempt_count' => 0,
            'not_before' => $this->now->subMinute(),
            'expires_at' => $this->now->addHour(),
            ...$overrides,
        ]);
    }
}
