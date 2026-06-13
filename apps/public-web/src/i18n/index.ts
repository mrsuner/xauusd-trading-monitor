import { useLocation, useParams } from "react-router-dom";
import type { ConfirmationState } from "../api/types";

export type UiLanguage = "en" | "zh-Hant";

export const defaultLanguage: UiLanguage = "en";
export const supportedLanguages: UiLanguage[] = ["en", "zh-Hant"];

export const languageLabels: Record<UiLanguage, string> = {
  en: "EN",
  "zh-Hant": "繁中"
};

const en = {
  nav: {
    latest: "Latest",
    raw: "Raw Feed",
    highImpact: "High Impact",
    tags: "Tags",
    about: "About",
    status: "Status",
    language: "Language",
    tickbaseHome: "TickBase News home",
    toggleTheme: "Toggle theme"
  },
  footer: {
    summary: "Public event radar for market-moving macro, gold, geopolitics, energy, and policy news. Not investment advice.",
    explore: "Explore",
    latestEvents: "Latest events",
    rawFeed: "Raw feed",
    methodology: "Methodology",
    apiStatus: "API status",
    dataBoundary: "Data Boundary",
    dataBoundaryBody:
      "This site only displays public-safe summaries and source attribution. Internal raw items, prompts, usage cost, sessions, and private delivery states are not published."
  },
  events: {
    eyebrow: "Public event radar",
    title: "TickBase News",
    body:
      "A public-safe event stream focused on XAUUSD, the Fed, Trump, Iran, the IRGC, energy, and geopolitical risk. It tracks source confirmation state and does not provide trading advice.",
    filters: "Filters",
    searchPlaceholder: "Search public summaries",
    search: "Search",
    allSeverity: "All severity",
    allConfirmation: "All confirmation",
    allCategories: "All categories",
    allTags: "All tags",
    ariaSeverity: "Severity",
    ariaConfirmation: "Confirmation state",
    ariaCategory: "Category",
    ariaTag: "Tag",
    severityOptions: {
      S: "S - highest public priority",
      A: "A - high public priority",
      B: "B - watch",
      C: "C - context"
    },
    confirmationOptions: {
      confirmed: "confirmed",
      partially_confirmed: "partially confirmed",
      unconfirmed: "unconfirmed",
      contradicted: "contradicted"
    } satisfies Record<ConfirmationState, string>,
    emptyTitle: "No public events match these filters",
    emptyBody: "Adjust severity, category, tag, or search text. The public website only shows approved public-safe events.",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `Showing page ${current} of ${totalPages}, ${total} public events.`,
    previousPage: "Previous page",
    nextPage: "Next page",
    reset: "Reset"
  },
  raw: {
    eyebrow: "Public raw feed",
    title: "Raw Source Feed",
    body:
      "Public-safe source items synchronized independently from event summaries. Each item shows cleaned original content and available full translation.",
    filters: "Filters",
    searchPlaceholder: "Search raw source items",
    search: "Search",
    allSourceTypes: "All source types",
    allCategories: "All categories",
    allTags: "All tags",
    ariaSourceType: "Source type",
    ariaCategory: "Category",
    ariaTag: "Tag",
    emptyTitle: "No raw source items match these filters",
    emptyBody: "Adjust source type, category, tag, or search text.",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `Showing page ${current} of ${totalPages}, ${total} raw source items.`,
    previousPage: "Previous page",
    nextPage: "Next page",
    reset: "Reset",
    sourceFallback: "Public source",
    sourceType: "Source type",
    originalContent: "Original Content",
    fullTranslation: "Full Translation",
    summary: "Summary",
    noOriginalContent: "No original content is available.",
    noFullTranslation: "No full translation is available.",
    relevance: "Relevance",
    supportingItems: "Supporting raw items",
    noSupportingItems: "No supporting raw items are linked to this event yet.",
    viewRawItem: "View raw item"
  },
  detail: {
    eyebrow: "Public event detail",
    missingIdTitle: "Event id is missing",
    missingIdBody: "Return to the event list and reopen the public event.",
    loading: "Loading event detail...",
    notFoundTitle: "Event not found",
    notFoundBody: "This public event does not exist or has been hidden.",
    eventTime: "Event time:",
    category: "Category:",
    summaryTitle: "Public Summary",
    boundary:
      "This page only includes public-safe summaries and source attribution. It does not include raw item text, private delivery state, prompts, or model usage data.",
    sources: "Sources",
    noSources: "No public source links available.",
    source: "Source",
    tagsActors: "Tags & Actors"
  },
  tag: {
    eyebrow: "Topic tag",
    fallbackTitle: "unknown",
    body: "Public events grouped by topic tag. Tags come from public-safe taxonomy in the event processing pipeline.",
    emptyTitle: "No public events for this tag yet",
    emptyBody: "Future synced events will appear here automatically."
  },
  about: {
    eyebrow: "About",
    title: "Market-moving news, structured for verification",
    body:
      "TickBase News is the public outlet of XAUUSD Event Radar. It only shows approved public-safe event summaries, severity, confirmation state, and source attribution.",
    sections: [
      {
        title: "System Role",
        body:
          "This site is not a trading signal service. It organizes sources with different viewpoints, speeds, and authority levels into a traceable public event stream, helping readers understand whether a claim has official confirmation, whether contradictory narratives exist, and how public narratives may affect markets."
      },
      {
        title: "Event Severity",
        body:
          "Severity reflects relative importance in the system rules and model workflow. S and A events deserve higher reading priority, but they do not imply trade direction or guarantee gold-price impact."
      },
      {
        title: "Severity Levels",
        body:
          "S marks top-priority events with direct market-moving potential or major policy/geopolitical implications. A marks important events that deserve timely review. B marks watch items with useful but lower-priority signal value. C marks context items that help explain the narrative background."
      },
      {
        title: "Confirmation State",
        body:
          "confirmed, partially confirmed, unconfirmed, and contradicted describe the degree of source confirmation. Unconfirmed events should be treated as watch items, not factual conclusions."
      },
      {
        title: "Source Background",
        body:
          "Source labels may include short background notes. These notes describe the public role or common editorial context of a source; they are not endorsements, credibility scores, or a substitute for reading the linked source."
      },
      {
        title: "Data Boundary",
        body:
          "The public website does not store HomeLab raw item text, AI prompts, token usage, private notification records, Telegram sessions, or internal management data. All content is generated through the public sync flow."
      },
      {
        title: "Disclaimer",
        body: "This website is for information and research only. It is not investment, trading, legal, or financial advice."
      }
    ]
  },
  status: {
    eyebrow: "Status",
    title: "Public API Status",
    body: "The public website depends only on the VPS public-api. This page shows basic health for the public API and public database.",
    loading: "Checking public API...",
    api: "API",
    database: "database",
    unknown: "unknown"
  },
  states: {
    loading: "Loading public events...",
    apiErrorTitle: "Public API is temporarily unavailable"
  },
  stats: {
    publicEvents: "Public events",
    sSeverity: "S severity",
    aSeverity: "A severity",
    latest: "Latest"
  },
  badges: {
    unknown: "unknown",
    severityDescriptions: {
      S: "Top-priority public event. Usually direct policy, geopolitical, market-structure, or high-impact gold/macro relevance.",
      A: "Important public event. Worth timely review, but with less immediate priority than S.",
      B: "Watch item. Useful signal or narrative movement, but lower confidence or lower market priority.",
      C: "Context item. Background information that helps explain the broader public narrative."
    },
    confirmation: {
      confirmed: "confirmed",
      partially_confirmed: "partially confirmed",
      unconfirmed: "unconfirmed",
      contradicted: "contradicted"
    } satisfies Record<ConfirmationState, string>,
    confirmationDescriptions: {
      confirmed: "Supported by official or multiple high-quality public sources.",
      partially_confirmed: "Some supporting evidence exists, but key details still need stronger confirmation.",
      unconfirmed: "Single-source, early, or insufficiently corroborated. Treat as a watch item.",
      contradicted: "Public sources conflict or later reporting disputes the claim."
    } satisfies Record<ConfirmationState, string>
  },
  sources: {
    fallback:
      "Public source link. Consider the source role, publication context, and whether other sources confirm the claim.",
    backgrounds: {
      "Federal Reserve":
        "Official US central bank source. Highest authority for Fed decisions, speeches, minutes, and policy communications.",
      "White House":
        "Official US executive branch source. Useful for administration positions, but political framing should be expected.",
      "Reuters":
        "Global wire service with institutional market readership. Often fast and broadly syndicated; still compare with primary sources for policy claims.",
      "AP":
        "Global wire service focused on broad news coverage. Useful for baseline reporting and cross-checking developing stories.",
      "Bloomberg":
        "Financial news service with strong market focus. Useful for market reaction and policy reporting; some content may rely on unnamed sources.",
      "Tasnim":
        "Iranian outlet commonly associated with conservative or IRGC-adjacent perspectives. Useful for Iranian hardline framing, not a neutral official statement.",
      "Press TV":
        "Iranian state-funded international broadcaster. Useful for official or state-aligned Iranian framing, especially in external-facing English coverage.",
      "IRNA":
        "Iran's state news agency. Useful for official Iranian government messaging and formal state framing.",
      "Mehr News":
        "Iranian semi-official news agency. Useful for domestic Iranian political and policy framing, but should be cross-checked on sensitive claims.",
      "US State Department":
        "Official US foreign-policy source. High authority for US diplomatic positions, sanctions notices, and official statements.",
      "IDF Official":
        "Official Israel Defense Forces source. High authority for IDF statements and operational claims, but represents a military actor's position.",
      "Khamenei English":
        "Official English-language channel for Iran's Supreme Leader. Useful for formal leadership messaging and ideological framing.",
      "Trump Truth Social":
        "Trump-aligned direct political messaging source. Useful for primary statements from Trump, but factual claims need independent confirmation.",
      "TrumpsTruth":
        "Trump-aligned social/media feed. Useful for direct political messaging, but claims need independent confirmation."
    } satisfies Record<string, string>
  },
  format: {
    untitled: "Untitled public event",
    untitledRawItem: "Untitled raw item",
    noSummary: "No public summary is available.",
    noRawSummary: "No public raw summary is available.",
    timeUnknown: "Time unknown",
    unscored: "Unscored",
    high: "High",
    watch: "Watch",
    info: "Info",
    uncategorized: "uncategorized"
  }
};

const zhHant: typeof en = {
  nav: {
    latest: "最新",
    raw: "原始 feed",
    highImpact: "高影響",
    tags: "標籤",
    about: "關於",
    status: "狀態",
    language: "語言",
    tickbaseHome: "TickBase News 首頁",
    toggleTheme: "切換主題"
  },
  footer: {
    summary: "追蹤可能影響市場的宏觀、黃金、地緣政治、能源與政策事件。內容不構成投資建議。",
    explore: "瀏覽",
    latestEvents: "最新事件",
    rawFeed: "原始 feed",
    methodology: "方法說明",
    apiStatus: "API 狀態",
    dataBoundary: "資料邊界",
    dataBoundaryBody:
      "本站只顯示 public-safe 摘要與來源歸屬，不發布內部 raw item、prompt、usage cost、session 或私人通知狀態。"
  },
  events: {
    eyebrow: "公開事件雷達",
    title: "TickBase News",
    body:
      "去敏後的公開事件流，聚焦 XAUUSD、Fed、Trump、Iran、IRGC、能源與地緣風險。內容用於追蹤消息與來源確認狀態，不提供交易建議。",
    filters: "篩選",
    searchPlaceholder: "搜尋公開摘要",
    search: "搜尋",
    allSeverity: "全部分級",
    allConfirmation: "全部確認狀態",
    allCategories: "全部分類",
    allTags: "全部標籤",
    ariaSeverity: "分級",
    ariaConfirmation: "確認狀態",
    ariaCategory: "分類",
    ariaTag: "標籤",
    severityOptions: {
      S: "S - 最高公開優先級",
      A: "A - 高公開優先級",
      B: "B - 觀察",
      C: "C - 背景"
    },
    confirmationOptions: {
      confirmed: "已確認",
      partially_confirmed: "部分確認",
      unconfirmed: "未確認",
      contradicted: "有相反口徑"
    },
    emptyTitle: "沒有符合條件的公開事件",
    emptyBody: "請調整 severity、category、tag 或搜尋字串。公開網站只顯示已核准同步的 public-safe events。",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `第 ${current} / ${totalPages} 頁，共 ${total} 筆公開事件。`,
    previousPage: "上一頁",
    nextPage: "下一頁",
    reset: "重設"
  },
  raw: {
    eyebrow: "公開原始資料源",
    title: "Raw Source Feed",
    body: "獨立於事件摘要同步的 public-safe source items。每筆資料顯示清洗後原文與可用全文翻譯。",
    filters: "篩選",
    searchPlaceholder: "搜尋原始資料源",
    search: "搜尋",
    allSourceTypes: "全部來源類型",
    allCategories: "全部分類",
    allTags: "全部標籤",
    ariaSourceType: "來源類型",
    ariaCategory: "分類",
    ariaTag: "標籤",
    emptyTitle: "沒有符合條件的原始資料",
    emptyBody: "請調整來源類型、分類、標籤或搜尋字串。",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `第 ${current} / ${totalPages} 頁，共 ${total} 筆原始資料。`,
    previousPage: "上一頁",
    nextPage: "下一頁",
    reset: "重設",
    sourceFallback: "公開來源",
    sourceType: "來源類型",
    originalContent: "原文",
    fullTranslation: "全文翻譯",
    summary: "摘要",
    noOriginalContent: "目前沒有可顯示的原文。",
    noFullTranslation: "目前沒有可顯示的全文翻譯。",
    relevance: "相關度",
    supportingItems: "相關原始資料",
    noSupportingItems: "此事件尚未連結相關原始資料。",
    viewRawItem: "查看原始資料"
  },
  detail: {
    eyebrow: "公開事件詳情",
    missingIdTitle: "缺少 event id",
    missingIdBody: "請回到事件列表重新開啟公開事件。",
    loading: "正在載入事件詳情...",
    notFoundTitle: "找不到事件",
    notFoundBody: "這筆公開事件不存在，或已被隱藏。",
    eventTime: "事件時間：",
    category: "分類：",
    summaryTitle: "公開摘要",
    boundary: "此頁只包含 public-safe 摘要與來源歸屬，不包含 raw item 全文、私人通知狀態、prompt 或模型用量資料。",
    sources: "來源",
    noSources: "目前沒有公開來源連結。",
    source: "來源",
    tagsActors: "標籤與角色"
  },
  tag: {
    eyebrow: "主題標籤",
    fallbackTitle: "unknown",
    body: "依 topic tag 聚合的公開事件流。Tag 來自事件處理流程中的 public-safe taxonomy，用於檢索與分組。",
    emptyTitle: "此 tag 尚無公開事件",
    emptyBody: "後續同步事件時會自動出現在這裡。"
  },
  about: {
    eyebrow: "關於",
    title: "為市場事件建立可驗證的公開脈絡",
    body: "TickBase News 是 XAUUSD Event Radar 的公開出口，只展示已核准同步的 public-safe 事件摘要、分級、確認狀態與來源歸屬。",
    sections: [
      {
        title: "系統定位",
        body:
          "本網站不是交易訊號服務。它的任務是把不同立場、不同速度、不同權力層級的消息來源整理成可追蹤的公開事件流，幫助讀者快速理解某個消息是否有官方確認、是否存在相反口徑，以及可能透過哪些公開敘事影響市場。"
      },
      {
        title: "事件分級",
        body:
          "Severity 反映事件在系統規則與模型流程中的相對重要性。S 與 A 表示更值得優先查看，但不表示任何交易方向，也不代表結果一定會影響金價。"
      },
      {
        title: "分級說明",
        body:
          "S 代表最高優先級，通常是具直接市場影響潛力，或涉及重大政策、地緣政治、金融市場結構的事件。A 代表重要事件，值得及時查看。B 是觀察項，具有敘事或訊號價值，但優先級或確認度較低。C 是背景項，用來補足公開敘事的上下文。"
      },
      {
        title: "確認狀態",
        body:
          "confirmed、partially confirmed、unconfirmed 與 contradicted 用於標示來源之間的確認程度。未確認事件應被視為待觀察，而不是事實結論。"
      },
      {
        title: "來源背景",
        body:
          "來源標籤可能附帶簡短背景說明。這些說明用來描述來源的公開角色或常見編輯脈絡，不代表本站背書、可信度評分，也不能替代閱讀原始連結。"
      },
      {
        title: "資料邊界",
        body:
          "公開網站不保存 HomeLab 內部 raw item 全文、AI prompt、token usage、私人通知記錄、Telegram session 或任何內部管理資料。所有內容都經由 public sync 流程產生。"
      },
      {
        title: "免責聲明",
        body: "本網站內容僅供資訊與研究用途，不構成投資建議、交易建議、法律建議或財務建議。"
      }
    ]
  },
  status: {
    eyebrow: "狀態",
    title: "Public API 狀態",
    body: "公共網站只依賴 VPS public-api。此頁顯示公開 API 與 public database 的基本健康狀態。",
    loading: "正在檢查 public API...",
    api: "API",
    database: "database",
    unknown: "unknown"
  },
  states: {
    loading: "正在載入公開事件...",
    apiErrorTitle: "Public API 暫時無法讀取"
  },
  stats: {
    publicEvents: "公開事件",
    sSeverity: "S 分級",
    aSeverity: "A 分級",
    latest: "最新"
  },
  badges: {
    unknown: "unknown",
    severityDescriptions: {
      S: "最高優先級公開事件，通常具有直接政策、地緣、金融市場結構或黃金/宏觀高影響相關性。",
      A: "重要公開事件，值得及時查看，但即時優先級低於 S。",
      B: "觀察項，具備訊號或敘事變化價值，但信心或市場優先級較低。",
      C: "背景項，用來補足更大的公開敘事脈絡。"
    },
    confirmation: {
      confirmed: "已確認",
      partially_confirmed: "部分確認",
      unconfirmed: "未確認",
      contradicted: "有相反口徑"
    },
    confirmationDescriptions: {
      confirmed: "已有官方來源或多個高品質公開來源支持。",
      partially_confirmed: "已有部分支持證據，但關鍵細節仍需要更強確認。",
      unconfirmed: "單一來源、早期消息或佐證不足，應作為觀察項處理。",
      contradicted: "公開來源之間出現衝突，或後續報導否定原始說法。"
    }
  },
  sources: {
    fallback: "公開來源連結。請同時考慮來源角色、發布脈絡，以及是否有其他來源確認該說法。",
    backgrounds: {
      "Federal Reserve": "美國中央銀行官方來源。對 Fed 決議、演說、會議紀要與政策溝通具最高權威性。",
      "White House": "美國行政部門官方來源。適合確認政府立場，但通常帶有行政部門的政治表述框架。",
      "Reuters": "全球通訊社，金融與機構讀者使用度高。速度快、被廣泛引用；政策類說法仍建議對照 primary source。",
      "AP": "全球通訊社，偏向廣泛新聞覆蓋。適合做基準報導與發展中事件的交叉確認。",
      "Bloomberg": "金融新聞服務，市場導向強。適合觀察市場反應與政策報導；部分內容可能依賴匿名消息源。",
      "Tasnim": "伊朗媒體，常被視為保守派或 IRGC-adjacent 口徑。適合觀察伊朗強硬派敘事，不等同中立官方聲明。",
      "Press TV": "伊朗國家資助的國際廣播媒體。適合觀察伊朗官方或 state-aligned 的對外英文敘事。",
      "IRNA": "伊朗國家通訊社。適合確認伊朗政府正式訊息與國家層級表述。",
      "Mehr News": "伊朗半官方通訊社。適合觀察伊朗國內政治與政策敘事；敏感主張仍需交叉確認。",
      "US State Department": "美國外交政策官方來源。對美國外交立場、制裁公告與正式聲明具高權威性。",
      "IDF Official": "以色列國防軍官方來源。對 IDF 聲明與軍事行動主張具高權威性，但代表軍事行為者立場。",
      "Khamenei English": "伊朗最高領袖官方英文頻道。適合觀察正式領導層訊息與意識形態表述。",
      "Trump Truth Social": "Trump-aligned 的直接政治訊息來源。適合追蹤 Trump 的 primary statement，但事實主張需要獨立確認。",
      "TrumpsTruth": "Trump-aligned 社群/媒體 feed。適合觀察直接政治訊息，但具體主張需要獨立來源確認。"
    }
  },
  format: {
    untitled: "未命名公開事件",
    untitledRawItem: "未命名原始資料",
    noSummary: "此事件尚無公開摘要。",
    noRawSummary: "此原始資料尚無公開摘要。",
    timeUnknown: "時間未定",
    unscored: "未評分",
    high: "高",
    watch: "觀察",
    info: "資訊",
    uncategorized: "未分類"
  }
};

export const dictionaries = {
  en,
  "zh-Hant": zhHant
};

export type Dictionary = typeof en;

export function isLanguage(value: string | undefined): value is UiLanguage {
  return value === "en" || value === "zh-Hant";
}

export function normalizeLanguage(value: string | null | undefined): UiLanguage {
  const candidate = value ?? undefined;
  return isLanguage(candidate) ? candidate : defaultLanguage;
}

export function useLanguage(): UiLanguage {
  const { lang } = useParams();
  return normalizeLanguage(lang);
}

export function useI18n(): Dictionary {
  return dictionaries[useLanguage()];
}

export function localizedPath(lang: UiLanguage, path: string, search = ""): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `/${lang}${normalizedPath}${search}`;
}

export function stripLanguagePrefix(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length > 0 && isLanguage(segments[0])) {
    return `/${segments.slice(1).join("/")}`;
  }
  return pathname === "/" ? "/events" : pathname;
}

export function useLocalizedPath() {
  const lang = useLanguage();
  return (path: string, search = "") => localizedPath(lang, path, search);
}

export function useLanguageSwitchPath(targetLang: UiLanguage): string {
  const location = useLocation();
  const pathWithoutLanguage = stripLanguagePrefix(location.pathname);
  return localizedPath(targetLang, pathWithoutLanguage, location.search);
}
