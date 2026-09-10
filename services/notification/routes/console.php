<?php

use App\Jobs\ScanPublicEvents;
use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Schedule;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Schedule::job(new ScanPublicEvents)
    ->everyTenSeconds()
    ->withoutOverlapping()
    ->when(fn (): bool => (bool) config('notification.enabled', false));
