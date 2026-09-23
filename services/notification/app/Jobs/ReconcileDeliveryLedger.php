<?php

namespace App\Jobs;

use App\Services\Delivery\LedgerReconciler;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

class ReconcileDeliveryLedger implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $uniqueFor = 55;

    public function __construct()
    {
        $this->onQueue('news-match');
    }

    public function handle(LedgerReconciler $reconciler): void
    {
        $reconciler->reconcile();
    }
}
