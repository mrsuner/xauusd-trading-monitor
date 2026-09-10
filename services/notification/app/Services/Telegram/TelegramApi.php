<?php

namespace App\Services\Telegram;

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

    /** @param array<string, mixed> $payload @return array<string, mixed>|list<mixed> */
    private function request(string $method, array $payload = [], int $timeout = 10): array
    {
        $token = (string) config('notification.telegram.bot_token');
        if ($token === '') {
            throw new RuntimeException('Telegram bot token is not configured.');
        }

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
}
