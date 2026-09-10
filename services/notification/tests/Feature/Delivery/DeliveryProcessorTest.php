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

    private function delivery(
        string $severity = 'A',
        string $summaryLanguage = 'zh-Hant',
        ?CarbonImmutable $receivedAt = null,
        string $chatId = '123456789',
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
            'type' => 'telegram',
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
            'channel_type' => 'telegram',
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
