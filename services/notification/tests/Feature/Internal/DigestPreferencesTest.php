<?php

namespace Tests\Feature\Internal;

use App\Models\Subscriber;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class DigestPreferencesTest extends TestCase
{
    use RefreshDatabase;

    private string $userId;

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.notification_internal.secret' => 'test-internal-secret']);
        $this->userId = (string) Str::ulid();
    }

    public function test_get_returns_independent_disabled_defaults_without_creating_rows(): void
    {
        $this->request('GET', [], false)->assertOk()
            ->assertJsonPath('data.access', 'upgrade_required')
            ->assertJsonPath('data.preferences.enabled', false)
            ->assertJsonPath('data.preferences.topics', [])
            ->assertJsonPath('data.available_topics.0', 'geopolitics');

        $this->assertDatabaseCount('subscribers', 0);
        $this->assertDatabaseCount('digest_preferences', 0);
    }

    public function test_active_user_can_replace_topics_and_identical_write_is_idempotent(): void
    {
        $payload = ['enabled' => true, 'topics' => ['monetary', 'geopolitics']];
        $this->request('PUT', $payload, true)->assertOk()
            ->assertJsonPath('data.preferences.topics.0', 'geopolitics')
            ->assertJsonPath('data.preferences.revision', 1);
        $this->request('PUT', $payload, true)->assertOk()
            ->assertJsonPath('data.preferences.revision', 1);

        $this->assertDatabaseCount('digest_preferences', 1);
        $this->assertDatabaseCount('digest_preference_topics', 2);
    }

    public function test_empty_enabled_topics_and_unknown_topic_are_rejected(): void
    {
        $this->request('PUT', ['enabled' => true, 'topics' => []], true)
            ->assertUnprocessable()->assertJsonPath('error', 'validation_failed');
        $this->request('PUT', ['enabled' => true, 'topics' => ['invented']], true)
            ->assertUnprocessable()->assertJsonPath('error', 'validation_failed');
    }

    public function test_unpaid_user_can_disable_without_changing_topics(): void
    {
        $payload = ['enabled' => true, 'topics' => ['energy']];
        $this->request('PUT', $payload, true)->assertOk();
        $this->request('PUT', ['enabled' => false, 'topics' => ['energy']], false)->assertOk();
        $this->request('PUT', ['enabled' => false, 'topics' => ['monetary']], false)
            ->assertForbidden()->assertJsonPath('error', 'upgrade_required');

        self::assertFalse(Subscriber::query()->firstOrFail()->digestPreference->enabled);
    }

    /** @param array<string, mixed> $payload */
    private function request(string $method, array $payload, bool $active): TestResponse
    {
        return $this->withHeaders([
            'X-Internal-Secret' => 'test-internal-secret',
            'X-News-Access' => $active ? 'active' : 'inactive',
        ])->json($method, "/internal/users/{$this->userId}/digest-preferences", $payload);
    }
}
