import type { OverviewStats, PublicCategory, PublicEvent, PublicRawItem, PublicTag } from "./types";

export const demoEvents: PublicEvent[] = [
  {
    id: "demo-s-fed-001",
    upstream_event_id: "00000000-0000-4000-8000-000000000001",
    idempotency_key: "demo:event:fed:001",
    schema_version: "public_event.v1",
    event_time: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    generated_at: new Date(Date.now() - 11 * 60 * 1000).toISOString(),
    received_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    severity: "S",
    relevance_score: 94,
    confirmation_state: "confirmed",
    title: "Fed rhetoric turns more hawkish",
    summary:
      "Fed-linked remarks emphasized persistent inflation and policy restraint, which may affect rate-cut expectations and XAUUSD sensitivity.",
    language: "en",
    available_languages: ["en", "zh-Hant", "ja"],
    translations: [
      {
        language: "en",
        title: "Fed rhetoric turns more hawkish",
        summary:
          "Fed-linked remarks emphasized persistent inflation and policy restraint, which may affect rate-cut expectations and XAUUSD sensitivity."
      },
      {
        language: "zh-Hant",
        title: "Fed 官員口徑突然轉鷹，金價風險重新定價",
        summary:
          "公開事件流顯示，Fed 相關口徑集中提到通膨韌性與政策限制性，市場對降息路徑的定價可能受到壓力。此摘要僅描述事件與可能傳導路徑，不構成交易建議。"
      },
      {
        language: "ja",
        title: "Fed 発言が一段とタカ派寄りに",
        summary:
          "Fed 関連発言は根強いインフレと政策の制約性を強調しており、利下げ期待と XAUUSD の感応度に影響する可能性があります。"
      }
    ],
    public_title_zh: "Fed 官員口徑突然轉鷹，金價風險重新定價",
    public_summary_zh:
      "公開事件流顯示，Fed 相關口徑集中提到通膨韌性與政策限制性，市場對降息路徑的定價可能受到壓力。此摘要僅描述事件與可能傳導路徑，不構成交易建議。",
    public_title_en: "Fed rhetoric turns more hawkish",
    public_summary_en:
      "Fed-linked remarks emphasized persistent inflation and policy restraint, which may affect rate-cut expectations and XAUUSD sensitivity.",
    public_source_links: [
      { source_name: "Federal Reserve", url: "https://www.federalreserve.gov/newsevents.htm" }
    ],
    topic_tags: ["fed", "rates", "xauusd"],
    content_category: "macro_policy",
    mentioned_actors: ["Federal Reserve", "XAUUSD"],
    route_metadata: { public_route_score: 94, generated_by: "event-router" }
  },
  {
    id: "demo-a-iran-001",
    upstream_event_id: "00000000-0000-4000-8000-000000000002",
    idempotency_key: "demo:event:iran:001",
    schema_version: "public_event.v1",
    event_time: new Date(Date.now() - 48 * 60 * 1000).toISOString(),
    generated_at: new Date(Date.now() - 47 * 60 * 1000).toISOString(),
    received_at: new Date(Date.now() - 46 * 60 * 1000).toISOString(),
    severity: "A",
    relevance_score: 87,
    confirmation_state: "partially_confirmed",
    title: "Iran hardline-adjacent source pushes back on deal narrative",
    summary:
      "Iran hardline-adjacent messaging diverged from optimistic US framing. Further confirmation is needed from official Iranian channels.",
    language: "en",
    available_languages: ["en", "zh-Hant"],
    translations: [
      {
        language: "en",
        title: "Iran hardline-adjacent source pushes back on deal narrative",
        summary:
          "Iran hardline-adjacent messaging diverged from optimistic US framing. Further confirmation is needed from official Iranian channels."
      },
      {
        language: "zh-Hant",
        title: "伊朗強硬派媒體否認談判讓步敘事",
        summary:
          "公開來源出現與美方樂觀敘事不一致的伊朗強硬派口徑。事件仍需等待政府、最高領袖系統或安全系統進一步確認。"
      }
    ],
    public_title_zh: "伊朗強硬派媒體否認談判讓步敘事",
    public_summary_zh:
      "公開來源出現與美方樂觀敘事不一致的伊朗強硬派口徑。事件仍需等待政府、最高領袖系統或安全系統進一步確認。",
    public_title_en: "Iran hardline-adjacent source pushes back on deal narrative",
    public_summary_en:
      "Iran hardline-adjacent messaging diverged from optimistic US framing. Further confirmation is needed from official Iranian channels.",
    public_source_links: [
      { source_name: "Tasnim", url: "https://www.tasnimnews.com/" },
      { source_name: "IRNA", url: "https://en.irna.ir/" }
    ],
    topic_tags: ["iran", "deal", "sanctions"],
    content_category: "geopolitics",
    mentioned_actors: ["Iran", "Trump", "IRGC"],
    route_metadata: { public_route_score: 87, generated_by: "event-router" }
  },
  {
    id: "demo-b-trump-001",
    upstream_event_id: "00000000-0000-4000-8000-000000000003",
    idempotency_key: "demo:event:trump:001",
    schema_version: "public_event.v1",
    event_time: new Date(Date.now() - 92 * 60 * 1000).toISOString(),
    generated_at: new Date(Date.now() - 91 * 60 * 1000).toISOString(),
    received_at: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
    severity: "B",
    relevance_score: 61,
    confirmation_state: "unconfirmed",
    title: "Trump-related source mentions Iran talks",
    summary:
      "A single Trump-related source mentioned progress on Iran talks, without matching confirmation from official diplomatic channels.",
    language: "en",
    available_languages: ["en", "zh-Hant"],
    translations: [
      {
        language: "en",
        title: "Trump-related source mentions Iran talks",
        summary:
          "A single Trump-related source mentioned progress on Iran talks, without matching confirmation from official diplomatic channels."
      },
      {
        language: "zh-Hant",
        title: "Trump 相關來源提及伊朗談判進展",
        summary:
          "單一來源提及談判進展，但尚未看到伊朗官方或美國外交系統同步確認。此類訊息適合列入觀察清單。"
      }
    ],
    public_title_zh: "Trump 相關來源提及伊朗談判進展",
    public_summary_zh:
      "單一來源提及談判進展，但尚未看到伊朗官方或美國外交系統同步確認。此類訊息適合列入觀察清單。",
    public_title_en: "Trump-related source mentions Iran talks",
    public_summary_en:
      "A single Trump-related source mentioned progress on Iran talks, without matching confirmation from official diplomatic channels.",
    public_source_links: [{ source_name: "TrumpsTruth", url: "https://trumpstruth.org/feed" }],
    topic_tags: ["trump", "iran", "watch"],
    content_category: "politics",
    mentioned_actors: ["Trump", "Iran"],
    route_metadata: { public_route_score: 61, generated_by: "event-router" }
  }
];

export const demoTags: PublicTag[] = [
  { tag: "iran", count: 2 },
  { tag: "xauusd", count: 1 },
  { tag: "fed", count: 1 },
  { tag: "trump", count: 1 },
  { tag: "sanctions", count: 1 }
];

export const demoCategories: PublicCategory[] = [
  { category: "geopolitics", count: 1 },
  { category: "macro_policy", count: 1 },
  { category: "politics", count: 1 }
];

export const demoRawItems: PublicRawItem[] = [
  {
    id: "demo-raw-fed-001",
    upstream_raw_item_id: "10000000-0000-4000-8000-000000000001",
    idempotency_key: "demo:raw:fed:001",
    schema_version: "public_raw_item.v1",
    source_name: "Federal Reserve",
    source_type: "rss",
    source_group: "macro",
    official_level: "official",
    priority: "P0",
    source_url: "https://www.federalreserve.gov/newsevents.htm",
    published_at: new Date(Date.now() - 14 * 60 * 1000).toISOString(),
    ingested_at: new Date(Date.now() - 13 * 60 * 1000).toISOString(),
    edited_at: null,
    received_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    title: "Fed remarks emphasize inflation persistence",
    original_content:
      "Federal Reserve remarks emphasized that inflation remains above target and that policy should remain restrictive until confidence improves.",
    source_language: "en",
    media_type: "none",
    summary_zh: "Fed 相關發言強調通膨仍高於目標，政策需要維持限制性直到信心改善。",
    summary_en:
      "Fed-linked remarks emphasized inflation persistence and continued policy restraint until confidence improves.",
    full_translation_zh:
      "Federal Reserve 相關發言強調，通膨仍高於目標，在信心改善以前，政策應保持限制性。這類口徑可能影響市場對降息時點的預期。",
    full_translation_en:
      "Federal Reserve remarks emphasized that inflation remains above target and policy should remain restrictive until confidence improves.",
    summary: "Fed-linked remarks emphasized inflation persistence and continued policy restraint until confidence improves.",
    full_translation:
      "Federal Reserve remarks emphasized that inflation remains above target and policy should remain restrictive until confidence improves.",
    language: "en",
    available_languages: ["en", "zh-Hant"],
    translations: [
      {
        language: "en",
        summary:
          "Fed-linked remarks emphasized inflation persistence and continued policy restraint until confidence improves.",
        full_translation:
          "Federal Reserve remarks emphasized that inflation remains above target and policy should remain restrictive until confidence improves.",
        status: "completed",
        is_truncated: false,
        source_chars: 137,
        translation_chars: 126
      },
      {
        language: "zh-Hant",
        summary: "Fed 相關發言強調通膨仍高於目標，政策需要維持限制性直到信心改善。",
        full_translation:
          "Federal Reserve 相關發言強調，通膨仍高於目標，在信心改善以前，政策應保持限制性。這類口徑可能影響市場對降息時點的預期。",
        status: "completed",
        is_truncated: false,
        source_chars: 137,
        translation_chars: 62
      }
    ],
    content_category: "macro_policy",
    topic_tags: ["fed", "rates", "xauusd"],
    mentioned_actors: ["Federal Reserve", "XAUUSD"],
    upstream_event_ids: [demoEvents[0].upstream_event_id],
    is_relevant: true,
    relevance_score: 91,
    filter_reason: null,
    classification_stage: "completed",
    classification_status: "completed",
    is_truncated: false,
    source_text_chars: 137,
    translation_chars: 126,
    scrub_metadata: { source: "raw_items" }
  },
  {
    id: "demo-raw-iran-001",
    upstream_raw_item_id: "10000000-0000-4000-8000-000000000002",
    idempotency_key: "demo:raw:iran:001",
    schema_version: "public_raw_item.v1",
    source_name: "Tasnim",
    source_type: "telegram",
    source_group: "geopolitics",
    official_level: "semi_official",
    priority: "P1",
    source_url: "https://www.tasnimnews.com/",
    published_at: new Date(Date.now() - 52 * 60 * 1000).toISOString(),
    ingested_at: new Date(Date.now() - 51 * 60 * 1000).toISOString(),
    edited_at: null,
    received_at: new Date(Date.now() - 50 * 60 * 1000).toISOString(),
    title: "Iran hardline-adjacent outlet disputes deal optimism",
    original_content:
      "A hardline-adjacent Iranian outlet pushed back on optimistic external framing around talks, saying key conditions remain unresolved.",
    source_language: "en",
    media_type: "none",
    summary_zh: "伊朗強硬派相近媒體否認外部樂觀談判敘事，稱關鍵條件仍未解決。",
    summary_en:
      "Iran hardline-adjacent messaging pushed back on optimistic external framing around talks.",
    full_translation_zh:
      "伊朗強硬派相近媒體對外部關於談判的樂觀敘事提出反駁，表示關鍵條件仍未解決。此類消息需等待官方渠道進一步確認。",
    full_translation_en:
      "A hardline-adjacent Iranian outlet pushed back on optimistic external framing around talks, saying key conditions remain unresolved.",
    summary: "Iran hardline-adjacent messaging pushed back on optimistic external framing around talks.",
    full_translation:
      "A hardline-adjacent Iranian outlet pushed back on optimistic external framing around talks, saying key conditions remain unresolved.",
    language: "en",
    available_languages: ["en", "zh-Hant"],
    translations: [],
    content_category: "geopolitics",
    topic_tags: ["iran", "deal", "sanctions"],
    mentioned_actors: ["Iran"],
    upstream_event_ids: [demoEvents[1].upstream_event_id],
    is_relevant: true,
    relevance_score: 83,
    filter_reason: null,
    classification_stage: "completed",
    classification_status: "completed",
    is_truncated: false,
    source_text_chars: 126,
    translation_chars: 126,
    scrub_metadata: { source: "raw_items" }
  }
];

export const demoStats: OverviewStats = {
  total_events: 3,
  s_events: 1,
  a_events: 1,
  latest_event_time: demoEvents[0].event_time
};
