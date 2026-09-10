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
    'horizon_allowed_ips' => array_values(array_filter(array_map(
        'trim',
        explode(',', (string) env('HORIZON_ALLOWED_IPS', '127.0.0.1,::1')),
    ))),
];
