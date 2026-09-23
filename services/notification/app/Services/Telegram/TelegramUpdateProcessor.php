<?php

namespace App\Services\Telegram;

use App\Exceptions\ChannelException;
use App\Models\RuntimeState;
use App\Services\Channels\ChannelService;
use Illuminate\Support\Facades\DB;

class TelegramUpdateProcessor
{
    private const STATE_KEY = 'telegram_updates';

    public function __construct(private ChannelService $channels) {}

    public function nextOffset(): int
    {
        return (int) (RuntimeState::query()->find(self::STATE_KEY)?->value['next_offset'] ?? 0);
    }

    /** @param list<array<string, mixed>> $updates */
    public function process(array $updates): int
    {
        usort($updates, fn (array $left, array $right): int => ((int) ($left['update_id'] ?? -1)) <=> ((int) ($right['update_id'] ?? -1)));
        $processed = 0;

        foreach ($updates as $update) {
            $updateId = filter_var($update['update_id'] ?? null, FILTER_VALIDATE_INT);
            if ($updateId === false || $updateId < $this->nextOffset()) {
                continue;
            }

            DB::transaction(function () use ($update, $updateId): void {
                $this->applyMessage($update);
                RuntimeState::query()->updateOrCreate(
                    ['key' => self::STATE_KEY],
                    ['value' => ['next_offset' => $updateId + 1]],
                );
            });
            $processed++;
        }

        return $processed;
    }

    /** @param array<string, mixed> $update */
    private function applyMessage(array $update): void
    {
        $message = $update['message'] ?? null;
        if (! is_array($message) || ($message['chat']['type'] ?? null) !== 'private') {
            return;
        }

        $chatId = $message['chat']['id'] ?? null;
        $text = trim((string) ($message['text'] ?? ''));
        if ((! is_int($chatId) && ! is_string($chatId)) || $text === '') {
            return;
        }

        if (preg_match('/^\/start(?:@\w+)?\s+([A-Za-z0-9_-]{43})$/', $text, $match) === 1) {
            try {
                $this->channels->consumeTelegramLink($match[1], (string) $chatId);
            } catch (ChannelException $exception) {
                if ($exception->httpStatus >= 500) {
                    throw $exception;
                }
            }

            return;
        }

        if (preg_match('/^\/stop(?:@\w+)?(?:\s|$)/', $text) === 1) {
            $this->channels->stopTelegramChat((string) $chatId);
        }
    }
}
