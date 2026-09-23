<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class VerifyInternalSecret
{
    /** @param Closure(Request): Response $next */
    public function handle(Request $request, Closure $next): Response
    {
        $expected = (string) config('services.notification_internal.secret');
        $provided = (string) $request->header('X-Internal-Secret', '');

        if ($expected === '' || ! hash_equals($expected, $provided)) {
            return response()->json([
                'error' => 'unauthorized',
                'message' => 'Invalid internal service credentials.',
            ], 401);
        }

        return $next($request);
    }
}
