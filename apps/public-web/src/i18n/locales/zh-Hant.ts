import type { Dictionary } from "./en";

export const zhHant = {
  nav: {
    latest: "最新",
    raw: "原始 feed",
    highImpact: "高影響",
    tags: "標籤",
    about: "關於",
    status: "狀態",
    support: "支持",
    supportCta: "支持",
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
    support: "支持本站",
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
  support: {
    eyebrow: "支持",
    title: "用愛發電，維持雷達運轉",
    body:
      "TickBase News 完全免費、沒有訂閱制。不同於 TickBase 的月付模式，本站採「用愛發電」：如果它為你帶來價值，一點小額捐助就能幫助它持續為大家運轉。",
    costsTitle: "你的支持會用在哪裡",
    costs: [
      {
        title: "AI 調用",
        body: "翻譯、摘要與相關度判斷都跑在付費模型 API 上。隨著覆蓋範圍擴大，這是最主要的持續性成本。"
      },
      {
        title: "伺服器與基礎設施",
        body: "公開網站、public API 與資料庫跑在 VPS 上，必須全天候在線才能維持 feed 的即時性。"
      },
      {
        title: "日常開發維護",
        body: "每日維護、新增來源與功能開發，讓事件雷達持續準確、快速且實用。"
      }
    ],
    ctaTitle: "幫雷達續一分鐘，或一小時",
    ctaBody:
      "在 Ko-fi 你可以用任意金額為本站「續時」，以分鐘或小時計。每一份支持都直接抵銷 AI、伺服器與維護成本。",
    ctaButton: "前往 Ko-fi 支持",
    ctaNote: "捐助完全出於自願，也不會解鎖任何付費內容——這裡的一切都維持公開。",
    disclaimer: "支持是維持站點運轉，而非購買投資建議。所有內容仍僅供資訊與研究用途。"
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
  },
  categories: {
    diplomacy: "外交",
    military: "軍事",
    sanctions: "制裁",
    fed: "Fed",
    energy: "能源",
    market: "市場",
    domestic_politics: "國內政治",
    economy: "經濟",
    technology: "科技",
    routine: "日常",
    social: "社會",
    other: "其他"
  }
} satisfies Dictionary;
