<?php

namespace App\Services\Digests;

use App\Models\DigestEdition;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use RuntimeException;
use Throwable;

class DigestGenerator
{
    public function __construct(private DigestModelClient $model) {}

    /** Return the number of seconds before retry, or null when resolved. */
    public function generate(string $editionId): ?int
    {
        $edition = DigestEdition::query()->with('events')->find($editionId);
        if ($edition === null || in_array($edition->status, ['published', 'no_content', 'failed', 'invalidated'], true)) {
            return null;
        }
        if ($edition->deadline_at->isPast()) {
            $edition->update(['status' => 'failed', 'error_code' => 'generation_deadline_expired']);
            Log::warning('Digest generation deadline expired.', [
                'edition_id' => $edition->id,
                'topic' => $edition->topic,
                'attempts' => $edition->generation_attempt_count,
            ]);

            return null;
        }
        if (($invalidation = $this->invalidation($edition)) !== null) {
            $this->invalidate($edition, $invalidation);

            return null;
        }

        $edition->update([
            'status' => 'generating',
            'generation_attempt_count' => $edition->generation_attempt_count + 1,
            'model_provider' => $this->model->provider(),
            'model_name' => $this->model->model(),
            'error_code' => null,
        ]);

        $promptTokens = 0;
        $completionTokens = 0;
        $latencyMs = 0;
        $requestIds = [];

        try {
            $events = $edition->events->map(fn ($event): array => $event->input_payload ?? [
                'event_id' => $event->public_event_id,
            ])->values()->all();
            $allowedIds = $edition->events->pluck('public_event_id')->map(fn ($id): string => (string) $id)->all();
            $englishResult = $this->model->generate($edition->topic, 'en', $events);
            $promptTokens += $englishResult->promptTokens;
            $completionTokens += $englishResult->completionTokens;
            $latencyMs += $englishResult->latencyMs;
            if ($englishResult->requestId !== null) {
                $requestIds[] = $englishResult->requestId;
            }
            $english = $this->validate($englishResult->content, $allowedIds);
            $translationResult = $this->model->generate($edition->topic, 'zh-Hant', $events, $english);
            $promptTokens += $translationResult->promptTokens;
            $completionTokens += $translationResult->completionTokens;
            $latencyMs += $translationResult->latencyMs;
            if ($translationResult->requestId !== null) {
                $requestIds[] = $translationResult->requestId;
            }
            $traditionalChinese = $this->validate(
                $translationResult->content,
                $allowedIds,
            );
            $this->assertTranslationMatches($english, $traditionalChinese);
            if (($invalidation = $this->invalidation($edition)) !== null) {
                $edition->update($this->telemetry($edition, $promptTokens, $completionTokens, $latencyMs, $requestIds));
                $this->invalidate($edition, $invalidation);

                return null;
            }
            $sourceHash = hash('sha256', json_encode($english, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

            DB::transaction(function () use (
                $editionId,
                $english,
                $traditionalChinese,
                $sourceHash,
                $promptTokens,
                $completionTokens,
                $latencyMs,
                $requestIds,
            ): void {
                $locked = DigestEdition::query()->lockForUpdate()->findOrFail($editionId);
                if ($locked->status === 'invalidated') {
                    return;
                }
                foreach (['en' => $english, 'zh-Hant' => $traditionalChinese] as $language => $content) {
                    $locked->translations()->updateOrCreate(['language' => $language], [
                        'title' => $content['title'],
                        'overview' => $content['overview'],
                        'developments' => $content['developments'],
                        'source_content_hash' => $sourceHash,
                    ]);
                }
                $locked->update([
                    'status' => 'published',
                    'published_at' => now('UTC'),
                    'error_code' => null,
                    ...$this->telemetry($locked, $promptTokens, $completionTokens, $latencyMs, $requestIds),
                ]);
            });
            Log::info('Digest edition published.', [
                'edition_id' => $editionId,
                'topic' => $edition->topic,
                'prompt_tokens' => $promptTokens,
                'completion_tokens' => $completionTokens,
                'latency_ms' => $latencyMs,
                'model_request_ids' => $requestIds,
            ]);

            return null;
        } catch (Throwable $exception) {
            $edition->refresh();
            $expired = $edition->deadline_at->isPast();
            $edition->update([
                'status' => $expired ? 'failed' : 'frozen',
                'error_code' => $this->errorCode($exception),
                ...$this->telemetry($edition, $promptTokens, $completionTokens, $latencyMs, $requestIds),
            ]);
            Log::warning('Digest generation attempt failed.', [
                'edition_id' => $edition->id,
                'topic' => $edition->topic,
                'error_code' => $edition->error_code,
                'expired' => $expired,
                'prompt_tokens' => $promptTokens,
                'completion_tokens' => $completionTokens,
                'latency_ms' => $latencyMs,
                'model_request_ids' => $requestIds,
            ]);

            return $expired ? null : 60;
        }
    }

    /** @param array<string, mixed> $content @param list<string> $allowedIds @return array{title: string, overview: string, developments: list<array{text: string, event_ids: list<string>}>} */
    private function validate(array $content, array $allowedIds): array
    {
        $limits = config('notification.digest.limits', []);
        $title = trim((string) ($content['title'] ?? ''));
        $overview = trim((string) ($content['overview'] ?? ''));
        $developments = $content['developments'] ?? null;
        if ($title === '' || mb_strlen($title) > (int) ($limits['title_chars'] ?? 180)
            || $overview === '' || mb_strlen($overview) > (int) ($limits['overview_chars'] ?? 2000)
            || ! is_array($developments) || ! array_is_list($developments)
            || count($developments) > (int) ($limits['developments'] ?? 12)) {
            throw new RuntimeException('digest_content_invalid');
        }

        $validated = [];
        foreach ($developments as $development) {
            $text = is_array($development) ? trim((string) ($development['text'] ?? '')) : '';
            $ids = is_array($development) && is_array($development['event_ids'] ?? null)
                ? array_values(array_unique(array_map('strval', $development['event_ids']))) : [];
            if ($text === '' || mb_strlen($text) > (int) ($limits['development_chars'] ?? 1000)
                || $ids === [] || array_diff($ids, $allowedIds) !== []) {
                throw new RuntimeException('digest_citation_invalid');
            }
            $validated[] = ['text' => $text, 'event_ids' => $ids];
        }
        if ($validated === []) {
            throw new RuntimeException('digest_content_invalid');
        }

        return ['title' => $title, 'overview' => $overview, 'developments' => $validated];
    }

    /**
     * A translation may change prose, but it must retain the canonical
     * development count and the exact citation grouping for each item.
     *
     * @param  array{developments: list<array{text: string, event_ids: list<string>}>}  $canonical
     * @param  array{developments: list<array{text: string, event_ids: list<string>}>}  $translation
     */
    private function assertTranslationMatches(array $canonical, array $translation): void
    {
        if (count($canonical['developments']) !== count($translation['developments'])) {
            throw new RuntimeException('digest_translation_citations_mismatch');
        }
        foreach ($canonical['developments'] as $index => $development) {
            if ($development['event_ids'] !== $translation['developments'][$index]['event_ids']) {
                throw new RuntimeException('digest_translation_citations_mismatch');
            }
        }
    }

    /** @param list<string> $requestIds @return array<string, mixed> */
    private function telemetry(
        DigestEdition $edition,
        int $promptTokens,
        int $completionTokens,
        int $latencyMs,
        array $requestIds,
    ): array {
        return [
            'model_prompt_tokens' => $edition->model_prompt_tokens + $promptTokens,
            'model_completion_tokens' => $edition->model_completion_tokens + $completionTokens,
            'model_latency_ms' => $edition->model_latency_ms + $latencyMs,
            'model_request_ids' => array_values(array_unique([
                ...($edition->model_request_ids ?? []),
                ...$requestIds,
            ])),
        ];
    }

    private function errorCode(Throwable $exception): string
    {
        $message = preg_replace('/[^a-z0-9_]+/', '_', strtolower($exception->getMessage())) ?? '';

        return substr(trim($message, '_') ?: 'digest_generation_failed', 0, 255);
    }

    private function invalidation(DigestEdition $edition): ?object
    {
        $table = DB::getDriverName() === 'pgsql' ? 'public.public_events' : 'public_events';

        return DB::table($table)->whereIn('id', $edition->events->pluck('public_event_id'))
            ->whereNotNull('invalidated_at')->orderBy('invalidated_at')->first([
                'invalidated_at', 'invalidation_kind', 'invalidation_reason',
            ]);
    }

    private function invalidate(DigestEdition $edition, object $invalidation): void
    {
        $edition->update([
            'status' => 'invalidated',
            'invalidated_at' => $invalidation->invalidated_at,
            'invalidation_kind' => $invalidation->invalidation_kind,
            'invalidation_reason' => $invalidation->invalidation_reason,
        ]);
    }
}
