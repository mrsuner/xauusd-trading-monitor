<?php

namespace App\Services\Digests;

use App\Jobs\SendDigestBatch;
use App\Models\DigestBatch;
use App\Models\DigestEdition;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;

class DigestMaintenance
{
    public function __construct(private DigestBatchCoordinator $coordinator) {}

    /** @return array{invalidated: int, batches: int, deleted: int} */
    public function run(?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now('UTC');
        $invalidated = $this->propagateInvalidations($now);
        $batches = $this->coordinator->scan($now);
        DigestBatch::query()->whereIn('status', ['pending', 'retry', 'sending'])
            ->where('not_before', '<=', $now)->pluck('id')
            ->each(fn (string $id) => SendDigestBatch::dispatch($id));
        $cutoff = $now->subDays((int) config('notification.digest.retention_days', 90));
        $deleted = DigestEdition::query()->where('window_start', '<', $cutoff)->delete();
        DigestBatch::query()->where('window_start', '<', $cutoff)->delete();

        return ['invalidated' => $invalidated, 'batches' => $batches, 'deleted' => $deleted];
    }

    private function propagateInvalidations(CarbonImmutable $now): int
    {
        $events = DB::getDriverName() === 'pgsql' ? 'public.public_events' : 'public_events';
        $affected = DB::table('digest_edition_events as dee')->join($events.' as pe', 'pe.id', '=', 'dee.public_event_id')
            ->whereNotNull('pe.invalidated_at')->get([
                'dee.edition_id', 'pe.invalidation_kind', 'pe.invalidation_reason', 'pe.invalidated_at',
            ])->unique('edition_id');

        foreach ($affected as $row) {
            DB::transaction(function () use ($row, $now): void {
                $edition = DigestEdition::query()->lockForUpdate()->find((string) $row->edition_id);
                if ($edition === null || $edition->status === 'invalidated') {
                    return;
                }
                $edition->update([
                    'status' => 'invalidated',
                    'invalidated_at' => $row->invalidated_at ?? $now,
                    'invalidation_kind' => $row->invalidation_kind,
                    'invalidation_reason' => $row->invalidation_reason,
                ]);
                $batches = DigestBatch::query()->whereIn('status', ['pending', 'retry'])
                    ->whereHas('editions', fn ($query) => $query->whereKey($edition->id))->get();
                foreach ($batches as $batch) {
                    $batch->editions()->detach($edition->id);
                    $batch->refresh();
                    $batch->update($batch->editions()->exists()
                        ? ['error_code' => 'partial_coverage']
                        : ['status' => 'canceled', 'error_code' => 'edition_invalidated']);
                }
            });
        }

        return $affected->count();
    }
}
