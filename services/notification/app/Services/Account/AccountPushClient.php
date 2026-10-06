<?php

namespace App\Services\Account;

use App\Models\Delivery;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;

class AccountPushClient
{
    public function send(Delivery $delivery, string $accountUserId, string $title, string $body, string $url): int
    {
        $baseUrl = rtrim((string) config('notification.account.base_url'), '/');
        $secret = (string) config('notification.account.secret');
        if ($baseUrl === '' || $secret === '') {
            return 503;
        }

        try {
            return Http::baseUrl($baseUrl)->acceptJson()->asJson()->connectTimeout(2)->timeout(20)
                ->withHeader('X-Internal-Secret', $secret)
                ->post('/internal/news/users/'.$accountUserId.'/push', [
                    'delivery_id' => $delivery->id,
                    'event_id' => $delivery->public_event_id,
                    'title' => $title,
                    'body' => $body,
                    'url' => $url,
                    'ttl_seconds' => max(1, min(3600, $delivery->expires_at->getTimestamp() - now('UTC')->getTimestamp())),
                ])->status();
        } catch (ConnectionException) {
            return 503;
        }
    }
}
