<?php

namespace App\Http\Controllers\Internal;

use App\Exceptions\PreferenceException;
use App\Http\Controllers\ApiController;
use App\Http\Requests\Internal\ReplacePreferencesRequest;
use App\Services\Preferences\PreferencesService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class PreferencesController extends ApiController
{
    public function __construct(private PreferencesService $preferences) {}

    public function show(Request $request, string $accountUserId): JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }

        $access = $this->access($request);

        return $this->data([
            'access' => $access ? 'active' : 'upgrade_required',
            'preferences' => $this->preferences->get($accountUserId),
        ])->header('Cache-Control', 'private, no-store');
    }

    public function update(ReplacePreferencesRequest $request, string $accountUserId): JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }

        try {
            $preferences = $this->preferences->replace(
                $accountUserId,
                $request->validated(),
                $this->access($request),
            );
        } catch (PreferenceException $exception) {
            $body = ['error' => $exception->errorCode, 'message' => $exception->getMessage()];
            if ($exception->fields !== []) {
                $body['fields'] = $exception->fields;
            }

            return response()->json($body, $exception->httpStatus);
        }

        return $this->data(['preferences' => $preferences])
            ->header('Cache-Control', 'private, no-store');
    }

    private function access(Request $request): bool
    {
        return hash_equals('active', (string) $request->header('X-News-Access', ''));
    }
}
