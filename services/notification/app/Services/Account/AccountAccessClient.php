<?php

namespace App\Services\Account;

use App\Enums\AccessDecision;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

class AccountAccessClient
{
    public function check(string $accountUserId): AccessDecision
    {
        $cacheKey = 'news-access:'.$accountUserId;
        $cached = Cache::get($cacheKey);
        if (is_string($cached) && ($decision = AccessDecision::tryFrom($cached)) !== null) {
            return $decision;
        }

        $baseUrl = rtrim((string) config('notification.account.base_url'), '/');
        $secret = (string) config('notification.account.secret');
        if ($baseUrl === '' || $secret === '') {
            return AccessDecision::Unknown;
        }

        try {
            $response = Http::baseUrl($baseUrl)->acceptJson()->connectTimeout(2)->timeout(5)
                ->withHeader('X-Internal-Secret', $secret)
                ->get('/internal/news/users/'.$accountUserId.'/access');
        } catch (ConnectionException) {
            return AccessDecision::Unknown;
        }

        $decision = match (true) {
            $response->status() === 404 => AccessDecision::Missing,
            $response->successful() && $response->json('data.news.access_allowed') === true => AccessDecision::Active,
            $response->successful() && $response->json('data.news.access_allowed') === false => AccessDecision::Inactive,
            default => AccessDecision::Unknown,
        };

        if ($decision !== AccessDecision::Unknown) {
            Cache::put($cacheKey, $decision->value, (int) config('notification.account.access_cache_seconds', 60));
        }

        return $decision;
    }
}
