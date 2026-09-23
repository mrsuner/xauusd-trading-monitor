<?php

namespace App\Services\Digests;

use App\Models\DigestBatch;
use App\Models\DigestEdition;

class DigestMessageFormatter
{
    public function format(DigestBatch $batch): string
    {
        $parts = [($batch->content_language === 'zh-Hant' ? '每日新聞摘要' : 'Daily News Digest').' · '.$batch->window_start->format('Y-m-d')];
        foreach ($batch->editions->sortBy('topic') as $edition) {
            /** @var DigestEdition $edition */
            $translation = $edition->translations->first();
            if ($translation === null) {
                continue;
            }
            $url = rtrim((string) config('notification.public_origin'), '/')
                .'/'.$batch->content_language.'/digests/'.$edition->id;
            $parts[] = $translation->title."\n".$translation->overview."\n".$url;
        }
        if ($batch->error_code === 'partial_coverage') {
            $parts[] = $batch->content_language === 'zh-Hant'
                ? '部分所選主題未能在發布期限前完成。'
                : 'Some selected topics were unavailable by the publication deadline.';
        }

        return mb_substr(implode("\n\n", $parts), 0, 3900);
    }
}
