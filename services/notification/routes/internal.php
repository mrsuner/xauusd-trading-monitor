<?php

use App\Http\Controllers\Internal\PreferencesController;
use Illuminate\Support\Facades\Route;

Route::get('users/{accountUserId}/preferences', [PreferencesController::class, 'show']);
Route::put('users/{accountUserId}/preferences', [PreferencesController::class, 'update']);
