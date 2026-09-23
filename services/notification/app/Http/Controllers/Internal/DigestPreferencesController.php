<?php

namespace App\Http\Controllers\Internal;

use App\Exceptions\PreferenceException;
use App\Http\Controllers\ApiController;
use App\Http\Requests\Internal\ReplaceDigestPreferencesRequest;
use App\Services\Digests\DigestPreferencesService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class DigestPreferencesController extends ApiController
{
    public function __construct(private DigestPreferencesService $preferences) {}

    public function show(Request $request, string $accountUserId): JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }

        return $this->data([
            'access' => $this->active($request) ? 'active' : 'upgrade_required',
            'preferences' => $this->preferences->get($accountUserId),
            'available_topics' => config('notification.digest.topics', []),
        ])->header('Cache-Control', 'private, no-store');
    }

    public function update(
        ReplaceDigestPreferencesRequest $request,
        string $accountUserId,
    ): JsonResponse {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }
        try {
            $preferences = $this->preferences->replace(
                $accountUserId,
                $request->boolean('enabled'),
                $request->validated('topics'),
                $this->active($request),
            );
        } catch (PreferenceException $exception) {
            return $this->error($exception->errorCode, $exception->getMessage(), $exception->httpStatus);
        }

        return $this->data(['preferences' => $preferences])
            ->header('Cache-Control', 'private, no-store');
    }

    private function active(Request $request): bool
    {
        return hash_equals('active', (string) $request->header('X-News-Access', ''));
    }
}
