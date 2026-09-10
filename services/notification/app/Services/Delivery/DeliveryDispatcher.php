<?php

namespace App\Services\Delivery;

use App\Jobs\SendTelegramDelivery;
use App\Models\Delivery;

class DeliveryDispatcher
{
    public function dispatch(Delivery $delivery): void
    {
        $delivery->forceFill(['dispatch_requested_at' => now('UTC')])->save();
        SendTelegramDelivery::dispatch($delivery->id)
            ->onQueue($delivery->priority === 'high' ? 'news-telegram-high' : 'news-telegram-standard')
            ->delay($delivery->not_before)
            ->afterCommit();
    }
}
