<?php

namespace App\Services\Delivery;

use App\Jobs\SendPushDelivery;
use App\Jobs\SendTelegramDelivery;
use App\Models\Delivery;

class DeliveryDispatcher
{
    public function dispatch(Delivery $delivery): void
    {
        $delivery->forceFill(['dispatch_requested_at' => now('UTC')])->save();
        $job = $delivery->channel_type === 'push'
            ? SendPushDelivery::dispatch($delivery->id)
            : SendTelegramDelivery::dispatch($delivery->id);
        $job->onQueue($delivery->channel_type === 'push'
            ? 'news-push'
            : ($delivery->priority === 'high' ? 'news-telegram-high' : 'news-telegram-standard'))
            ->delay($delivery->not_before)
            ->afterCommit();
    }
}
