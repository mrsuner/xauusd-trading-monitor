import { useLocation, useParams } from "react-router-dom";
import type { ConfirmationState, Language } from "../api/types";

export const defaultLanguage: Language = "en";
export const supportedLanguages: Language[] = ["en", "zh-Hant"];

export const languageLabels: Record<Language, string> = {
  en: "EN",
  "zh-Hant": "繁中"
};

const en = {
  nav: {
    latest: "Latest",
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
    emptyTitle: "No public events match these filters",
    emptyBody: "Adjust severity, category, tag, or search text. The public website only shows approved public-safe events.",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `Showing page ${current} of ${totalPages}, ${total} public events.`,
    previousPage: "Previous page",
    nextPage: "Next page",
    reset: "Reset"
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
        title: "Confirmation State",
        body:
          "confirmed, partially confirmed, unconfirmed, and contradicted describe the degree of source confirmation. Unconfirmed events should be treated as watch items, not factual conclusions."
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
    confirmation: {
      confirmed: "confirmed",
      partially_confirmed: "partially confirmed",
      unconfirmed: "unconfirmed",
      contradicted: "contradicted"
    } satisfies Record<ConfirmationState, string>
  },
  format: {
    untitled: "Untitled public event",
    noSummary: "No public summary is available.",
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
    emptyTitle: "沒有符合條件的公開事件",
    emptyBody: "請調整 severity、category、tag 或搜尋字串。公開網站只顯示已核准同步的 public-safe events。",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `第 ${current} / ${totalPages} 頁，共 ${total} 筆公開事件。`,
    previousPage: "上一頁",
    nextPage: "下一頁",
    reset: "重設"
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
        title: "確認狀態",
        body:
          "confirmed、partially confirmed、unconfirmed 與 contradicted 用於標示來源之間的確認程度。未確認事件應被視為待觀察，而不是事實結論。"
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
    confirmation: {
      confirmed: "confirmed",
      partially_confirmed: "partially confirmed",
      unconfirmed: "unconfirmed",
      contradicted: "contradicted"
    }
  },
  format: {
    untitled: "未命名公開事件",
    noSummary: "此事件尚無公開摘要。",
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

export function isLanguage(value: string | undefined): value is Language {
  return value === "en" || value === "zh-Hant";
}

export function normalizeLanguage(value: string | null | undefined): Language {
  const candidate = value ?? undefined;
  return isLanguage(candidate) ? candidate : defaultLanguage;
}

export function useLanguage(): Language {
  const { lang } = useParams();
  return normalizeLanguage(lang);
}

export function useI18n(): Dictionary {
  return dictionaries[useLanguage()];
}

export function localizedPath(lang: Language, path: string, search = ""): string {
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

export function useLanguageSwitchPath(targetLang: Language): string {
  const location = useLocation();
  const pathWithoutLanguage = stripLanguagePrefix(location.pathname);
  return localizedPath(targetLang, pathWithoutLanguage, location.search);
}
