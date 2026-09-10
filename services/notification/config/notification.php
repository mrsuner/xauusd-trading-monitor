<?php

$languages = array_values(array_filter(array_map(
    'trim',
    explode(',', (string) env('NOTIFICATION_SUPPORTED_LANGUAGES', 'zh-Hant,en')),
)));

return [
    'enabled' => (bool) env('NOTIFICATION_ENABLED', false),
    'dry_run' => (bool) env('NOTIFICATION_DRY_RUN', true),
    'supported_languages' => $languages,
    'default_language' => env('NOTIFICATION_DEFAULT_LANGUAGE', 'zh-Hant'),
    'initial_paid_cap' => (int) env('NOTIFICATION_INITIAL_PAID_CAP', 100),
    'channel_fingerprint_key' => env('NOTIFICATION_CHANNEL_FINGERPRINT_KEY'),
    'telegram' => [
        'bot_token' => env('TELEGRAM_BOT_TOKEN'),
        'bot_username' => env('TELEGRAM_BOT_USERNAME'),
        'link_ttl_minutes' => 10,
    ],
    'account' => [
        'base_url' => env('ACCOUNT_INTERNAL_URL'),
        'secret' => env('NEWS_INTERNAL_SECRET'),
        'access_cache_seconds' => 60,
    ],
    'scan' => [
        'interval_seconds' => 10,
        'batch_size' => 100,
        'freshness_minutes' => 60,
        'future_tolerance_minutes' => 5,
    ],
    'horizon_allowed_ips' => array_values(array_filter(array_map(
        'trim',
        explode(',', (string) env('HORIZON_ALLOWED_IPS', '127.0.0.1,::1')),
    ))),
];
