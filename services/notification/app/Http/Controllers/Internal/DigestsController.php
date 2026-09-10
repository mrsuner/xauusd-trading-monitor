<?php

namespace App\Http\Controllers\Internal;

use App\Http\Controllers\ApiController;
use App\Services\Digests\DigestReader;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;

class DigestsController extends ApiController
{
    public function __construct(private DigestReader $digests) {}

    public function index(Request $request, string $accountUserId): JsonResponse
    {
        if (($error = $this->authorizeRead($request, $accountUserId)) !== null) {
            return $error;
        }
        $validated = $request->validate([
            'language' => ['required', Rule::in(config('notification.supported_languages', []))],
        ]);

        return $this->data($this->digests->list($validated['language']))
            ->header('Cache-Control', 'private, no-store');
    }

    public function show(Request $request, string $accountUserId, string $editionId): JsonResponse
    {
        if (($error = $this->authorizeRead($request, $accountUserId)) !== null) {
            return $error;
        }
        if (! Str::isUuid($editionId)) {
            return $this->error('validation_failed', 'The edition id must be a valid UUID.', 422);
        }
        $validated = $request->validate([
            'language' => ['required', Rule::in(config('notification.supported_languages', []))],
        ]);
        $digest = $this->digests->find($editionId, $validated['language']);
        if ($digest === null) {
            return $this->error('not_found', 'Digest edition not found.', 404);
        }

        return $this->data($digest)->header('Cache-Control', 'private, no-store');
    }

    private function authorizeRead(Request $request, string $accountUserId): ?JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }
        if (! hash_equals('active', (string) $request->header('X-News-Access', ''))) {
            return $this->error('upgrade_required', 'An active News subscription is required.', 403);
        }

        return null;
    }
}
