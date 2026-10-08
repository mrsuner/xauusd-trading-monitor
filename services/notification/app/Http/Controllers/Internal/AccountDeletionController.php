<?php

namespace App\Http\Controllers\Internal;

use App\Models\Subscriber;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

class AccountDeletionController
{
    public function suspend(string $accountUserId): JsonResponse
    {
        DB::transaction(function () use ($accountUserId): void {
            $subscriber = Subscriber::query()->where('account_user_id', $accountUserId)->lockForUpdate()->first();
            if (! $subscriber) {
                return;
            }
            if ($subscriber->master_enabled) {
                $subscriber->update(['master_enabled' => false, 'revision' => $subscriber->revision + 1]);
            }
            $subscriber->channels()->update(['enabled' => false]);
            $subscriber->digestPreference()->update(['enabled' => false]);
        });
        Cache::forget('news-access:'.$accountUserId);

        return response()->json(null, 204);
    }

    public function destroy(string $accountUserId): JsonResponse
    {
        Subscriber::query()->where('account_user_id', $accountUserId)->delete();
        Cache::forget('news-access:'.$accountUserId);

        return response()->json(null, 204);
    }
}
