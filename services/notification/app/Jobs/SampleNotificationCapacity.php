<?php

namespace App\Jobs;

use App\Services\Delivery\CapacityReporter;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

class SampleNotificationCapacity implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $uniqueFor = 55;

    public function __construct()
    {
        $this->onQueue('news-match');
    }

    public function handle(CapacityReporter $capacity): void
    {
        $capacity->report();
    }
}
