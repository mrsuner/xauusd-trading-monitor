<?php

namespace App\Jobs;

use App\Models\Delivery;
use App\Services\Delivery\DeliveryProcessor;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Cache;

class SendTelegramDelivery implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $uniqueFor = 60;

    public int $timeout = 25;

    public int $tries = 0;

    public int $maxExceptions = 3;

    public function __construct(public readonly string $deliveryId) {}

    public function uniqueId(): string
    {
        return $this->deliveryId;
    }

    public function retryUntil(): \DateTimeInterface
    {
        return Delivery::query()->find($this->deliveryId)?->expires_at ?? now()->addMinute();
    }

    public function handle(DeliveryProcessor $processor): void
    {
        $lock = Cache::lock(
            'delivery:'.$this->deliveryId,
            (int) config('notification.delivery.lock_seconds', 45),
        );
        if (! $lock->get()) {
            $this->release(5);

            return;
        }

        try {
            Delivery::query()->whereKey($this->deliveryId)->update(['dispatch_confirmed_at' => now('UTC')]);
            $delay = $processor->process($this->deliveryId);
            if ($delay !== null) {
                $this->release($delay);
            }
        } finally {
            $lock->release();
        }
    }
}
