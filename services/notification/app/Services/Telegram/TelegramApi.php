<?php

namespace App\Services\Telegram;

use App\Enums\TelegramResultType;
use App\ValueObjects\TelegramResult;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class TelegramApi
{
    /** @return array<string, mixed> */
    public function webhookInfo(): array
    {
        return $this->request('getWebhookInfo');
    }

    /** @return list<array<string, mixed>> */
    public function updates(int $offset): array
    {
        $result = $this->request('getUpdates', [
            'offset' => $offset,
            'timeout' => 20,
            'allowed_updates' => ['message'],
        ], 25);

        return is_array($result) ? array_values($result) : [];
    }

    public function sendMessage(string $chatId, string $text): TelegramResult
    {
        $token = $this->token();
        try {
            $response = Http::acceptJson()->connectTimeout(3)->timeout(10)
                ->post("https://api.telegram.org/bot{$token}/sendMessage", [
                    'chat_id' => $chatId,
                    'text' => $text,
                    'disable_web_page_preview' => true,
                ]);
        } catch (ConnectionException) {
            return new TelegramResult(TelegramResultType::TransientFailure);
        }

        $body = $response->json();
        if ($response->successful() && is_array($body) && ($body['ok'] ?? false) === true) {
            return new TelegramResult(
                TelegramResultType::Accepted,
                isset($body['result']['message_id']) ? (string) $body['result']['message_id'] : null,
            );
        }

        $description = strtolower((string) (is_array($body) ? ($body['description'] ?? '') : ''));

        return match (true) {
            $response->status() === 429 => new TelegramResult(
                TelegramResultType::RateLimited,
                retryAfter: max(1, (int) ($body['parameters']['retry_after'] ?? 1)),
            ),
            $response->status() === 401 => new TelegramResult(TelegramResultType::ProviderInvalid),
            $response->status() === 403 || str_contains($description, 'blocked') || str_contains($description, 'chat not found') => new TelegramResult(TelegramResultType::TargetInvalid),
            $response->serverError() => new TelegramResult(TelegramResultType::TransientFailure),
            default => new TelegramResult(TelegramResultType::PayloadInvalid),
        };
    }

    /** @param array<string, mixed> $payload @return array<string, mixed>|list<mixed> */
    private function request(string $method, array $payload = [], int $timeout = 10): array
    {
        $token = $this->token();

        $response = Http::acceptJson()
            ->connectTimeout(3)
            ->timeout($timeout)
            ->post("https://api.telegram.org/bot{$token}/{$method}", $payload);
        $body = $response->json();
        if (! $response->successful() || ! is_array($body) || ($body['ok'] ?? false) !== true) {
            throw new RuntimeException("Telegram {$method} failed.");
        }

        $result = $body['result'] ?? [];

        return is_array($result) ? $result : [];
    }

    private function token(): string
    {
        $token = (string) config('notification.telegram.bot_token');
        if ($token === '') {
            throw new RuntimeException('Telegram bot token is not configured.');
        }

        return $token;
    }
}
