<?php

namespace App\Services\Delivery;

use App\Enums\DeliveryStatus;
use App\Models\Delivery;
use App\Models\RuntimeState;
use App\Models\Subscriber;
use Carbon\CarbonImmutable;

class CapacityReporter
{
    /** @return array<string, mixed> */
    public function report(): array
    {
        $now = CarbonImmutable::now('UTC');
        $lastScanAt = $this->stateTimestamp('scanner', 'last_scan_at');
        $lastSendAt = $this->stateTimestamp('telegram_last_send', 'sent_at');
        $cooldownUntil = $this->stateTimestamp('telegram_provider', 'cooldown_until');
        $oldest = Delivery::query()
            ->whereIn('status', [DeliveryStatus::Pending->value, DeliveryStatus::Retry->value])
            ->where('not_before', '<=', $now)
            ->where('expires_at', '>', $now)
            ->min('created_at');
        $oldestAge = $oldest === null
            ? null
            : max(0, (int) floor(CarbonImmutable::parse($oldest, 'UTC')->diffInSeconds($now)));
        $activated = Subscriber::query()->where('master_enabled', true)
            ->whereHas('channels', fn ($query) => $query->where('enabled', true)->where('verified', true))
            ->count();
        $reasons = [];

        if (! config('notification.admission_enabled', false)) {
            $reasons[] = 'operator_closed';
        }
        if ($activated >= (int) config('notification.initial_paid_cap', 100)) {
            $reasons[] = 'cohort_full';
        }
        if ($lastScanAt === null || $lastScanAt->lt($now->subSeconds(30))) {
            $reasons[] = 'scanner_stale';
        }
        if ($oldestAge !== null && $oldestAge > 120) {
            $reasons[] = 'delivery_backlog';
        }
        if ($cooldownUntil?->gt($now->addSeconds(120))) {
            $reasons[] = 'provider_cooldown';
        }

        $health = RuntimeState::query()->find('admission_health');
        $healthySinceValue = $health?->value['healthy_since'] ?? null;
        $healthySince = is_string($healthySinceValue) ? CarbonImmutable::parse($healthySinceValue, 'UTC') : null;
        if ($reasons === []) {
            if ($healthySince === null) {
                $healthySince = $now;
                RuntimeState::query()->updateOrCreate(
                    ['key' => 'admission_health'],
                    ['value' => ['healthy_since' => $now->toIso8601String()]],
                );
            }
            if ($healthySince->gt($now->subMinutes(15))) {
                $reasons[] = 'recovery_window';
            }
        } elseif ($healthySince !== null) {
            RuntimeState::query()->updateOrCreate(
                ['key' => 'admission_health'],
                ['value' => ['healthy_since' => null]],
            );
            $healthySince = null;
        }

        return [
            'status' => $reasons === [] ? 'accepting' : 'closed',
            'reasons' => $reasons,
            'activated_subscribers' => $activated,
            'initial_paid_cap' => (int) config('notification.initial_paid_cap', 100),
            'oldest_ready_delivery_age_seconds' => $oldestAge,
            'last_scan_at' => $lastScanAt?->toIso8601String(),
            'last_send_at' => $lastSendAt?->toIso8601String(),
            'provider_cooldown_until' => $cooldownUntil?->toIso8601String(),
            'healthy_since' => $healthySince?->toIso8601String(),
            'checked_at' => $now->toIso8601String(),
        ];
    }

    private function stateTimestamp(string $key, string $field): ?CarbonImmutable
    {
        $value = RuntimeState::query()->find($key)?->value[$field] ?? null;

        return is_string($value) ? CarbonImmutable::parse($value, 'UTC') : null;
    }
}
