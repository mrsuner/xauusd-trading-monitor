<?php

namespace Tests\Feature\Digests;

use App\Jobs\SendDigestBatch;
use App\Models\DigestBatch;
use App\Models\DigestEdition;
use App\Models\Subscriber;
use App\Services\Digests\DigestBatchCoordinator;
use App\Services\Digests\DigestBatchProcessor;
use App\Services\Digests\DigestMaintenance;
use Carbon\CarbonImmutable;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Tests\TestCase;

class DigestDeliveryTest extends TestCase
{
    use RefreshDatabase;

    private CarbonImmutable $now;

    protected function setUp(): void
    {
        parent::setUp();
        $this->now = CarbonImmutable::parse('2026-09-11T00:30:00Z');
        CarbonImmutable::setTestNow($this->now);
        Cache::flush();
        config([
            'notification.account.base_url' => 'http://account:8080',
            'notification.account.secret' => 'account-secret',
            'notification.telegram.bot_token' => 'bot-token',
            'notification.public_origin' => 'https://news.thetickbase.com',
        ]);
        Schema::create('public_events', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->timestampTz('invalidated_at')->nullable();
            $table->string('invalidation_kind')->nullable();
            $table->string('invalidation_reason')->nullable();
        });
    }

    protected function tearDown(): void
    {
        CarbonImmutable::setTestNow();
        parent::tearDown();
    }

    public function test_coordinator_creates_one_early_batch_when_selected_topics_are_terminal(): void
    {
        Queue::fake();
        $subscriber = $this->subscriber(['energy', 'monetary']);
        $energy = $this->edition('energy', 'published');
        $energy->translations()->create($this->translation('Energy daily'));
        $this->edition('monetary', 'no_content');

        $this->assertSame(1, app(DigestBatchCoordinator::class)->scan($this->now));
        $batch = DigestBatch::query()->firstOrFail();
        $this->assertSame('pending', $batch->status);
        $this->assertNull($batch->error_code);
        $this->assertSame($subscriber->id, $batch->subscriber_id);
        $this->assertSame([$energy->id], $batch->editions()->pluck('digest_editions.id')->all());
        Queue::assertPushed(SendDigestBatch::class, 1);
        $this->assertSame(0, app(DigestBatchCoordinator::class)->scan($this->now));
    }

    public function test_deadline_builds_partial_batch_and_processor_sends_one_protected_link(): void
    {
        Queue::fake();
        $this->subscriber(['energy', 'monetary']);
        $energy = $this->edition('energy', 'published');
        $energy->translations()->create($this->translation('Energy daily'));
        Http::fake([
            'http://account:8080/*' => Http::response(['data' => ['news' => ['access_allowed' => true]]]),
            'https://api.telegram.org/*' => Http::response(['ok' => true, 'result' => ['message_id' => 44]]),
        ]);

        $deadline = $this->now->addMinutes(30);
        $this->assertSame(1, app(DigestBatchCoordinator::class)->scan($deadline));
        $batch = DigestBatch::query()->firstOrFail();
        $this->assertSame('partial_coverage', $batch->error_code);
        CarbonImmutable::setTestNow($deadline);
        $this->assertNull(app(DigestBatchProcessor::class)->process($batch->id));
        $this->assertSame('sent', $batch->fresh()->status);
        Http::assertSent(fn (Request $request): bool => ! str_ends_with($request->url(), '/sendMessage')
            || (str_contains((string) $request->data()['text'], "/zh-Hant/digests/{$energy->id}")
                && str_contains((string) $request->data()['text'], '部分所選主題未能')));
    }

    public function test_withdrawal_invalidates_edition_and_keeps_unaffected_section_pending(): void
    {
        Queue::fake();
        $subscriber = $this->subscriber(['energy', 'monetary']);
        $energy = $this->edition('energy', 'published');
        $energy->translations()->create($this->translation('Energy'));
        $monetary = $this->edition('monetary', 'published');
        $monetary->translations()->create($this->translation('Monetary'));
        $batch = $this->batch($subscriber, [$energy, $monetary]);
        $eventId = (string) Str::uuid();
        $energy->events()->create([
            'public_event_id' => $eventId, 'upstream_event_id' => (string) Str::uuid(), 'position' => 1,
        ]);
        DB::table('public_events')->insert([
            'id' => $eventId, 'invalidated_at' => $this->now,
            'invalidation_kind' => 'withdrawal', 'invalidation_reason' => 'Source withdrawal',
        ]);

        $result = app(DigestMaintenance::class)->run($this->now);

        $this->assertSame(1, $result['invalidated']);
        $this->assertSame('invalidated', $energy->fresh()->status);
        $this->assertSame('pending', $batch->fresh()->status);
        $this->assertSame('partial_coverage', $batch->fresh()->error_code);
        $this->assertSame([$monetary->id], $batch->editions()->pluck('digest_editions.id')->all());
    }

    private function subscriber(array $topics): Subscriber
    {
        $subscriber = Subscriber::query()->create([
            'account_user_id' => (string) Str::ulid(), 'master_enabled' => false,
            'match_all_categories' => false, 'min_severity' => 'A', 'content_language' => 'zh-Hant',
            'revision' => 1, 'effective_from' => $this->now->subDay(),
        ]);
        $preference = $subscriber->digestPreference()->create([
            'enabled' => true, 'revision' => 1, 'effective_from' => $this->now->subDay(),
        ]);
        $preference->topics()->createMany(array_map(fn (string $topic): array => ['topic' => $topic], $topics));
        $subscriber->channels()->create([
            'type' => 'telegram', 'enabled' => true, 'verified' => true, 'revision' => 1,
            'enabled_from' => $this->now->subDay(), 'encrypted_target' => Crypt::encryptString('123456789'),
            'target_fingerprint' => hash('sha256', '123456789'), 'linked_at' => $this->now->subDay(),
        ]);

        return $subscriber;
    }

    private function edition(string $topic, string $status): DigestEdition
    {
        return DigestEdition::query()->create([
            'topic' => $topic, 'window_start' => $this->now->startOfDay()->subDay(),
            'window_end' => $this->now->startOfDay(), 'cutoff_at' => $this->now->startOfDay()->addMinutes(15),
            'deadline_at' => $this->now->startOfDay()->addHour(), 'status' => $status,
            'input_count' => 0, 'coverage_truncated' => false,
            'published_at' => $status === 'published' ? $this->now : null,
        ]);
    }

    private function translation(string $title): array
    {
        return [
            'language' => 'zh-Hant', 'title' => $title, 'overview' => '摘要',
            'developments' => [['text' => '進展', 'event_ids' => [(string) Str::uuid()]]],
            'source_content_hash' => str_repeat('a', 64),
        ];
    }

    private function batch(Subscriber $subscriber, array $editions): DigestBatch
    {
        $channel = $subscriber->channels()->firstOrFail();
        $batch = DigestBatch::query()->create([
            'subscriber_id' => $subscriber->id, 'channel_id' => $channel->id,
            'window_start' => $this->now->startOfDay()->subDay(), 'preference_revision' => 1,
            'channel_revision' => 1, 'content_language' => 'zh-Hant', 'status' => 'pending',
            'attempt_count' => 0, 'not_before' => $this->now, 'deadline_at' => $this->now->addMinutes(30),
        ]);
        $batch->editions()->sync(collect($editions)->pluck('id')->all());

        return $batch;
    }
}
