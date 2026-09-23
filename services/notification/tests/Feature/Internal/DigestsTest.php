<?php

namespace Tests\Feature\Internal;

use App\Models\DigestEdition;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

class DigestsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.notification_internal.secret' => 'test-internal-secret']);
    }

    public function test_paid_reader_gets_requested_language_and_frozen_citations(): void
    {
        $edition = $this->edition();
        $edition->translations()->create([
            'language' => 'zh-Hant',
            'title' => '每日地緣摘要',
            'overview' => '今日摘要。',
            'developments' => [['text' => '事件重點', 'event_ids' => ['event-1']]],
            'source_content_hash' => str_repeat('a', 64),
        ]);
        $eventId = (string) Str::uuid();
        $edition->events()->create([
            'public_event_id' => $eventId,
            'upstream_event_id' => (string) Str::uuid(),
            'position' => 1,
        ]);

        $headers = $this->headers(true);
        $this->withHeaders($headers)->getJson($this->path().'?language=zh-Hant')
            ->assertOk()->assertJsonPath('data.0.status', 'ready')
            ->assertJsonPath('data.0.title', '每日地緣摘要');
        $this->withHeaders($headers)->getJson($this->path()."/{$edition->id}?language=zh-Hant")
            ->assertOk()->assertJsonPath('data.overview', '今日摘要。')
            ->assertJsonPath('data.event_ids.0', $eventId);
    }

    public function test_inactive_reader_is_denied_and_invalidated_text_is_not_served(): void
    {
        $edition = $this->edition();
        $edition->translations()->create([
            'language' => 'en', 'title' => 'Known invalid', 'overview' => 'Do not serve',
            'developments' => [], 'source_content_hash' => str_repeat('b', 64),
        ]);
        $this->withHeaders($this->headers(false))->getJson($this->path().'?language=en')
            ->assertForbidden()->assertJsonPath('error', 'upgrade_required');

        $edition->update([
            'status' => 'invalidated', 'invalidated_at' => now('UTC'),
            'invalidation_kind' => 'withdrawal', 'invalidation_reason' => 'Source withdrew the report.',
        ]);
        $this->withHeaders($this->headers(true))->getJson($this->path()."/{$edition->id}?language=en")
            ->assertOk()->assertJsonPath('data.status', 'invalidated')
            ->assertJsonPath('data.overview', null)
            ->assertJsonMissing(['overview' => 'Do not serve']);
    }

    private function edition(): DigestEdition
    {
        return DigestEdition::query()->create([
            'topic' => 'geopolitics',
            'window_start' => now('UTC')->subDay()->startOfDay(),
            'window_end' => now('UTC')->startOfDay(),
            'cutoff_at' => now('UTC')->startOfDay()->addMinutes(15),
            'deadline_at' => now('UTC')->startOfDay()->addHour(),
            'status' => 'published',
            'input_count' => 1,
            'coverage_truncated' => false,
            'published_at' => now('UTC'),
        ]);
    }

    /** @return array<string, string> */
    private function headers(bool $active): array
    {
        return [
            'X-Internal-Secret' => 'test-internal-secret',
            'X-News-Access' => $active ? 'active' : 'inactive',
        ];
    }

    private function path(): string
    {
        return '/internal/users/'.Str::ulid().'/digests';
    }
}
