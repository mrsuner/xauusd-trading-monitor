<?php

use App\Http\Controllers\Internal\CapacityController;
use App\Http\Controllers\Internal\ChannelsController;
use App\Http\Controllers\Internal\DigestPreferencesController;
use App\Http\Controllers\Internal\DigestsController;
use App\Http\Controllers\Internal\PreferencesController;
use Illuminate\Support\Facades\Route;

Route::get('users/{accountUserId}/preferences', [PreferencesController::class, 'show']);
Route::put('users/{accountUserId}/preferences', [PreferencesController::class, 'update']);
Route::get('users/{accountUserId}/channels', [ChannelsController::class, 'index']);
Route::post('users/{accountUserId}/channels/telegram/link', [ChannelsController::class, 'linkTelegram']);
Route::patch('users/{accountUserId}/channels/{type}', [ChannelsController::class, 'update']);
Route::delete('users/{accountUserId}/channels/{type}', [ChannelsController::class, 'destroy']);
Route::get('capacity', CapacityController::class);
Route::get('users/{accountUserId}/digest-preferences', [DigestPreferencesController::class, 'show']);
Route::put('users/{accountUserId}/digest-preferences', [DigestPreferencesController::class, 'update']);
Route::get('users/{accountUserId}/digests', [DigestsController::class, 'index']);
Route::get('users/{accountUserId}/digests/{editionId}', [DigestsController::class, 'show']);
