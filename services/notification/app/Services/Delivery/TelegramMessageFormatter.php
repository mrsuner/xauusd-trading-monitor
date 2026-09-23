<?php

namespace App\Services\Delivery;

use App\ValueObjects\ContentSelection;
use App\ValueObjects\PublicEventData;

class TelegramMessageFormatter
{
    public function format(PublicEventData $event, ContentSelection $content, string $requestedLanguage): string
    {
        $heading = $requestedLanguage === 'zh-Hant' ? '即時新聞' : 'News alert';
        $fallback = $content->isFallback
            ? ($requestedLanguage === 'zh-Hant'
                ? "翻譯暫時無法使用（內容語言：{$content->language}）\n\n"
                : "Translation temporarily unavailable (content language: {$content->language})\n\n")
            : '';
        $origin = rtrim((string) config('notification.public_origin'), '/');
        $url = $origin.'/events/'.$event->id;
        $prefix = "{$event->severity} · {$heading}\n\n{$fallback}";
        $suffix = "\n\n{$url}";
        $available = max(0, 3500 - mb_strlen($prefix.$suffix));
        $summary = mb_substr($content->summary, 0, $available);

        return $prefix.$summary.$suffix;
    }
}
