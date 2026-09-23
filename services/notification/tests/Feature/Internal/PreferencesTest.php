<?php

namespace Tests\Feature\Internal;

use App\Models\Subscriber;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class PreferencesTest extends TestCase
{
    use RefreshDatabase;

    private string $userId;

    protected function setUp(): void
    {
        parent::setUp();

        config([
            'services.notification_internal.secret' => 'test-internal-secret',
            'notification.supported_languages' => ['zh-Hant', 'en'],
            'notification.default_language' => 'zh-Hant',
        ]);
        $this->userId = (string) Str::ulid();

        Schema::create('public_subscription_categories', function (Blueprint $table): void {
            $table->string('key')->primary();
        });
        Schema::create('public_subscription_tags', function (Blueprint $table): void {
            $table->string('key')->primary();
        });
        DB::table('public_subscription_categories')->insert([
            ['key' => 'energy'],
            ['key' => 'macro_data'],
        ]);
        DB::table('public_subscription_tags')->insert([
            ['key' => 'ecb'],
            ['key' => 'fed'],
        ]);
    }

    public function test_internal_secret_is_required(): void
    {
        $this->getJson("/internal/users/{$this->userId}/preferences")
            ->assertUnauthorized()
            ->assertExactJson([
                'error' => 'unauthorized',
                'message' => 'Invalid internal service credentials.',
            ]);
    }

    public function test_get_returns_defaults_without_creating_a_subscriber(): void
    {
        $this->internalGet()->assertOk()->assertJsonPath('data.access', 'upgrade_required')
            ->assertJsonPath('data.preferences.master_enabled', false)
            ->assertJsonPath('data.preferences.min_severity', 'A')
            ->assertJsonPath('data.preferences.revision', 0);

        $this->assertDatabaseCount('subscribers', 0);
    }

    public function test_active_user_can_replace_preferences_and_identical_put_is_idempotent(): void
    {
        $payload = $this->payload(categories: ['macro_data'], tags: ['fed']);

        $this->internalPut($payload, active: true)
            ->assertOk()
            ->assertJsonPath('data.preferences.categories.0', 'macro_data')
            ->assertJsonPath('data.preferences.tags.0', 'fed')
            ->assertJsonPath('data.preferences.revision', 1);

        $this->internalPut($payload, active: true)
            ->assertOk()
            ->assertJsonPath('data.preferences.revision', 1);

        $this->assertDatabaseCount('subscribers', 1);
    }

    public function test_unpaid_user_can_disable_but_cannot_change_scope(): void
    {
        $this->internalPut($this->payload(categories: ['macro_data']), active: true)->assertOk();

        $this->internalPut($this->payload(categories: ['macro_data']), active: false)->assertOk();
        $this->internalPut($this->payload(categories: ['energy']), active: false)
            ->assertForbidden()
            ->assertJsonPath('error', 'upgrade_required');
    }

    public function test_enabling_requires_a_verified_enabled_channel(): void
    {
        $this->internalPut($this->payload(categories: ['macro_data']), active: true)->assertOk();

        $this->internalPut($this->payload(master: true, categories: ['macro_data']), active: true)
            ->assertStatus(409)
            ->assertJsonPath('error', 'channel_required');

        $subscriber = Subscriber::query()->where('account_user_id', $this->userId)->firstOrFail();
        $subscriber->channels()->create([
            'id' => (string) Str::uuid(),
            'type' => 'telegram',
            'enabled' => true,
            'verified' => true,
            'revision' => 1,
            'enabled_from' => now('UTC'),
        ]);

        $this->internalPut($this->payload(master: true, categories: ['macro_data']), active: true)
            ->assertOk()
            ->assertJsonPath('data.preferences.master_enabled', true)
            ->assertJsonPath('data.preferences.revision', 2);
    }

    public function test_unknown_taxonomy_and_unknown_fields_are_rejected_without_writes(): void
    {
        $this->internalPut($this->payload(categories: ['invented']), active: true)
            ->assertUnprocessable()
            ->assertJsonPath('error', 'validation_failed');

        $this->internalPut([...$this->payload(), 'user_id' => $this->userId], active: true)
            ->assertUnprocessable()
            ->assertJsonPath('fields.request.0', 'Unknown fields: user_id.');

        $this->assertDatabaseCount('subscribers', 0);
    }

    /** @param list<string> $categories @param list<string> $tags @return array<string, mixed> */
    private function payload(bool $master = false, array $categories = [], array $tags = []): array
    {
        return [
            'master_enabled' => $master,
            'match_all_categories' => false,
            'min_severity' => 'A',
            'content_language' => 'zh-Hant',
            'categories' => $categories,
            'tags' => $tags,
        ];
    }

    private function internalGet(): TestResponse
    {
        return $this->withHeaders([
            'X-Internal-Secret' => 'test-internal-secret',
            'X-News-Access' => 'inactive',
        ])->getJson("/internal/users/{$this->userId}/preferences");
    }

    /** @param array<string, mixed> $payload */
    private function internalPut(array $payload, bool $active): TestResponse
    {
        return $this->withHeaders([
            'X-Internal-Secret' => 'test-internal-secret',
            'X-News-Access' => $active ? 'active' : 'inactive',
        ])->putJson("/internal/users/{$this->userId}/preferences", $payload);
    }
}
