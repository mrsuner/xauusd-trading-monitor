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
    'admission_enabled' => (bool) env('NOTIFICATION_ADMISSION_ENABLED', false),
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
    'public_origin' => env('NEWS_PUBLIC_ORIGIN', 'https://news.thetickbase.com'),
    'delivery' => [
        'max_provider_attempts' => 5,
        'lock_seconds' => 45,
        'dispatch_stale_seconds' => 120,
        'http_backoff_seconds' => [30, 120, 300, 600],
    ],
    'digest' => [
        'enabled' => (bool) env('DIGEST_ENABLED', false),
        'topics' => ['geopolitics', 'monetary', 'energy', 'macro_data'],
        'retention_days' => 90,
        'input_limit' => 20,
        'freeze_minute' => 15,
        'deadline_minute' => 60,
        'prompt_version' => 'shared-digest.v1',
        'limits' => [
            'title_chars' => 180,
            'overview_chars' => 2000,
            'development_chars' => 1000,
            'developments' => 12,
        ],
        'model' => [
            'provider' => env('DIGEST_MODEL_PROVIDER', 'openrouter'),
            'base_url' => env('DIGEST_MODEL_BASE_URL', 'https://openrouter.ai/api/v1'),
            'api_key' => env('DIGEST_MODEL_API_KEY'),
            'name' => env('DIGEST_MODEL_NAME'),
            'timeout_seconds' => (int) env('DIGEST_MODEL_TIMEOUT_SECONDS', 60),
            'max_output_tokens' => (int) env('DIGEST_MODEL_MAX_OUTPUT_TOKENS', 1800),
        ],
    ],
    'horizon_allowed_ips' => array_values(array_filter(array_map(
        'trim',
        explode(',', (string) env('HORIZON_ALLOWED_IPS', '127.0.0.1,::1')),
    ))),
];
