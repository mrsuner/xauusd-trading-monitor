<?php

namespace Tests\Feature;

use App\Models\Channel;
use App\Models\RuntimeState;
use App\Services\Channels\ChannelService;
use App\Services\Telegram\TelegramUpdateProcessor;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

class TelegramPollerTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config([
            'notification.channel_fingerprint_key' => 'test-fingerprint-key',
            'notification.telegram.bot_token' => 'bot-secret-token',
            'notification.telegram.bot_username' => 'TickbaseNewsTestBot',
        ]);
    }

    public function test_updates_are_ordered_link_once_and_commit_durable_offset(): void
    {
        $code = $this->linkCode((string) Str::ulid());
        $processor = app(TelegramUpdateProcessor::class);

        self::assertSame(2, $processor->process([
            $this->update(11, '/start '.$code, 'private', 123456789),
            $this->update(10, 'ignored', 'private', 123456789),
        ]));
        self::assertSame(12, $processor->nextOffset());
        self::assertSame(12, RuntimeState::query()->findOrFail('telegram_updates')->value['next_offset']);

        $channel = Channel::query()->firstOrFail();
        self::assertTrue($channel->verified);
        self::assertFalse($channel->enabled);
        self::assertNull($channel->link_code_hash);

        self::assertSame(0, $processor->process([$this->update(11, '/start '.$code, 'private', 123456789)]));
    }

    public function test_group_start_is_ignored_and_private_stop_disables_delivery(): void
    {
        $code = $this->linkCode((string) Str::ulid());
        $processor = app(TelegramUpdateProcessor::class);
        $processor->process([$this->update(1, '/start '.$code, 'group', -100123)]);
        self::assertFalse(Channel::query()->firstOrFail()->verified);

        $processor->process([$this->update(2, '/start '.$code, 'private', 123456789)]);
        $channel = Channel::query()->firstOrFail();
        $channel->update(['enabled' => true, 'enabled_from' => now('UTC')]);

        $processor->process([$this->update(3, '/stop please', 'private', 123456789)]);
        self::assertFalse($channel->fresh()->enabled);
        self::assertSame(4, $processor->nextOffset());
    }

    public function test_command_refuses_long_polling_when_webhook_exists(): void
    {
        Http::fake([
            '*getWebhookInfo' => Http::response(['ok' => true, 'result' => ['url' => 'https://example.com/hook']]),
        ]);

        $this->artisan('telegram:poll', ['--once' => true])
            ->expectsOutput('Telegram webhook is configured; refusing to start long polling.')
            ->assertFailed();

        Http::assertSentCount(1);
    }

    public function test_once_command_uses_persisted_offset(): void
    {
        RuntimeState::query()->create(['key' => 'telegram_updates', 'value' => ['next_offset' => 42]]);
        Http::fake(function (Request $request) {
            if (str_ends_with($request->url(), '/getWebhookInfo')) {
                return Http::response(['ok' => true, 'result' => ['url' => '']]);
            }

            return Http::response(['ok' => true, 'result' => []]);
        });

        $this->artisan('telegram:poll', ['--once' => true])->assertSuccessful();

        Http::assertSent(fn (Request $request): bool => str_ends_with($request->url(), '/getUpdates')
            && $request->data()['offset'] === 42
            && $request->data()['timeout'] === 20);
    }

    private function linkCode(string $accountUserId): string
    {
        $link = app(ChannelService::class)->createTelegramLink($accountUserId, true)['deep_link'];
        parse_str((string) parse_url($link, PHP_URL_QUERY), $query);

        return (string) $query['start'];
    }

    /** @return array<string, mixed> */
    private function update(int $id, string $text, string $chatType, int $chatId): array
    {
        return [
            'update_id' => $id,
            'message' => [
                'text' => $text,
                'chat' => ['id' => $chatId, 'type' => $chatType],
            ],
        ];
    }
}
