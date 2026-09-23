<?php

namespace App\Jobs;

use App\Services\Digests\DigestEditionFreezer;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

class FreezeDailyDigests implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $uniqueFor = 3600;

    public function __construct()
    {
        $this->onQueue('news-digest-generate');
    }

    public function handle(DigestEditionFreezer $freezer): void
    {
        $freezer->freezePreviousDay();
    }
}
