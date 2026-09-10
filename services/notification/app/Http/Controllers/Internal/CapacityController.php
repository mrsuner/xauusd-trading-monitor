<?php

namespace App\Http\Controllers\Internal;

use App\Http\Controllers\ApiController;
use App\Services\Delivery\CapacityReporter;
use Illuminate\Http\JsonResponse;

class CapacityController extends ApiController
{
    public function __invoke(CapacityReporter $capacity): JsonResponse
    {
        return $this->data($capacity->report())
            ->header('Cache-Control', 'private, no-store');
    }
}
