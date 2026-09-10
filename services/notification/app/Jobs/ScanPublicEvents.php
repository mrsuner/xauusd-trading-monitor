<?php

namespace App\Jobs;

use App\Services\Delivery\EventScanner;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

class ScanPublicEvents implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $uniqueFor = 9;

    public function __construct()
    {
        $this->onQueue('news-match');
    }

    public function handle(EventScanner $scanner): void
    {
        $scanner->scan();
    }
}
