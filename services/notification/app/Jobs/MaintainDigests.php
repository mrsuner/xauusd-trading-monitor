<?php

namespace App\Jobs;

use App\Services\Digests\DigestMaintenance;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

class MaintainDigests implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $uniqueFor = 55;

    public function __construct()
    {
        $this->onQueue('news-digest-deliver');
    }

    public function handle(DigestMaintenance $maintenance): void
    {
        $maintenance->run();
    }
}
