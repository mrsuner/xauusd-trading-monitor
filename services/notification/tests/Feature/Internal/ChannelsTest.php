<?php

namespace Tests\Feature\Internal;

use App\Models\Channel;
use App\Models\Subscriber;
use App\Services\Channels\ChannelService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class ChannelsTest extends TestCase
{
    use RefreshDatabase;

    private string $userId;

    protected function setUp(): void
    {
        parent::setUp();

        config([
            'services.notification_internal.secret' => 'test-internal-secret',
            'notification.channel_fingerprint_key' => 'test-fingerprint-key',
            'notification.telegram.bot_username' => 'TickbaseNewsTestBot',
        ]);
        $this->userId = (string) Str::ulid();
    }

    public function test_paid_user_can_create_and_consume_single_use_link_without_storing_plaintext(): void
    {
        $response = $this->internal('POST', 'channels/telegram/link', [], true)
            ->assertCreated()
            ->assertJsonPath('data.expires_at', fn (mixed $value): bool => is_string($value));
        $deepLink = (string) $response->json('data.deep_link');
        parse_str((string) parse_url($deepLink, PHP_URL_QUERY), $query);
        $code = (string) ($query['start'] ?? '');

        self::assertSame(43, strlen($code));
        $channel = Channel::query()->firstOrFail();
        self::assertSame(hash('sha256', $code), $channel->link_code_hash);
        self::assertStringNotContainsString($code, (string) $channel->toJson());

        self::assertTrue(app(ChannelService::class)->consumeTelegramLink($code, '123456789'));
        self::assertFalse(app(ChannelService::class)->consumeTelegramLink($code, '123456789'));

        $channel->refresh();
        self::assertTrue($channel->verified);
        self::assertFalse($channel->enabled);
        self::assertSame('123456789', Crypt::decryptString($channel->encrypted_target));
        self::assertSame('***6789', $channel->target_hint);
        self::assertNull($channel->link_code_hash);

        $this->internal('GET', 'channels', [], false)
            ->assertOk()
            ->assertJsonPath('data.0.target_hint', '***6789')
            ->assertJsonMissing(['encrypted_target' => $channel->encrypted_target])
            ->assertJsonMissing(['target' => '123456789']);
    }

    public function test_link_requires_paid_access_and_configuration(): void
    {
        $this->internal('POST', 'channels/telegram/link', [], false)
            ->assertForbidden()->assertJsonPath('error', 'upgrade_required');

        config(['notification.telegram.bot_username' => null]);
        $this->internal('POST', 'channels/telegram/link', [], true)
            ->assertStatus(503)->assertJsonPath('error', 'service_unavailable');
    }

    public function test_link_creation_is_rate_limited_and_verified_channel_requires_delete_before_relink(): void
    {
        for ($attempt = 0; $attempt < 5; $attempt++) {
            $this->internal('POST', 'channels/telegram/link', [], true)->assertCreated();
        }
        $this->internal('POST', 'channels/telegram/link', [], true)
            ->assertStatus(429)->assertJsonPath('error', 'rate_limited');

        $otherUser = (string) Str::ulid();
        $response = $this->internalFor($otherUser, 'POST', 'channels/telegram/link', [], true)->assertCreated();
        parse_str((string) parse_url((string) $response->json('data.deep_link'), PHP_URL_QUERY), $query);
        app(ChannelService::class)->consumeTelegramLink((string) $query['start'], '987654321');

        $this->internalFor($otherUser, 'POST', 'channels/telegram/link', [], true)
            ->assertStatus(409)->assertJsonPath('error', 'channel_already_linked');
    }

    public function test_enable_requires_verification_but_disable_and_unlink_do_not_require_paid_access(): void
    {
        $this->internal('POST', 'channels/telegram/link', [], true)->assertCreated();
        $this->internal('PATCH', 'channels/telegram', ['enabled' => true], true)
            ->assertStatus(409)->assertJsonPath('error', 'channel_unverified');

        $channel = Channel::query()->firstOrFail();
        $channel->update([
            'verified' => true,
            'encrypted_target' => Crypt::encryptString('123456789'),
            'target_fingerprint' => hash_hmac('sha256', '123456789', 'test-fingerprint-key'),
            'target_hint' => '***6789',
            'linked_at' => now('UTC'),
            'link_code_hash' => null,
            'link_expires_at' => null,
        ]);

        $this->internal('PATCH', 'channels/telegram', ['enabled' => true], true)
            ->assertOk()->assertJsonPath('data.enabled', true);

        $this->internal('PATCH', 'channels/telegram', ['enabled' => false], false)
            ->assertOk()->assertJsonPath('data.enabled', false);

        $this->internal('DELETE', 'channels/telegram', [], false)->assertNoContent();
        $this->internal('DELETE', 'channels/telegram', [], false)->assertNoContent();

        $channel->refresh();
        self::assertFalse($channel->verified);
        self::assertNull($channel->encrypted_target);
        self::assertNull($channel->target_fingerprint);
    }

    public function test_unlink_cancels_nonterminal_delivery_without_deleting_history(): void
    {
        $subscriber = $this->subscriber();
        $channel = $subscriber->channels()->create([
            'type' => 'telegram',
            'enabled' => true,
            'verified' => true,
            'revision' => 2,
            'encrypted_target' => Crypt::encryptString('123456789'),
            'target_fingerprint' => hash_hmac('sha256', '123456789', 'test-fingerprint-key'),
            'target_hint' => '***6789',
            'linked_at' => now('UTC'),
        ]);
        $deliveryId = (string) Str::uuid();
        DB::table('deliveries')->insert([
            'id' => $deliveryId,
            'subscriber_id' => $subscriber->id,
            'channel_id' => $channel->id,
            'upstream_event_id' => (string) Str::uuid(),
            'public_event_id' => (string) Str::uuid(),
            'channel_type' => 'telegram',
            'subscriber_revision' => 1,
            'channel_revision' => 2,
            'status' => 'pending',
            'attempt_count' => 0,
            'not_before' => now('UTC'),
            'expires_at' => now('UTC')->addHour(),
            'created_at' => now('UTC'),
            'updated_at' => now('UTC'),
        ]);

        $this->internal('DELETE', 'channels/telegram', [], false)->assertNoContent();

        $this->assertDatabaseHas('deliveries', [
            'id' => $deliveryId,
            'status' => 'canceled',
            'error_code' => 'channel_unlinked',
        ]);
    }

    private function subscriber(): Subscriber
    {
        return Subscriber::query()->create([
            'account_user_id' => $this->userId,
            'master_enabled' => false,
            'match_all_categories' => false,
            'min_severity' => 'A',
            'content_language' => 'zh-Hant',
            'revision' => 1,
            'effective_from' => now('UTC'),
        ]);
    }

    /** @param array<string, mixed> $payload */
    private function internal(string $method, string $path, array $payload, bool $active): TestResponse
    {
        return $this->internalFor($this->userId, $method, $path, $payload, $active);
    }

    /** @param array<string, mixed> $payload */
    private function internalFor(string $userId, string $method, string $path, array $payload, bool $active): TestResponse
    {
        return $this->withHeaders([
            'X-Internal-Secret' => 'test-internal-secret',
            'X-News-Access' => $active ? 'active' : 'inactive',
        ])->json($method, "/internal/users/{$userId}/{$path}", $payload);
    }
}
