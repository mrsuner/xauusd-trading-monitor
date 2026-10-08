<?php

namespace Tests\Feature\Internal;

use App\Enums\AccessDecision;
use App\Models\Subscriber;
use App\Services\Account\AccountAccessClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

class AccountDeletionTest extends TestCase
{
    use RefreshDatabase;

    private function subscriber(): Subscriber
    {
        return Subscriber::create(['account_user_id' => (string) Str::ulid(), 'master_enabled' => true,
            'match_all_categories' => true, 'min_severity' => 'A', 'content_language' => 'en',
            'revision' => 1, 'effective_from' => now()]);
    }

    public function test_cleanup_requires_internal_secret_and_is_idempotent(): void
    {
        config(['services.notification_internal.secret' => 'test-secret']);
        $subscriber = $this->subscriber();
        $other = $this->subscriber();
        $base = '/internal/users/'.$subscriber->account_user_id.'/account-deletion';
        $subscriber->channels()->create(['type' => 'telegram', 'enabled' => true, 'verified' => true, 'revision' => 1]);
        $subscriber->categories()->create(['key' => 'energy']);
        $subscriber->tags()->create(['key' => 'oil']);
        $subscriber->digestPreference()->create(['enabled' => true, 'revision' => 1, 'effective_from' => now()]);
        DB::table('digest_preference_topics')->insert(['subscriber_id' => $subscriber->id, 'topic' => 'energy']);
        $edition = (string) Str::uuid();
        DB::table('digest_editions')->insert(['id' => $edition, 'topic' => 'energy', 'window_start' => now()->subDay(),
            'window_end' => now(), 'cutoff_at' => now(), 'deadline_at' => now(), 'status' => 'no_content']);
        $this->deleteJson($base)->assertUnauthorized();
        $this->withHeader('X-Internal-Secret', 'test-secret')->postJson($base.'/suspend')->assertNoContent();
        $this->assertFalse($subscriber->fresh()->master_enabled);
        $this->assertFalse($subscriber->channels()->first()->enabled);
        $this->assertFalse($subscriber->digestPreference()->first()->enabled);
        $this->postJson($base.'/suspend')->assertNoContent();
        $this->assertSame(2, $subscriber->fresh()->revision);
        $this->deleteJson($base)->assertNoContent();
        $this->deleteJson($base)->assertNoContent();
        foreach (['channels', 'category_subscriptions', 'tag_subscriptions', 'digest_preferences', 'digest_preference_topics'] as $table) {
            $this->assertDatabaseMissing($table, ['subscriber_id' => $subscriber->id]);
        }
        $this->assertDatabaseHas('subscribers', ['id' => $other->id]);
        $this->assertDatabaseHas('digest_editions', ['id' => $edition]);
    }

    public function test_send_time_eligibility_does_not_trust_cached_active_access(): void
    {
        config(['notification.account.base_url' => 'https://account.test', 'notification.account.secret' => 'test']);
        Cache::put('news-access:user', AccessDecision::Active->value, 60);
        Http::preventStrayRequests();
        Http::fake(['account.test/*' => Http::response(['data' => ['news' => ['access_allowed' => false]]])]);
        $client = app(AccountAccessClient::class);
        $this->assertSame(AccessDecision::Active, $client->check('user'));
        $this->assertSame(AccessDecision::Inactive, $client->check('user', fresh: true));
        Http::assertSentCount(1);
    }
}
