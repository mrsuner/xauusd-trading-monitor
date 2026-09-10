<?php

namespace App\Http\Controllers\Internal;

use App\Exceptions\ChannelException;
use App\Http\Controllers\ApiController;
use App\Http\Requests\Internal\UpdateChannelRequest;
use App\Services\Channels\ChannelService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Str;

class ChannelsController extends ApiController
{
    public function __construct(private ChannelService $channels) {}

    public function index(string $accountUserId): JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }

        return $this->data($this->channels->list($accountUserId))
            ->header('Cache-Control', 'private, no-store');
    }

    public function linkTelegram(Request $request, string $accountUserId): JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }
        if ($request->all() !== []) {
            return response()->json([
                'error' => 'validation_failed',
                'message' => 'The request is invalid.',
                'fields' => ['request' => ['The request body must be empty.']],
            ], 422);
        }

        try {
            return $this->data(
                $this->channels->createTelegramLink($accountUserId, $this->access($request)),
                201,
            )->header('Cache-Control', 'private, no-store');
        } catch (ChannelException $exception) {
            return $this->channelError($exception);
        }
    }

    public function update(UpdateChannelRequest $request, string $accountUserId, string $type): JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }

        try {
            return $this->data($this->channels->setEnabled(
                $accountUserId,
                $type,
                (bool) $request->validated('enabled'),
                $this->access($request),
            ));
        } catch (ChannelException $exception) {
            return $this->channelError($exception);
        }
    }

    public function destroy(string $accountUserId, string $type): Response|JsonResponse
    {
        if (! Str::isUlid($accountUserId)) {
            return $this->error('validation_failed', 'The account user id must be a valid ULID.', 422);
        }

        try {
            $this->channels->unlink($accountUserId, $type);
        } catch (ChannelException $exception) {
            return $this->channelError($exception);
        }

        return response()->noContent();
    }

    private function access(Request $request): bool
    {
        return hash_equals('active', (string) $request->header('X-News-Access', ''));
    }

    private function channelError(ChannelException $exception): JsonResponse
    {
        return $this->error($exception->errorCode, $exception->getMessage(), $exception->httpStatus);
    }
}
