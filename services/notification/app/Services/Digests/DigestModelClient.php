<?php

namespace App\Services\Digests;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class DigestModelClient
{
    /** @param list<array<string, mixed>> $events @param array<string, mixed>|null $canonical @return array<string, mixed> */
    public function generate(string $topic, string $language, array $events, ?array $canonical = null): array
    {
        $settings = config('notification.digest.model', []);
        $key = trim((string) ($settings['api_key'] ?? ''));
        $model = trim((string) ($settings['name'] ?? ''));
        if ($key === '' || $model === '') {
            throw new RuntimeException('digest_model_not_configured');
        }

        $instruction = $canonical === null
            ? "Create a concise daily {$topic} news digest in English. Use only the supplied events. Distinguish facts, uncertainty, and conflicting reports. Do not give trading instructions or invent causal claims."
            : "Translate the supplied canonical digest into {$language}. Preserve every event_id exactly.";
        $input = $canonical === null ? ['events' => $events] : ['canonical' => $canonical];

        try {
            $response = Http::withToken($key)->acceptJson()
                ->connectTimeout(5)->timeout((int) ($settings['timeout_seconds'] ?? 60))
                ->post(rtrim((string) $settings['base_url'], '/').'/chat/completions', [
                    'model' => $model,
                    'temperature' => 0.2,
                    'max_tokens' => (int) ($settings['max_output_tokens'] ?? 1800),
                    'messages' => [
                        ['role' => 'system', 'content' => $instruction.' Return JSON with title, overview, and developments. Each development must contain text and event_ids.'],
                        ['role' => 'user', 'content' => json_encode($input, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE)],
                    ],
                    'response_format' => ['type' => 'json_object'],
                ])->throw();
        } catch (ConnectionException $exception) {
            throw new RuntimeException('digest_model_unavailable', previous: $exception);
        }

        $content = $response->json('choices.0.message.content');
        $decoded = is_string($content) ? json_decode($content, true) : null;
        if (! is_array($decoded)) {
            throw new RuntimeException('digest_model_invalid_json');
        }

        return $decoded;
    }

    public function provider(): string
    {
        return (string) config('notification.digest.model.provider');
    }

    public function model(): string
    {
        return (string) config('notification.digest.model.name');
    }
}
