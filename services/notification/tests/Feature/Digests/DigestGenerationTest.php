<?php

namespace Tests\Feature\Digests;

use App\Jobs\GenerateDigestEdition;
use App\Models\DigestEdition;
use App\Services\Digests\DigestEditionFreezer;
use App\Services\Digests\DigestGenerator;
use Carbon\CarbonImmutable;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Tests\TestCase;

class DigestGenerationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Schema::create('public_events', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('upstream_event_id');
            $table->string('severity');
            $table->integer('relevance_score')->nullable();
            $table->timestampTz('event_time')->nullable();
            $table->timestampTz('public_content_ready_at')->nullable();
            $table->timestampTz('invalidated_at')->nullable();
            $table->string('invalidation_kind')->nullable();
            $table->string('invalidation_reason')->nullable();
            $table->json('route_metadata');
            $table->boolean('is_visible')->default(true);
        });
        Schema::create('public_events_translations', function (Blueprint $table): void {
            $table->uuid('public_event_id');
            $table->string('language');
            $table->text('title')->nullable();
            $table->text('summary')->nullable();
        });
    }

    public function test_freeze_uses_stable_order_deduplicates_and_snapshots_inputs(): void
    {
        Queue::fake();
        config(['notification.digest.input_limit' => 2]);
        $start = CarbonImmutable::parse('2026-09-10 00:00:00 UTC');
        $firstUpstream = (string) Str::uuid();
        $expected = $this->event('A', 80, $start->addHour(), ['geopolitics'], $firstUpstream);
        $this->event('A', 70, $start->addHours(2), ['geopolitics'], $firstUpstream);
        $second = $this->event('B', 100, $start->addHours(3), ['geopolitics']);
        $this->event('C', 99, $start->addHours(4), ['geopolitics']);
        $this->event('S', 100, $start->addHours(5), ['energy']);
        $this->event('S', 100, $start->addHours(6), ['geopolitics'], eventTime: $start->subDays(2));
        $withoutSummary = $this->event('S', 100, $start->addHours(7), ['geopolitics']);
        DB::table('public_events_translations')->where('public_event_id', $withoutSummary)->delete();

        $edition = app(DigestEditionFreezer::class)->freeze('geopolitics', $start, $start->addDay());

        $this->assertSame([$expected, $second], $edition->events()->pluck('public_event_id')->all());
        $this->assertSame(2, $edition->input_count);
        $this->assertTrue($edition->coverage_truncated);
        $this->assertSame('English '.$expected, $edition->events()->first()->input_payload['summaries']['en']);
        Queue::assertPushed(GenerateDigestEdition::class, fn ($job): bool => $job->editionId === $edition->id);

        $same = app(DigestEditionFreezer::class)->freeze('geopolitics', $start, $start->addDay());
        $this->assertSame($edition->id, $same->id);
        Queue::assertPushed(GenerateDigestEdition::class, 1);
    }

    public function test_generator_publishes_citation_checked_english_and_chinese(): void
    {
        config([
            'notification.digest.model.api_key' => 'secret',
            'notification.digest.model.name' => 'model-test',
            'notification.digest.model.base_url' => 'https://model.test/v1',
        ]);
        $eventId = (string) Str::uuid();
        $edition = $this->edition($eventId);
        Http::fakeSequence()
            ->push($this->modelResponse('Daily energy', 'Overview', $eventId))
            ->push($this->modelResponse('每日能源', '摘要', $eventId));

        $delay = app(DigestGenerator::class)->generate($edition->id);

        $this->assertNull($delay);
        $edition->refresh()->load('translations');
        $this->assertSame('published', $edition->status);
        $this->assertSame(['en', 'zh-Hant'], $edition->translations->pluck('language')->sort()->values()->all());
        $this->assertNotNull($edition->published_at);
        $this->assertSame(22, $edition->model_prompt_tokens);
        $this->assertSame(14, $edition->model_completion_tokens);
        $this->assertSame(['request-test'], $edition->model_request_ids);
        $this->assertGreaterThanOrEqual(0, $edition->model_latency_ms);
        Http::assertSentCount(2);
        Http::assertSent(fn ($request): bool => $request->url() === 'https://model.test/v1/chat/completions'
            && $request['reasoning_effort'] === 'low'
            && $request['response_format']['type'] === 'json_schema'
            && $request['response_format']['json_schema']['strict'] === true);
    }

    public function test_freeze_excludes_headline_only_event_without_a_summary(): void
    {
        Queue::fake();
        $start = CarbonImmutable::parse('2026-09-10 00:00:00 UTC');
        $eventId = $this->event('A', 90, $start->addHour(), ['geopolitics']);
        DB::table('public_events_translations')->where('public_event_id', $eventId)->update([
            'title' => 'Headline without supporting summary',
            'summary' => '   ',
        ]);

        $edition = app(DigestEditionFreezer::class)->freeze('geopolitics', $start, $start->addDay());

        $this->assertSame('no_content', $edition->status);
        $this->assertSame(0, $edition->input_count);
        $this->assertDatabaseCount('digest_edition_events', 0);
        Queue::assertNothingPushed();
    }

    public function test_freeze_keeps_partial_language_event_without_snapshotting_empty_summary(): void
    {
        Queue::fake();
        $start = CarbonImmutable::parse('2026-09-10 00:00:00 UTC');
        $eventId = $this->event('A', 90, $start->addHour(), ['geopolitics']);
        DB::table('public_events_translations')->where('public_event_id', $eventId)->update(['summary' => '   ']);
        DB::table('public_events_translations')->insert([
            'public_event_id' => $eventId,
            'language' => 'zh-Hant',
            'title' => '只有部分語言有摘要',
            'summary' => '這是一筆可供摘要模型使用的繁體中文摘要。',
        ]);

        $edition = app(DigestEditionFreezer::class)->freeze('geopolitics', $start, $start->addDay());

        $this->assertSame('frozen', $edition->status);
        $this->assertSame(1, $edition->input_count);
        $this->assertSame(
            ['zh-Hant' => '這是一筆可供摘要模型使用的繁體中文摘要。'],
            $edition->events()->sole()->input_payload['summaries'],
        );
        Queue::assertPushed(GenerateDigestEdition::class, 1);
    }

    public function test_generator_retries_invalid_citations_until_fixed_deadline(): void
    {
        config(['notification.digest.model.api_key' => 'secret', 'notification.digest.model.name' => 'model-test']);
        $eventId = (string) Str::uuid();
        $edition = $this->edition($eventId);
        Http::fakeSequence()->push($this->modelResponse('Title', 'Overview', (string) Str::uuid()));

        $this->assertSame(60, app(DigestGenerator::class)->generate($edition->id));
        $edition->refresh();
        $this->assertSame('frozen', $edition->status);
        $this->assertSame('digest_citation_invalid', $edition->error_code);
        $this->assertSame(1, $edition->generation_attempt_count);
    }

    public function test_generator_rejects_translation_that_changes_citations(): void
    {
        config(['notification.digest.model.api_key' => 'secret', 'notification.digest.model.name' => 'model-test']);
        $firstEventId = (string) Str::uuid();
        $secondEventId = (string) Str::uuid();
        $edition = $this->edition($firstEventId);
        $edition->events()->create([
            'public_event_id' => $secondEventId,
            'upstream_event_id' => (string) Str::uuid(),
            'position' => 2,
            'input_payload' => ['event_id' => $secondEventId, 'summaries' => ['en' => 'Second source summary']],
        ]);
        Http::fakeSequence()
            ->push($this->modelResponse('Daily energy', 'Overview', $firstEventId))
            ->push($this->modelResponse('每日能源', '摘要', $secondEventId));

        $this->assertSame(60, app(DigestGenerator::class)->generate($edition->id));
        $this->assertSame('digest_translation_citations_mismatch', $edition->fresh()->error_code);
    }

    public function test_manual_command_can_dry_run_and_generate_without_dispatching_a_job(): void
    {
        Queue::fake();
        CarbonImmutable::setTestNow('2026-09-11 00:20:00 UTC');
        $start = CarbonImmutable::parse('2026-09-10 00:00:00 UTC');
        $eventId = $this->event('A', 90, $start->addHour(), ['energy']);

        $this->artisan('digest:generate', ['--date' => '2026-09-10', '--topic' => ['energy'], '--dry-run' => true])
            ->expectsOutputToContain('Digest window: 2026-09-10 UTC')
            ->assertSuccessful();
        $this->assertDatabaseCount('digest_editions', 0);

        config([
            'notification.digest.model.api_key' => 'secret',
            'notification.digest.model.name' => 'model-test',
            'notification.digest.model.base_url' => 'https://model.test/v1',
        ]);
        Http::fakeSequence()
            ->push($this->modelResponse('Daily energy', 'Overview', $eventId))
            ->push($this->modelResponse('每日能源', '摘要', $eventId));

        $this->artisan('digest:generate', ['--date' => '2026-09-10', '--topic' => ['energy']])
            ->assertSuccessful();

        $this->assertDatabaseCount('digest_editions', 1);
        $this->assertSame('published', DigestEdition::query()->sole()->status);
        Queue::assertNotPushed(GenerateDigestEdition::class);
        CarbonImmutable::setTestNow();
    }

    private function event(string $severity, int $score, CarbonImmutable $readyAt, array $domains, ?string $upstreamId = null, ?CarbonImmutable $eventTime = null): string
    {
        $id = (string) Str::uuid();
        DB::table('public_events')->insert([
            'id' => $id,
            'upstream_event_id' => $upstreamId ?? (string) Str::uuid(),
            'severity' => $severity,
            'relevance_score' => $score,
            'event_time' => $eventTime,
            'public_content_ready_at' => $readyAt,
            'route_metadata' => json_encode(['primary_domain' => $domains[0], 'matched_domains' => $domains]),
            'is_visible' => true,
        ]);
        DB::table('public_events_translations')->insert([
            'public_event_id' => $id, 'language' => 'en', 'summary' => 'English '.$id,
        ]);

        return $id;
    }

    private function edition(string $eventId): DigestEdition
    {
        $edition = DigestEdition::query()->create([
            'topic' => 'energy',
            'window_start' => now('UTC')->subDay(),
            'window_end' => now('UTC'),
            'cutoff_at' => now('UTC'),
            'deadline_at' => now('UTC')->addHour(),
            'status' => 'frozen',
            'input_count' => 1,
            'coverage_truncated' => false,
        ]);
        $edition->events()->create([
            'public_event_id' => $eventId,
            'upstream_event_id' => (string) Str::uuid(),
            'position' => 1,
            'input_payload' => ['event_id' => $eventId, 'summaries' => ['en' => 'Source summary']],
        ]);

        return $edition;
    }

    /** @return array<string, mixed> */
    private function modelResponse(string $title, string $overview, string $eventId): array
    {
        return [
            'id' => 'request-test',
            'usage' => ['prompt_tokens' => 11, 'completion_tokens' => 7],
            'choices' => [['message' => ['content' => json_encode([
                'title' => $title,
                'overview' => $overview,
                'developments' => [['text' => 'Development', 'event_ids' => [$eventId]]],
            ], JSON_THROW_ON_ERROR)]]],
        ];
    }
}
