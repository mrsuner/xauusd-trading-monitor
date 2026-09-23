<?php

namespace App\Services\Delivery;

use App\Enums\DeliveryStatus;
use App\Models\Delivery;
use Carbon\CarbonImmutable;

class LedgerReconciler
{
    public function __construct(private DeliveryDispatcher $dispatcher) {}

    /** @return array{expired: int, recovered_sending: int, dispatched: int} */
    public function reconcile(): array
    {
        $now = CarbonImmutable::now('UTC');
        $terminal = [
            DeliveryStatus::Sent->value,
            DeliveryStatus::Failed->value,
            DeliveryStatus::Canceled->value,
            DeliveryStatus::Expired->value,
        ];
        $expired = Delivery::query()->whereNotIn('status', $terminal)
            ->where('expires_at', '<=', $now)
            ->update(['status' => DeliveryStatus::Expired->value, 'error_code' => 'freshness_expired', 'updated_at' => $now]);
        $recovered = Delivery::query()->where('status', DeliveryStatus::Sending->value)
            ->where('last_attempt_at', '<=', $now->subSeconds((int) config('notification.delivery.lock_seconds', 45)))
            ->update([
                'status' => DeliveryStatus::Retry->value,
                'not_before' => $now,
                'error_code' => 'provider_outcome_ambiguous',
                'updated_at' => $now,
            ]);

        $stale = $now->subSeconds((int) config('notification.delivery.dispatch_stale_seconds', 120));
        $deliveries = Delivery::query()
            ->whereIn('status', [DeliveryStatus::Pending->value, DeliveryStatus::Retry->value])
            ->where('not_before', '<=', $now)
            ->where('expires_at', '>', $now)
            ->where(function ($query) use ($stale): void {
                $query->whereNull('dispatch_confirmed_at')->where(function ($nested) use ($stale): void {
                    $nested->whereNull('dispatch_requested_at')->orWhere('dispatch_requested_at', '<=', $stale);
                })->orWhere('dispatch_confirmed_at', '<=', $stale);
            })
            ->orderBy('created_at')
            ->limit(100)
            ->get();
        $deliveries->each(fn (Delivery $delivery) => $this->dispatcher->dispatch($delivery));

        return ['expired' => $expired, 'recovered_sending' => $recovered, 'dispatched' => $deliveries->count()];
    }
}
