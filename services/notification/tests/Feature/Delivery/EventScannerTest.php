<?php

namespace Tests\Feature\Delivery;

use App\Models\RuntimeState;
use App\Models\Subscriber;
use App\Services\Delivery\EventScanner;
use Carbon\CarbonImmutable;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Tests\TestCase;

class EventScannerTest extends TestCase
{
    use RefreshDatabase;

    private CarbonImmutable $now;

    protected function setUp(): void
    {
        parent::setUp();
        $this->now = CarbonImmutable::parse('2026-09-11T12:00:00Z');
        CarbonImmutable::setTestNow($this->now);
        Cache::flush();
        config([
            'notification.enabled' => true,
            'notification.dry_run' => false,
            'notification.account.base_url' => 'http://account:8080',
            'notification.account.secret' => 'account-secret',
        ]);
        $this->createPublicTables();
        RuntimeState::query()->create([
            'key' => 'notification',
            'value' => ['started_at' => $this->now->subMinutes(10)->toIso8601String()],
        ]);
    }

    protected function tearDown(): void
    {
        CarbonImmutable::setTestNow();
        parent::tearDown();
    }

    public function test_matching_paid_subscriber_creates_one_durable_delivery_and_receipt(): void
    {
        $userId = (string) Str::ulid();
        $this->subscriber($userId);
        [$eventId, $upstreamId] = $this->event();
        Http::fake(['*' => Http::response(['data' => ['news' => ['access_allowed' => true]]])]);

        $first = app(EventScanner::class)->scan();
        $second = app(EventScanner::class)->scan();

        self::assertSame(1, $first['deliveries']);
        self::assertSame(0, $second['events']);
        $this->assertDatabaseHas('deliveries', [
            'subscriber_id' => Subscriber::query()->firstOrFail()->id,
            'public_event_id' => $eventId,
            'upstream_event_id' => $upstreamId,
            'status' => 'pending',
            'attempt_count' => 0,
        ]);
        $this->assertDatabaseHas('event_receipts', [
            'upstream_event_id' => $upstreamId,
            'public_event_id' => $eventId,
        ]);
        self::assertNotNull(DB::table('event_receipts')->value('processed_at'));
        Http::assertSentCount(1);
    }

    public function test_unknown_access_remains_unresolved_without_blocking_later_retry(): void
    {
        $this->subscriber((string) Str::ulid());
        [, $upstreamId] = $this->event();
        $accountAvailable = false;
        Http::fake(function () use (&$accountAvailable) {
            return $accountAvailable
                ? Http::response(['data' => ['news' => ['access_allowed' => true]]])
                : Http::response(['error' => 'unavailable'], 503);
        });

        $result = app(EventScanner::class)->scan();
        self::assertSame(1, $result['unresolved']);
        $this->assertDatabaseHas('event_receipts', ['upstream_event_id' => $upstreamId, 'processed_at' => null]);
        $this->assertDatabaseCount('deliveries', 0);

        $accountAvailable = true;
        $retry = app(EventScanner::class)->scan();
        self::assertSame(1, $retry['deliveries']);
        self::assertNotNull(DB::table('event_receipts')->value('processed_at'));
    }

    public function test_inactive_access_is_resolved_without_delivery(): void
    {
        $this->subscriber((string) Str::ulid());
        [, $upstreamId] = $this->event();
        Http::fake(['*' => Http::response(['data' => ['news' => ['access_allowed' => false]]])]);

        app(EventScanner::class)->scan();

        $this->assertDatabaseCount('deliveries', 0);
        $this->assertDatabaseHas('event_receipts', ['upstream_event_id' => $upstreamId]);
        self::assertNotNull(DB::table('event_receipts')->value('processed_at'));
    }

    public function test_matcher_filters_category_tag_severity_and_channel_activation_time(): void
    {
        $subscriber = $this->subscriber((string) Str::ulid(), category: 'energy', tag: 'fed');
        $subscriber->channels()->update(['enabled_from' => $this->now]);
        $this->event(category: 'macro_data', tags: ['fed'], severity: 'B');
        Http::fake(['*' => Http::response(['data' => ['news' => ['access_allowed' => true]]])]);

        app(EventScanner::class)->scan();

        $this->assertDatabaseCount('deliveries', 0);
        Http::assertNothingSent();
    }

    public function test_dry_run_counts_matches_without_writing_runtime_or_ledger(): void
    {
        RuntimeState::query()->delete();
        config(['notification.dry_run' => true]);
        $this->subscriber((string) Str::ulid());
        $this->event(receivedAt: $this->now->subMinutes(5));
        Http::fake(['*' => Http::response(['data' => ['news' => ['access_allowed' => true]]])]);

        $result = app(EventScanner::class)->scan();

        self::assertSame(1, $result['deliveries']);
        self::assertTrue($result['dry_run']);
        $this->assertDatabaseCount('deliveries', 0);
        $this->assertDatabaseCount('event_receipts', 0);
        $this->assertDatabaseCount('runtime_state', 0);
    }

    private function subscriber(string $userId, string $category = 'macro_data', ?string $tag = null): Subscriber
    {
        $subscriber = Subscriber::query()->create([
            'account_user_id' => $userId,
            'master_enabled' => true,
            'match_all_categories' => false,
            'min_severity' => 'A',
            'content_language' => 'zh-Hant',
            'revision' => 1,
            'effective_from' => $this->now->subMinutes(9),
        ]);
        $subscriber->categories()->create(['key' => $category]);
        if ($tag !== null) {
            $subscriber->tags()->create(['key' => $tag]);
        }
        $subscriber->channels()->create([
            'type' => 'telegram',
            'enabled' => true,
            'verified' => true,
            'revision' => 1,
            'enabled_from' => $this->now->subMinutes(9),
        ]);

        return $subscriber;
    }

    /** @param list<string> $tags @return array{string, string} */
    private function event(
        string $category = 'macro_data',
        array $tags = ['fed'],
        string $severity = 'A',
        ?CarbonImmutable $receivedAt = null,
    ): array {
        $id = (string) Str::uuid();
        $upstreamId = (string) Str::uuid();
        $receivedAt ??= $this->now->subMinute();
        DB::table('public_events')->insert([
            'id' => $id,
            'upstream_event_id' => $upstreamId,
            'received_at' => $receivedAt,
            'event_time' => $receivedAt,
            'generated_at' => $receivedAt,
            'severity' => $severity,
            'content_category' => $category,
            'topic_tags' => json_encode($tags),
            'is_visible' => true,
        ]);
        DB::table('public_events_translations')->insert([
            'id' => (string) Str::uuid(),
            'public_event_id' => $id,
            'language' => 'zh-Hant',
            'summary' => '測試摘要',
        ]);

        return [$id, $upstreamId];
    }

    private function createPublicTables(): void
    {
        Schema::create('public_subscription_categories', fn (Blueprint $table) => $table->string('key')->primary());
        Schema::create('public_subscription_tags', fn (Blueprint $table) => $table->string('key')->primary());
        DB::table('public_subscription_categories')->insert([['key' => 'energy'], ['key' => 'macro_data']]);
        DB::table('public_subscription_tags')->insert([['key' => 'ecb'], ['key' => 'fed']]);

        Schema::create('public_events', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('upstream_event_id');
            $table->timestampTz('received_at');
            $table->timestampTz('event_time')->nullable();
            $table->timestampTz('generated_at')->nullable();
            $table->string('severity', 1);
            $table->string('content_category')->nullable();
            $table->text('topic_tags');
            $table->boolean('is_visible');
        });
        Schema::create('public_events_translations', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('public_event_id');
            $table->string('language');
            $table->text('summary')->nullable();
        });
    }
}
