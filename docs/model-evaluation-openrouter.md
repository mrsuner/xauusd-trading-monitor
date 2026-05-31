# OpenRouter 摘要與翻譯模型測試 Prompt

本文件用於比較 OpenRouter free / cheap models 是否適合 `normalizer-classifier` 的輔助摘要與翻譯任務。

V1 判斷原則：

- 核心分類仍使用 `gpt-5.4-mini`。
- OpenRouter free / cheap models 只用於 `summary_zh`、`translation_zh`、低風險文字整理。
- 測試時重點觀察 JSON 穩定性、繁體中文品質、翻譯忠實度、是否加入原文沒有的推論。

## 1. System Prompt

```text
You summarize and translate news items for an XAUUSD event radar.

Return only valid JSON. Do not wrap the JSON in Markdown.
Use Traditional Chinese for all Chinese output.

You must not provide trading instructions, entries, stop loss, take profit, position sizing, buy, sell, long, short, bullish, or bearish recommendations.
You must not predict market direction.
You must not add facts that are not present in the input.

summary_zh must be a concise Traditional Chinese news summary, preferably under 90 Chinese characters.

If the source text is not Chinese, translation_zh should be a faithful Traditional Chinese translation of the key content, preferably under 500 Chinese characters.
If the source text is already Chinese, translation_zh should be null.

Preserve names, places, institutions, numbers, dates, source uncertainty, and quoted claims.
If the text is rumor-like or unconfirmed, say so clearly.

Return this exact JSON shape:
{
  "summary_zh": "string",
  "translation_zh": "string|null",
  "detected_language": "string|null",
  "notes": "string|null"
}
```

## 2. User Prompt

```json
{
  "source": {
    "name": "Tasnim News",
    "source_type": "telegram",
    "source_group": "iran_irgc_adjacent",
    "official_level": "semi_official",
    "priority": "P0",
    "stance": "IRGC-linked / hardline-adjacent"
  },
  "raw_item": {
    "title": "Iran nuclear talks",
    "text_clean": "Tasnim reports that Iranian officials rejected claims that Tehran has agreed to abandon uranium enrichment, saying any agreement must preserve Iran's nuclear rights and remove sanctions.",
    "language": "en",
    "url": "https://example.test/tasnim/iran-nuclear-talks",
    "published_at": "2026-05-31T08:12:00Z"
  }
}
```

## 3. 追加測試樣本

### 3.1 Trump / Deal Optimism

```json
{
  "source": {
    "name": "Trump Truth Social Tracker",
    "source_type": "telegram",
    "source_group": "us_trump",
    "official_level": "unofficial_mirror",
    "priority": "P0",
    "stance": "third-party mirror of Trump posts"
  },
  "raw_item": {
    "title": null,
    "text_clean": "President Trump: We are very close to a historic deal with Iran. Final details are being worked out. No one wants war.",
    "language": "en",
    "url": "https://truthsocial.com/@realDonaldTrump/posts/example",
    "published_at": "2026-05-31T09:30:00Z"
  }
}
```

### 3.2 Fed Speaker

```json
{
  "source": {
    "name": "Federal Reserve",
    "source_type": "rss",
    "source_group": "us_fed",
    "official_level": "official",
    "priority": "P0",
    "stance": "US central bank"
  },
  "raw_item": {
    "title": "Speech by Chair Powell",
    "text_clean": "Inflation remains somewhat elevated, and the Committee is not in a hurry to adjust the policy stance while upside risks to inflation persist.",
    "language": "en",
    "url": "https://www.federalreserve.gov/newsevents/speech/example.htm",
    "published_at": "2026-05-31T14:00:00Z"
  }
}
```

### 3.3 Persian Text

```json
{
  "source": {
    "name": "Sepah News",
    "source_type": "rss",
    "source_group": "iran_irgc_official",
    "official_level": "official",
    "priority": "P0",
    "stance": "IRGC official public relations"
  },
  "raw_item": {
    "title": "هشدار درباره هرگونه اقدام دشمن",
    "text_clean": "سپاه پاسداران اعلام کرد هرگونه اقدام دشمن علیه امنیت ایران با پاسخ قاطع و فوری مواجه خواهد شد.",
    "language": "fa",
    "url": "https://example.test/sepah/news",
    "published_at": "2026-05-31T10:45:00Z"
  }
}
```

## 4. 評分標準

| 項目 | 合格標準 |
| --- | --- |
| JSON 格式 | 可直接 `json.loads`，沒有 Markdown fence |
| 繁中摘要 | `summary_zh` 自然、簡短、沒有簡體字 |
| 翻譯忠實度 | 不擴寫、不加入交易解讀、不改變不確定語氣 |
| 名詞保留 | Trump、Tasnim、Fed、IRGC、uranium enrichment 等核心名詞不混淆 |
| 風險控制 | 不輸出交易方向或建議 |
| 延遲 | 單條樣本最好低於 3 秒，可接受低於 6 秒 |

## 5. 預期輸出範例

```json
{
  "summary_zh": "Tasnim 稱伊朗否認已同意放棄濃縮鈾。",
  "translation_zh": "Tasnim 報導稱，伊朗官員否認德黑蘭已同意放棄濃縮鈾的說法，並表示任何協議都必須保留伊朗的核權利並解除制裁。",
  "detected_language": "en",
  "notes": "消息來自半官方、強硬派相關來源；未加入交易方向判斷。"
}
```
