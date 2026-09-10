<?php

namespace App\Services\Delivery;

use App\Enums\AccessDecision;
use App\Enums\DeliveryStatus;
use App\Models\Delivery;
use App\Models\EventReceipt;
use App\Models\RuntimeState;
use App\Models\Subscriber;
use App\Services\Account\AccountAccessClient;
use App\Services\Preferences\EventMatcher;
use App\Services\Preferences\TaxonomyCatalog;
use App\ValueObjects\PublicEventData;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class EventScanner
{
    public function __construct(
        private PublicEventRepository $events,
        private TaxonomyCatalog $taxonomy,
        private EventMatcher $matcher,
        private AccountAccessClient $access,
        private ContentSchedule $contentSchedule,
        private DeliveryDispatcher $dispatcher,
    ) {}

    /** @return array{events: int, deliveries: int, unresolved: int, dry_run: bool} */
    public function scan(): array
    {
        $dryRun = (bool) config('notification.dry_run', true);
        if (! config('notification.enabled', false)) {
            return ['events' => 0, 'deliveries' => 0, 'unresolved' => 0, 'dry_run' => $dryRun];
        }

        $now = CarbonImmutable::now('UTC');
        $startedAt = $dryRun
            ? $now->subMinutes((int) config('notification.scan.freshness_minutes', 60))
            : $this->startedAt($now);
        $catalog = $this->taxonomy->keys();
        $events = $this->events->recent($startedAt, $now, (int) config('notification.scan.batch_size', 100));
        $stats = ['events' => 0, 'deliveries' => 0, 'unresolved' => 0, 'dry_run' => $dryRun];

        foreach ($events as $event) {
            $receipt = EventReceipt::query()->find($event->upstreamEventId);
            if ($receipt?->processed_at !== null) {
                continue;
            }
            $stats['events']++;
            $result = $this->fanOut($event, $catalog, $now, $dryRun);
            $stats['deliveries'] += $result['deliveries'];
            $stats['unresolved'] += $result['unresolved'];
        }

        if (! $dryRun) {
            RuntimeState::query()->updateOrCreate(
                ['key' => 'scanner'],
                ['value' => ['last_scan_at' => $now->toIso8601String(), 'stats' => $stats]],
            );
        }

        return $stats;
    }

    /** @param array{categories: list<string>, tags: list<string>} $catalog @return array{deliveries: int, unresolved: int} */
    private function fanOut(PublicEventData $event, array $catalog, CarbonImmutable $now, bool $dryRun): array
    {
        $expiresAt = $event->receivedAt->addHour()->min($event->effectiveEventTime->addHour());
        $created = 0;
        $unknown = 0;
        $subscribers = Subscriber::query()
            ->with(['categories:key,subscriber_id', 'tags:key,subscriber_id', 'channels' => fn ($query) => $query->where('enabled', true)->where('verified', true)])
            ->where('master_enabled', true)
            ->where('effective_from', '<=', $event->receivedAt)
            ->get();

        foreach ($subscribers as $subscriber) {
            if (! $this->matcher->matches(
                $subscriber->match_all_categories,
                $subscriber->categories->pluck('key')->all(),
                $subscriber->tags->pluck('key')->all(),
                $subscriber->min_severity,
                $catalog['categories'],
                $catalog['tags'],
                $event->category,
                $event->tags,
                $event->severity,
            )) {
                continue;
            }

            $decision = $this->access->check($subscriber->account_user_id);
            if ($decision === AccessDecision::Unknown) {
                $unknown++;

                continue;
            }
            if ($decision !== AccessDecision::Active) {
                continue;
            }

            foreach ($subscriber->channels as $channel) {
                if ($channel->enabled_from === null || $channel->enabled_from->gt($event->receivedAt)) {
                    continue;
                }
                if ($dryRun) {
                    $created++;

                    continue;
                }

                $deliveryId = (string) Str::uuid();
                $inserted = Delivery::query()->insertOrIgnore([
                    'id' => $deliveryId,
                    'subscriber_id' => $subscriber->id,
                    'channel_id' => $channel->id,
                    'upstream_event_id' => $event->upstreamEventId,
                    'public_event_id' => $event->id,
                    'channel_type' => $channel->type,
                    'priority' => $event->severity === 'S' ? 'high' : 'standard',
                    'subscriber_revision' => $subscriber->revision,
                    'channel_revision' => $channel->revision,
                    'status' => DeliveryStatus::Pending->value,
                    'attempt_count' => 0,
                    'not_before' => $this->contentSchedule->notBefore($event, $subscriber->content_language, $now),
                    'expires_at' => $expiresAt,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);
                $created += $inserted;
                if ($inserted === 1) {
                    $this->dispatcher->dispatch(Delivery::query()->findOrFail($deliveryId));
                }
            }
        }

        if (! $dryRun) {
            DB::transaction(function () use ($event, $expiresAt, $unknown, $now): void {
                EventReceipt::query()->updateOrCreate(
                    ['upstream_event_id' => $event->upstreamEventId],
                    [
                        'public_event_id' => $event->id,
                        'received_at' => $event->receivedAt,
                        'processed_at' => $unknown === 0 ? $now : null,
                        'expires_at' => $expiresAt,
                    ],
                );
            });
        }

        return ['deliveries' => $created, 'unresolved' => $unknown];
    }

    private function startedAt(CarbonImmutable $now): CarbonImmutable
    {
        $state = RuntimeState::query()->firstOrCreate(
            ['key' => 'notification_started'],
            ['value' => ['started_at' => $now->toIso8601String()]],
        );

        return CarbonImmutable::parse($state->value['started_at'], 'UTC');
    }
}
