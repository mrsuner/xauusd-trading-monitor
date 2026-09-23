<?php

namespace App\Jobs;

use App\Services\Digests\DigestBatchProcessor;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Cache;

class SendDigestBatch implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $tries = 0;

    public int $timeout = 25;

    public int $uniqueFor = 60;

    public function __construct(public readonly string $batchId)
    {
        $this->onQueue('news-digest-deliver');
    }

    public function uniqueId(): string
    {
        return $this->batchId;
    }

    public function handle(DigestBatchProcessor $processor): void
    {
        $lock = Cache::lock('digest-delivery:'.$this->batchId, 45);
        if (! $lock->get()) {
            $this->release(5);

            return;
        }
        try {
            $delay = $processor->process($this->batchId);
            if ($delay !== null) {
                $this->release($delay);
            }
        } finally {
            $lock->release();
        }
    }
}
