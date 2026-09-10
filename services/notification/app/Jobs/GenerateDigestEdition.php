<?php

namespace App\Jobs;

use App\Models\DigestEdition;
use App\Services\Digests\DigestGenerator;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Cache;

class GenerateDigestEdition implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $tries = 0;

    public int $timeout = 180;

    public int $uniqueFor = 300;

    public function __construct(public readonly string $editionId)
    {
        $this->onQueue('news-digest-generate');
    }

    public function uniqueId(): string
    {
        return $this->editionId;
    }

    public function retryUntil(): \DateTimeInterface
    {
        return DigestEdition::query()->find($this->editionId)?->deadline_at ?? now()->addMinute();
    }

    public function handle(DigestGenerator $generator): void
    {
        $lock = Cache::lock('digest-generation:'.$this->editionId, 210);
        if (! $lock->get()) {
            $this->release(10);

            return;
        }
        try {
            $delay = $generator->generate($this->editionId);
            if ($delay !== null) {
                $this->release($delay);
            }
        } finally {
            $lock->release();
        }
    }
}
