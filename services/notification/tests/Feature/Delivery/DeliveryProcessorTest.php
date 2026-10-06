<?php

namespace Tests\Feature\Delivery;

use App\Enums\DeliveryStatus;
use App\Models\Delivery;
use App\Models\Subscriber;
use App\Services\Delivery\DeliveryProcessor;
use Carbon\CarbonImmutable;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Tests\TestCase;

class DeliveryProcessorTest extends TestCase
{
    use RefreshDatabase;

    private CarbonImmutable $now;

    private int $dedupRequests = 0;

    protected function setUp(): void
    {
        parent::setUp();
        $this->now = CarbonImmutable::parse('2026-09-11T12:00:00Z');
        CarbonImmutable::setTestNow($this->now);
        Cache::flush();
        config([
            'notification.account.base_url' => 'http://account:8080',
            'notification.account.secret' => 'account-secret',
            'notification.telegram.bot_token' => 'bot-secret-token',
            'notification.channel_fingerprint_key' => 'test-fingerprint-key',
            'notification.public_origin' => 'https://news.thetickbase.com',
        ]);
        $this->createPublicTables();
    }

    protected function tearDown(): void
    {
        CarbonImmutable::setTestNow();
        parent::tearDown();
    }

    public function test_ready_paid_delivery_is_sent_once_as_plain_text(): void
    {
        $delivery = $this->delivery();
        Http::fake([
            'http://account:8080/*' => Http::response(['data' => ['news' => ['access_allowed' => true]]]),
            'https://api.telegram.org/*' => Http::response(['ok' => true, 'result' => ['message_id' => 321]]),
        ]);

        self::assertNull(app(DeliveryProcessor::class)->process($delivery->id));

        $delivery->refresh();
        self::assertSame(DeliveryStatus::Sent, $delivery->status);
        self::assertSame(1, $delivery->attempt_count);
        self::assertSame('321', $delivery->provider_message_id);
        Http::assertSent(function (Request $request): bool {
            if (! str_ends_with($request->url(), '/sendMessage')) {
                return true;
            }
            $text = (string) $request->data()['text'];

            return $request->data()['chat_id'] === '123456789'
                && ! array_key_exists('parse_mode', $request->data())
                && str_contains($text, '即時新聞')
                && str_contains($text, '測試摘要')
                && str_contains($text, 'https://news.thetickbase.com/events/');
        });

        app(DeliveryProcessor::class)->process($delivery->id);
        Http::assertSentCount(2);
    }

    public function test_push_delivery_uses_account_dispatch_and_marks_provider_acceptance(): void
    {
        $delivery = $this->delivery(channelType: 'push');
        Http::fake([
            'http://account:8080/internal/news/users/*/access' => Http::response(['data' => ['news' => ['access_allowed' => true]]]),
            'http://account:8080/internal/news/users/*/push' => Http::response(['data' => ['accepted' => true]], 202),
        ]);

        self::assertNull(app(DeliveryProcessor::class)->process($delivery->id));
        self::assertSame(DeliveryStatus::Sent, $delivery->fresh()->status);
        Http::assertSent(fn (Request $request): bool => str_ends_with($request->url(), '/push')
            && $request->data()['delivery_id'] === $delivery->id
            && $request->data()['event_id'] === $delivery->public_event_id
            && str_contains($request->data()['url'], '/zh-Hant/events/'.$delivery->public_event_id)
            && $request->hasHeader('X-Internal-Secret', 'account-secret'));
        $this->assertDatabaseMissing('runtime_state', ['key' => 'telegram_last_send']);
    }

    public function test_push_without_registered_browser_is_canceled(): void
    {
        $delivery = $this->delivery(channelType: 'push');
        Http::fake([
            'http://account:8080/internal/news/users/*/access' => Http::response(['data' => ['news' => ['access_allowed' => true]]]),
            'http://account:8080/internal/news/users/*/push' => Http::response(['error' => 'no_web_devices'], 409),
        ]);

        self::assertNull(app(DeliveryProcessor::class)->process($delivery->id));
        self::assertSame(DeliveryStatus::Canceled, $delivery->fresh()->status);
        self::assertSame('no_web_devices', $delivery->fresh()->error_code);
    }

    public function test_unknown_access_waits_without_provider_attempt(): void
    {
        $delivery = $this->delivery();
        Http::fake(['http://account:8080/*' => Http::response(['error' => 'offline'], 503)]);

        self::assertSame(60, app(DeliveryProcessor::class)->process($delivery->id));

        $delivery->refresh();
        self::assertSame(DeliveryStatus::Retry, $delivery->status);
        self::assertSame(0, $delivery->attempt_count);
        self::assertSame('account_unavailable', $delivery->error_code);
        Http::assertSentCount(1);
    }

    public function test_inactive_access_and_changed_revision_cancel_before_provider(): void
    {
        $delivery = $this->delivery();
        $this->fakeAccount(false);
        self::assertNull(app(DeliveryProcessor::class)->process($delivery->id));
        self::assertSame(DeliveryStatus::Canceled, $delivery->fresh()->status);

        Cache::flush();
        $other = $this->delivery(chatId: '987654321');
        $other->subscriber->increment('revision');
        $this->fakeAccount(true);
        self::assertNull(app(DeliveryProcessor::class)->process($other->id));
        self::assertSame('configuration_changed', $other->fresh()->error_code);
        Http::assertNotSent(fn (Request $request): bool => str_ends_with($request->url(), '/sendMessage'));
    }

    public function test_a_waits_two_minutes_then_sends_english_fallback_with_notice(): void
    {
        $delivery = $this->delivery(severity: 'A', summaryLanguage: 'en', receivedAt: $this->now->subMinute());
        $this->fakeAccount(true, telegramAccepted: true);

        self::assertSame(60, app(DeliveryProcessor::class)->process($delivery->id));
        self::assertSame(0, $delivery->fresh()->attempt_count);

        CarbonImmutable::setTestNow($this->now->addMinute());
        self::assertNull(app(DeliveryProcessor::class)->process($delivery->id));
        self::assertSame(DeliveryStatus::Sent, $delivery->fresh()->status);
        Http::assertSent(fn (Request $request): bool => ! str_ends_with($request->url(), '/sendMessage')
            || str_contains((string) $request->data()['text'], '翻譯暫時無法使用（內容語言：en）'));
    }

    public function test_429_sets_durable_cooldown_and_does_not_hide_attempt(): void
    {
        $delivery = $this->delivery();
        Http::fake([
            'http://account:8080/*' => Http::response(['data' => ['news' => ['access_allowed' => true]]]),
            'https://api.telegram.org/*' => Http::response([
                'ok' => false,
                'description' => 'Too Many Requests',
                'parameters' => ['retry_after' => 7],
            ], 429),
        ]);

        self::assertSame(7, app(DeliveryProcessor::class)->process($delivery->id));
        $delivery->refresh();
        self::assertSame(1, $delivery->attempt_count);
        self::assertSame('provider_429', $delivery->error_code);
        $this->assertDatabaseHas('runtime_state', ['key' => 'telegram_provider']);
    }

    public function test_network_failure_uses_bounded_retry_and_blocked_target_disables_channel(): void
    {
        $delivery = $this->delivery();
        $providerMode = 'timeout';
        Http::fake(function (Request $request) use (&$providerMode) {
            if (str_ends_with($request->url(), '/sendMessage')) {
                if ($providerMode === 'blocked') {
                    return Http::response(['ok' => false, 'description' => 'Forbidden: bot was blocked'], 403);
                }
                throw new ConnectionException('timeout');
            }

            return Http::response(['data' => ['news' => ['access_allowed' => true]]]);
        });

        $delay = app(DeliveryProcessor::class)->process($delivery->id);
        self::assertGreaterThanOrEqual(30, $delay);
        self::assertLessThanOrEqual(36, $delay);
        self::assertSame('provider_transient', $delivery->fresh()->error_code);

        Cache::flush();
        CarbonImmutable::setTestNow($this->now->addMinutes(10));
        $blocked = $this->delivery(chatId: '987654321');
        $providerMode = 'blocked';
        self::assertNull(app(DeliveryProcessor::class)->process($blocked->id));
        self::assertSame(DeliveryStatus::Failed, $blocked->fresh()->status);
        self::assertFalse($blocked->channel->fresh()->enabled);
    }

    public function test_expired_delivery_never_checks_account_or_provider(): void
    {
        $delivery = $this->delivery();
        $delivery->update(['expires_at' => $this->now]);
        Http::fake();

        self::assertNull(app(DeliveryProcessor::class)->process($delivery->id));
        self::assertSame(DeliveryStatus::Expired, $delivery->fresh()->status);
        Http::assertNothingSent();
    }

    private function fakeAccount(bool $active, bool $telegramAccepted = false): void
    {
        $responses = [
            'http://account:8080/*' => Http::response(['data' => ['news' => ['access_allowed' => $active]]]),
        ];
        if ($telegramAccepted) {
            $responses['https://api.telegram.org/*'] = Http::response(['ok' => true, 'result' => ['message_id' => 1]]);
        }
        Http::fake($responses);
    }

    public function test_cross_source_duplicate_cancels_only_after_an_actual_delivery(): void
    {
        [$reference, $current] = $this->duplicatePair();
        $this->fakeDedup();
        self::assertNull(app(DeliveryProcessor::class)->process($current->id));
        self::assertSame(DeliveryStatus::Canceled, $current->fresh()->status);
        self::assertSame('cross_source_duplicate:'.$reference->id, $current->fresh()->error_code);
        self::assertSame(0, $current->fresh()->attempt_count);
        Http::assertNotSent(fn (Request $request): bool => str_ends_with($request->url(), '/sendMessage'));
        Http::assertSent(fn (Request $request): bool => $request->url() === 'https://openrouter.ai/api/alpha/decisions'
            && $request->data()['model'] === 'typesafe/jev-1.13'
            && ! isset($request->data()['state']['current']['source_name']));
    }

    public function test_public_snapshot_replay_uses_recorded_decisions_without_external_sends(): void
    {
        // Real report text/timestamps; only the recipient ledger and API transport
        // are synthetic. Reused provisional labels are not independent acceptance.
        $packet = json_decode(file_get_contents(__DIR__.'/../../Fixtures/news-dedup-snapshot-replay.json'), true, flags: JSON_THROW_ON_ERROR);
        self::assertCount(20, $packet['pairs']);
        $this->now = CarbonImmutable::parse('2026-09-22T12:00:00Z');
        CarbonImmutable::setTestNow($this->now);
        [$reference, $current] = $this->duplicatePair();
        Http::preventStrayRequests();
        $counts = ['pairs' => 0, 'canceled' => 0, 'sent_fake' => 0, 'recorded_model_responses_used' => 0];
        $pair = null;
        $modelCalls = 0;
        $telegramCalls = 0;
        Http::fake(function (Request $request) use (&$pair, &$modelCalls, &$telegramCalls) {
            if ($request->url() === 'https://openrouter.ai/api/alpha/decisions') {
                $modelCalls++;
                self::assertSame($pair['current']['content'], $request->data()['state']['current']['content']);
                self::assertSame($pair['candidate']['content'], $request->data()['state']['candidate']['content']);
                self::assertArrayNotHasKey('english_content', $request->data()['state']['current']);

                return Http::response(['model' => $pair['recorded']['model'], 'usage' => $pair['recorded']['usage'],
                    'answers' => ['relationship' => $pair['recorded']['decision']]]);
            }
            if (str_ends_with($request->url(), '/sendMessage')) {
                $telegramCalls++;

                return Http::response(['ok' => true, 'result' => ['message_id' => 1]]);
            }
            self::assertStringStartsWith('http://account:8080/', $request->url());

            return Http::response(['data' => ['news' => ['access_allowed' => true]]]);
        });
        foreach ($packet['pairs'] as $pair) {
            Cache::flush();
            $modelCalls = 0;
            $telegramCalls = 0;
            $current->refresh()->update(['status' => 'pending', 'attempt_count' => 0, 'sent_at' => null,
                'provider_message_id' => null, 'error_code' => null]);
            foreach ([[$reference, $pair['candidate']], [$current, $pair['current']]] as [$delivery, $report]) {
                DB::table('public_raw_items')->whereJsonContains('upstream_event_ids', $delivery->upstream_event_id)
                    ->update(['title' => $report['title'], 'original_content' => $report['content'],
                        'source_name' => $report['source_name'], 'published_at' => CarbonImmutable::parse($report['published_at'])]);
            }
            self::assertNull(app(DeliveryProcessor::class)->process($current->id), $pair['id']);
            self::assertLessThanOrEqual(1, $modelCalls, $pair['id']);
            $counts['pairs']++;
            $counts['recorded_model_responses_used'] += $modelCalls;
            if ($current->fresh()->status === DeliveryStatus::Canceled) {
                self::assertSame('duplicate', $pair['expected'], $pair['id']);
                self::assertSame('cross_source_duplicate:'.$reference->id, $current->fresh()->error_code);
                self::assertSame(0, $current->fresh()->attempt_count);
                self::assertSame(0, $telegramCalls);
                $counts['canceled']++;
            } else {
                self::assertSame(DeliveryStatus::Sent, $current->fresh()->status, $pair['id']);
                self::assertSame(1, $telegramCalls);
                $counts['sent_fake']++;
            }
        }
        self::assertGreaterThan(0, $counts['canceled']);
        self::assertGreaterThan(0, $counts['sent_fake']);
        fwrite(STDOUT, "\nSnapshot delivery replay: ".json_encode($counts, JSON_THROW_ON_ERROR)."\n");
    }

    public function test_dedup_timeout_fails_open_without_retrying_model(): void
    {
        [, $current] = $this->duplicatePair();
        $this->fakeDedup(timeout: true);
        self::assertNull(app(DeliveryProcessor::class)->process($current->id));
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(1, $this->dedupRequests);
        Http::assertSentCount(2);
    }

    public function test_changed_figures_are_sent_without_a_model_call(): void
    {
        [, $current] = $this->duplicatePair();
        DB::table('public_raw_items')->whereJsonContains('upstream_event_ids', $current->upstream_event_id)
            ->update(['original_content' => 'Fed holds rates at 3.5%.']);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        Http::assertNotSent(fn (Request $request): bool => str_contains($request->url(), 'openrouter.ai'));
    }

    public function test_unsent_reference_cannot_suppress_a_message(): void
    {
        [$reference, $current] = $this->duplicatePair();
        $reference->update(['status' => 'failed', 'sent_at' => null]);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        Http::assertNotSent(fn (Request $request): bool => str_contains($request->url(), 'openrouter.ai'));
    }

    public function test_other_recipient_does_not_suppress(): void
    {
        [$reference, $current] = $this->duplicatePair(sameRecipient: false);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        Http::assertNotSent(fn (Request $request): bool => str_contains($request->url(), 'openrouter.ai'));
    }

    public function test_invalid_answer_fails_open(): void
    {
        [, $current] = $this->duplicatePair();
        $this->fakeDedup(invalid: true);
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(1, $this->dedupRequests);
    }

    public function test_edited_reference_is_not_used_to_suppress(): void
    {
        [$reference, $current] = $this->duplicatePair();
        DB::table('public_raw_items')->whereJsonContains('upstream_event_ids', $reference->upstream_event_id)
            ->update(['updated_at' => $this->now]);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(0, $this->dedupRequests);
    }

    public function test_ambiguous_original_is_not_used_to_suppress(): void
    {
        [, $current] = $this->duplicatePair();
        $row = (array) DB::table('public_raw_items')->whereJsonContains('upstream_event_ids', $current->upstream_event_id)->first();
        $row['id'] = (string) Str::uuid();
        DB::table('public_raw_items')->insert($row);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(0, $this->dedupRequests);
    }

    public function test_missing_original_is_sent(): void
    {
        [, $current] = $this->duplicatePair();
        DB::table('public_raw_items')->whereJsonContains('upstream_event_ids', $current->upstream_event_id)->delete();
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(0, $this->dedupRequests);
    }

    public function test_stale_reference_is_not_used(): void
    {
        [$reference, $current] = $this->duplicatePair();
        $reference->update(['sent_at' => $this->now->subMinutes(31)]);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(0, $this->dedupRequests);
    }

    public function test_delivery_to_an_older_channel_revision_does_not_suppress(): void
    {
        [$reference, $current] = $this->duplicatePair();
        $reference->update(['channel_revision' => 0]);
        $this->fakeDedup();
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(0, $this->dedupRequests);
    }

    public function test_comparisons_are_bounded_to_two_candidates(): void
    {
        [$reference, $current] = $this->duplicatePair();
        foreach ([2, 3] as $index) {
            $previous = $reference->replicate();
            $previous->upstream_event_id = (string) Str::uuid();
            $previous->public_event_id = (string) Str::uuid();
            $previous->save();
            DB::table('public_raw_items')->insert(['id' => (string) Str::uuid(),
                'upstream_event_ids' => json_encode([$previous->upstream_event_id]),
                'source_name' => 'Source '.$index, 'title' => null, 'original_content' => 'Fed holds rates at 3.25%.',
                'published_at' => $this->now->subMinute(), 'updated_at' => $this->now->subMinutes(2),
                'is_visible' => true, 'is_truncated' => false]);
        }
        config(['notification.dedup.candidates' => 100]);
        $this->fakeDedup(unrelated: true);
        app(DeliveryProcessor::class)->process($current->id);
        self::assertSame(DeliveryStatus::Sent, $current->fresh()->status);
        self::assertSame(2, $this->dedupRequests);
    }

    /** @return array{Delivery, Delivery} */
    private function duplicatePair(bool $sameRecipient = true): array
    {
        config(['notification.dedup.enabled' => true,
            'notification.dedup.endpoint' => 'https://openrouter.ai/api/alpha/decisions',
            'notification.dedup.api_key' => 'test-only', 'notification.dedup.model' => 'typesafe/jev-1.13']);
        Schema::create('public_raw_items', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->text('upstream_event_ids');
            $table->string('source_name');
            $table->string('title')->nullable();
            $table->text('original_content')->nullable();
            $table->timestamp('published_at');
            $table->timestamp('updated_at');
            $table->boolean('is_visible');
            $table->boolean('is_truncated');
        });
        $reference = $this->delivery();
        $reference->update(['status' => 'sent', 'sent_at' => $this->now->subMinute()]);
        $current = $this->delivery(chatId: '987654321');
        if ($sameRecipient) {
            $current->update(['subscriber_id' => $reference->subscriber_id, 'channel_id' => $reference->channel_id]);
        }
        foreach ([$reference, $current] as $index => $delivery) {
            DB::table('public_raw_items')->insert(['id' => (string) Str::uuid(),
                'upstream_event_ids' => json_encode([$delivery->upstream_event_id]),
                'source_name' => 'Source '.$index, 'title' => null,
                'original_content' => 'Fed holds rates at 3.25%.', 'published_at' => $this->now->subMinute(),
                'updated_at' => $this->now->subMinutes(2),
                'is_visible' => true, 'is_truncated' => false]);
        }

        return [$reference, $current];
    }

    private function fakeDedup(bool $timeout = false, bool $invalid = false, bool $unrelated = false): void
    {
        Http::fake(function (Request $request) use ($timeout, $invalid, $unrelated) {
            if (str_contains($request->url(), 'openrouter.ai')) {
                $this->dedupRequests++;
                if ($timeout) {
                    throw new ConnectionException('simulated timeout');
                }

                return Http::response(['model' => 'typesafe/jev-1.13-version', 'usage' => ['cost' => 0.00003],
                    'answers' => ['relationship' => ['type' => 'choice', 'choice' => $unrelated ? 'unrelated' : 'duplicate', 'confidence' => $invalid ? null : 0.99,
                        'probabilities' => ['duplicate' => $unrelated ? 0 : 0.99, 'material_update' => 0.01, 'unrelated' => $unrelated ? 0.99 : 0, 'insufficient_evidence' => 0]]]]);
            }
            if (str_ends_with($request->url(), '/sendMessage')) {
                return Http::response(['ok' => true, 'result' => ['message_id' => 1]]);
            }

            return Http::response(['data' => ['news' => ['access_allowed' => true]]]);
        });
    }

    private function delivery(
        string $severity = 'A',
        string $summaryLanguage = 'zh-Hant',
        ?CarbonImmutable $receivedAt = null,
        string $chatId = '123456789',
        string $channelType = 'telegram',
    ): Delivery {
        $receivedAt ??= $this->now->subMinute();
        $eventId = (string) Str::uuid();
        $upstreamId = (string) Str::uuid();
        DB::table('public_events')->insert([
            'id' => $eventId,
            'upstream_event_id' => $upstreamId,
            'received_at' => $receivedAt,
            'event_time' => $receivedAt,
            'generated_at' => $receivedAt,
            'severity' => $severity,
            'content_category' => 'macro_data',
            'topic_tags' => json_encode(['fed']),
            'is_visible' => true,
        ]);
        DB::table('public_events_translations')->insert([
            'id' => (string) Str::uuid(),
            'public_event_id' => $eventId,
            'language' => $summaryLanguage,
            'summary' => $summaryLanguage === 'en' ? 'English summary' : '測試摘要',
        ]);

        $subscriber = Subscriber::query()->create([
            'account_user_id' => (string) Str::ulid(),
            'master_enabled' => true,
            'match_all_categories' => false,
            'min_severity' => 'A',
            'content_language' => 'zh-Hant',
            'revision' => 1,
            'effective_from' => $receivedAt->subMinute(),
        ]);
        $subscriber->categories()->create(['key' => 'macro_data']);
        $subscriber->tags()->create(['key' => 'fed']);
        $channel = $subscriber->channels()->create([
            'type' => $channelType,
            'enabled' => true,
            'verified' => true,
            'revision' => 1,
            'enabled_from' => $receivedAt->subMinute(),
            'encrypted_target' => Crypt::encryptString($chatId),
            'target_fingerprint' => hash_hmac('sha256', $chatId, 'test-fingerprint-key'),
            'target_hint' => '***'.substr($chatId, -4),
        ]);

        return Delivery::query()->create([
            'subscriber_id' => $subscriber->id,
            'channel_id' => $channel->id,
            'upstream_event_id' => $upstreamId,
            'public_event_id' => $eventId,
            'channel_type' => $channelType,
            'subscriber_revision' => 1,
            'channel_revision' => 1,
            'status' => 'pending',
            'attempt_count' => 0,
            'not_before' => $this->now,
            'expires_at' => $receivedAt->addHour(),
        ]);
    }

    private function createPublicTables(): void
    {
        Schema::create('public_subscription_categories', fn (Blueprint $table) => $table->string('key')->primary());
        Schema::create('public_subscription_tags', fn (Blueprint $table) => $table->string('key')->primary());
        DB::table('public_subscription_categories')->insert(['key' => 'macro_data']);
        DB::table('public_subscription_tags')->insert(['key' => 'fed']);
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
