<?php

namespace App\Services\Digests;

use App\Models\DigestEdition;
use Illuminate\Support\Facades\DB;
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

            return null;
        }

        $edition->update([
            'status' => 'generating',
            'generation_attempt_count' => $edition->generation_attempt_count + 1,
            'model_provider' => $this->model->provider(),
            'model_name' => $this->model->model(),
            'error_code' => null,
        ]);

        try {
            $events = $edition->events->map(fn ($event): array => $event->input_payload ?? [
                'event_id' => $event->public_event_id,
            ])->values()->all();
            $allowedIds = $edition->events->pluck('public_event_id')->map(fn ($id): string => (string) $id)->all();
            $english = $this->validate($this->model->generate($edition->topic, 'en', $events), $allowedIds);
            $traditionalChinese = $this->validate(
                $this->model->generate($edition->topic, 'zh-Hant', $events, $english),
                $allowedIds,
            );
            $sourceHash = hash('sha256', json_encode($english, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

            DB::transaction(function () use ($editionId, $english, $traditionalChinese, $sourceHash): void {
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
                $locked->update(['status' => 'published', 'published_at' => now('UTC'), 'error_code' => null]);
            });

            return null;
        } catch (Throwable $exception) {
            $edition->refresh();
            $expired = $edition->deadline_at->isPast();
            $edition->update([
                'status' => $expired ? 'failed' : 'frozen',
                'error_code' => $this->errorCode($exception),
            ]);

            return $expired ? null : 60;
        }
    }

    /** @param array<string, mixed> $content @param list<string> $allowedIds @return array{title: string, overview: string, developments: list<array{text: string, event_ids: list<string>}>} */
    private function validate(array $content, array $allowedIds): array
    {
        $title = trim((string) ($content['title'] ?? ''));
        $overview = trim((string) ($content['overview'] ?? ''));
        $developments = $content['developments'] ?? null;
        if ($title === '' || $overview === '' || ! is_array($developments) || ! array_is_list($developments)) {
            throw new RuntimeException('digest_content_invalid');
        }

        $validated = [];
        foreach ($developments as $development) {
            $text = is_array($development) ? trim((string) ($development['text'] ?? '')) : '';
            $ids = is_array($development) && is_array($development['event_ids'] ?? null)
                ? array_values(array_unique(array_map('strval', $development['event_ids']))) : [];
            if ($text === '' || $ids === [] || array_diff($ids, $allowedIds) !== []) {
                throw new RuntimeException('digest_citation_invalid');
            }
            $validated[] = ['text' => $text, 'event_ids' => $ids];
        }
        if ($validated === []) {
            throw new RuntimeException('digest_content_invalid');
        }

        return ['title' => $title, 'overview' => $overview, 'developments' => $validated];
    }

    private function errorCode(Throwable $exception): string
    {
        $message = preg_replace('/[^a-z0-9_]+/', '_', strtolower($exception->getMessage())) ?? '';

        return substr(trim($message, '_') ?: 'digest_generation_failed', 0, 255);
    }
}
