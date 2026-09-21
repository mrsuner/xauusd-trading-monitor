import type { Dictionary } from "./en";

export const ja = {
  nav: {
    latest: "最新",
    raw: "Raw Feed",
    highImpact: "高インパクト",
    explore: "探索",
    topics: "トピック",
    about: "概要",
    status: "ステータス",
    support: "サポート",
    notifications: "通知",
    digests: "デイリーダイジェスト",
    supportCta: "サポート",
    language: "言語",
    signIn: "ログイン",
    accountMenu: "アカウントメニュー",
    openMenu: "メニューを開く",
    closeMenu: "メニューを閉じる",
    tickbaseHome: "TickBase News ホーム",
    toggleTheme: "テーマを切り替え"
  },
  footer: {
    summary:
      "市場を動かし得るマクロ、金、地政学、エネルギー、政策ニュースの公開イベントレーダーです。投資助言ではありません。",
    explore: "見る",
    product: "プロダクト",
    latestEvents: "最新イベント",
    highImpact: "高インパクト",
    rawFeed: "Raw feed",
    topics: "トピック",
    methodology: "方法論",
    support: "このサイトを支援",
    apiStatus: "API ステータス",
    mainTickBase: "TickBase メインサイト",
    dataBoundary: "データ境界",
    dataBoundaryBody:
      "このサイトは public-safe な要約と出典情報だけを表示します。内部 raw item、prompt、usage cost、session、非公開配信状態は公開しません。"
  },
  account: {
    loading: "アカウントを確認中",
    unavailable: "アカウントサービスを一時的に利用できません。",
    retry: "アカウントを再読み込み",
    newsPro: "NEWS PRO",
    free: "無料",
    accountSubscription: "アカウントと購読",
    signOut: "ログアウト",
    signingOut: "ログアウト中...",
    signOutError: "ログアウトできませんでした。もう一度お試しください。"
  },
  auth: {
    signInTitle: "ログイン",
    signInBody: "TickBase アカウントでニュース設定、通知、デイリーダイジェストを管理できます。",
    registerTitle: "アカウントを作成",
    registerBody: "News の設定と配信内容を保存する TickBase アカウントを作成します。",
    name: "名前",
    email: "メールアドレス",
    password: "パスワード",
    passwordConfirmation: "パスワードの確認",
    showPassword: "パスワードを表示",
    hidePassword: "パスワードを隠す",
    signIn: "ログイン",
    signingIn: "ログイン中...",
    createAccount: "アカウントを作成",
    creatingAccount: "アカウントを作成中...",
    noAccount: "TickBase を初めて利用しますか？",
    haveAccount: "すでにアカウントをお持ちですか？",
    passwordMismatch: "確認用パスワードが一致しません。",
    genericError: "アカウントリクエストを完了できませんでした。"
  },
  topics: {
    eyebrow: "探索",
    title: "トピック",
    body: "TickBase News に現在掲載されているトピック別に公開イベントを閲覧できます。",
    loading: "トピックを読み込み中...",
    emptyTitle: "トピックはまだありません",
    emptyBody: "公開イベントが同期されると、トピックがここに表示されます。",
    eventCount: (count: number) => `${count}件のイベント`
  },
  notifications: {
    eyebrow: "個人配信",
    title: "ニュース通知",
    body: "関心のある公開トピックを選び、対象の速報を Telegram で受け取れます。個人配信には有効な News subscription が必要です。",
    signInTitle: "ログインして通知を管理",
    signInBody: "共通の browser session は TickBase Account が管理します。ログイン後、このページに戻ってください。",
    signIn: "TickBase にログイン",
    loadError: "通知設定を一時的に読み込めません。",
    upgradeRequired: "公開ニュースは引き続き閲覧できます。配信範囲の変更や Telegram 通知の有効化には有効な News subscription が必要です。",
    requestError: "リクエストを完了できませんでした。",
    preferencesTitle: "配信設定",
    preferencesBody: "選択した category と tag は AND 条件で照合されます。",
    masterLabel: "個人通知",
    masterBody: "オフにすると選択内容と Telegram の連携を残したまま、新しい配信を停止します。",
    severity: "最低 severity",
    language: "配信言語",
    categories: "Categories",
    allCategories: "有効な全 category を対象にする",
    tags: "Topic tags",
    tagsBody: "tag を選択しない場合、選択した category 内のすべての tag が対象です。",
    catalogError: "subscription catalog を利用できません。既存の選択内容は変更されていません。",
    unavailableSelections: "無効ですが保存されている選択",
    saved: "設定を保存しました。",
    saving: "保存中…",
    save: "設定を保存",
    telegramBody: "1つの private Telegram chat を連携します。single-use link は10分で期限切れになります。",
    channelLoadError: "Telegram の状態を一時的に読み込めません。",
    creatingLink: "リンク作成中…",
    linkTelegram: "Telegram を連携",
    openTelegramBody: "Telegram で bot を開始し、このページに戻って状態を確認してください。",
    openTelegram: "Telegram を開く",
    checkLink: "状態を確認",
    linked: "Telegram 連携済み",
    channelEnabled: "Telegram 配信を有効にする",
    channelNeedsAttention: "Telegram 配信に問題があります。問題が続く場合は chat を再連携してください。",
    unlink: "Telegram の連携を解除",
    unlinkConfirm: "Telegram の連携を解除し、未送信の配信をキャンセルしますか？"
  },
  events: {
    eyebrow: "公開イベントレーダー",
    title: "TickBase News",
    body:
      "XAUUSD、Fed、Trump、Iran、IRGC、エネルギー、地政学リスクに焦点を当てた public-safe なイベントストリームです。出典の確認状態を追跡し、取引助言は提供しません。",
    filters: "フィルター",
    searchPlaceholder: "公開要約を検索",
    search: "検索",
    allSeverity: "すべての重要度",
    allConfirmation: "すべての確認状態",
    allCategories: "すべてのカテゴリ",
    allTags: "すべてのタグ",
    ariaSeverity: "重要度",
    ariaConfirmation: "確認状態",
    ariaCategory: "カテゴリ",
    ariaTag: "タグ",
    severityOptions: {
      S: "S - 最高の公開優先度",
      A: "A - 高い公開優先度",
      B: "B - 注視",
      C: "C - 背景"
    },
    confirmationOptions: {
      confirmed: "確認済み",
      partially_confirmed: "一部確認済み",
      unconfirmed: "未確認",
      contradicted: "矛盾あり"
    },
    emptyTitle: "条件に一致する公開イベントはありません",
    emptyBody: "重要度、カテゴリ、タグ、検索語を調整してください。公開サイトには承認済みの public-safe events だけが表示されます。",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `${totalPages} ページ中 ${current} ページ、公開イベント ${total} 件を表示しています。`,
    previousPage: "前のページ",
    nextPage: "次のページ",
    reset: "リセット"
  },
  raw: {
    eyebrow: "公開 raw feed",
    title: "Raw Source Feed",
    body:
      "イベント要約とは独立して同期される public-safe な source items です。各項目には整形済み原文と利用可能な全文翻訳が表示されます。",
    filters: "フィルター",
    searchPlaceholder: "raw source items を検索",
    search: "検索",
    allSourceTypes: "すべてのソース種別",
    allCategories: "すべてのカテゴリ",
    allTags: "すべてのタグ",
    ariaSourceType: "ソース種別",
    ariaCategory: "カテゴリ",
    ariaTag: "タグ",
    emptyTitle: "条件に一致する raw source items はありません",
    emptyBody: "ソース種別、カテゴリ、タグ、検索語を調整してください。",
    pageStatus: (current: number, totalPages: number, total: number) =>
      `${totalPages} ページ中 ${current} ページ、raw source items ${total} 件を表示しています。`,
    previousPage: "前のページ",
    nextPage: "次のページ",
    reset: "リセット",
    sourceFallback: "公開ソース",
    sourceType: "ソース種別",
    originalContent: "原文",
    fullTranslation: "全文翻訳",
    summary: "要約",
    noOriginalContent: "表示できる原文はありません。",
    noFullTranslation: "表示できる全文翻訳はありません。",
    relevance: "関連度",
    supportingItems: "関連 raw items",
    noSupportingItems: "このイベントに関連 raw items はまだ紐づいていません。",
    viewRawItem: "raw item を表示"
  },
  detail: {
    eyebrow: "公開イベント詳細",
    missingIdTitle: "Event id がありません",
    missingIdBody: "イベント一覧に戻り、公開イベントを開き直してください。",
    loading: "イベント詳細を読み込み中...",
    notFoundTitle: "イベントが見つかりません",
    notFoundBody: "この公開イベントは存在しないか、非表示になっています。",
    eventTime: "イベント時刻:",
    category: "カテゴリ:",
    summaryTitle: "公開要約",
    boundary:
      "このページには public-safe な要約と出典情報だけが含まれます。raw item 本文、非公開配信状態、prompt、モデル使用量データは含まれません。",
    sources: "ソース",
    noSources: "公開ソースリンクはありません。",
    source: "ソース",
    tagsActors: "タグと関係者"
  },
  tag: {
    eyebrow: "トピックタグ",
    fallbackTitle: "unknown",
    body: "トピックタグ別にまとめた公開イベントです。タグはイベント処理 pipeline の public-safe taxonomy から生成されます。",
    emptyTitle: "このタグの公開イベントはまだありません",
    emptyBody: "今後同期されたイベントが自動的に表示されます。"
  },
  about: {
    eyebrow: "概要",
    title: "市場を動かすニュースを検証可能な形に整理",
    body:
      "TickBase News は XAUUSD Event Radar の公開チャンネルです。承認済みの public-safe なイベント要約、重要度、確認状態、出典情報だけを表示します。",
    sections: [
      {
        title: "システムの役割",
        body:
          "このサイトは取引シグナルサービスではありません。立場、速度、権威性が異なる情報源を追跡可能な公開イベントストリームに整理し、主張が公式に確認されているか、矛盾するナラティブがあるか、市場に影響し得る公開ナラティブは何かを把握しやすくします。"
      },
      {
        title: "イベント重要度",
        body:
          "重要度はシステムルールとモデル workflow における相対的な優先度です。S と A は優先して読む価値が高いことを示しますが、取引方向や金価格への影響を保証するものではありません。"
      },
      {
        title: "重要度レベル",
        body:
          "S は直接的な市場影響や重要な政策・地政学的含意を持つ最優先イベントです。A は速やかに確認すべき重要イベントです。B は有用だが優先度の低い注視項目です。C は広い公開ナラティブを理解するための背景情報です。"
      },
      {
        title: "確認状態",
        body:
          "confirmed、partially confirmed、unconfirmed、contradicted は出典確認の度合いを示します。未確認イベントは事実結論ではなく注視項目として扱ってください。"
      },
      {
        title: "ソース背景",
        body:
          "ソースラベルには短い背景説明が含まれることがあります。これは公開上の役割や一般的な編集文脈を説明するもので、推薦、信頼度スコア、原文確認の代替ではありません。"
      },
      {
        title: "データ境界",
        body:
          "公開サイトは HomeLab の raw item 本文、AI prompt、token usage、非公開通知記録、Telegram session、内部管理データを保存しません。すべての内容は public sync flow を通じて生成されます。"
      },
      {
        title: "免責事項",
        body: "このサイトは情報提供と調査目的のみです。投資、取引、法律、財務の助言ではありません。"
      }
    ]
  },
  support: {
    eyebrow: "サポート",
    title: "善意で動くレーダーを支える",
    body:
      "TickBase News の公開 feed は無料で閲覧できます。任意の寄付は公開サービスの運営を支えます。有料の個人配信は別に管理されます。",
    costsTitle: "支援の使い道",
    costs: [
      {
        title: "AI 推論",
        body: "翻訳、要約、関連度判定は有料モデル API で実行されます。カバレッジが広がるほど最大の継続コストになります。"
      },
      {
        title: "サーバーとインフラ",
        body: "公開サイト、public API、database は VPS 上で稼働し、feed を新鮮に保つため常時オンラインである必要があります。"
      },
      {
        title: "継続的な開発",
        body: "日々の保守、新しいソース追加、イベントレーダーを正確・高速・有用に保つための機能開発です。"
      }
    ],
    ctaTitle: "レーダーに 1 分、または 1 時間を足す",
    ctaBody:
      "Ko-fi では任意の金額でサイトの稼働時間を分単位または時間単位で支援できます。すべての支援は AI、サーバー、保守費用に直接充てられます。",
    ctaButton: "Ko-fi で支援",
    ctaNote: "寄付は任意で、個人配信を有効にするものではありません。公開 feed は誰でも閲覧できます。",
    disclaimer: "支援は運営費を支えるもので、投資助言を購入するものではありません。すべての内容は情報提供と調査目的のみです。"
  },
  status: {
    eyebrow: "ステータス",
    title: "Public API ステータス",
    body: "公開サイトは VPS public-api のみに依存します。このページは public API と public database の基本的なヘルスを表示します。",
    loading: "Public API を確認中...",
    api: "API",
    database: "database",
    unknown: "unknown"
  },
  states: {
    loading: "公開イベントを読み込み中...",
    apiErrorTitle: "Public API は一時的に利用できません"
  },
  stats: {
    publicEvents: "公開イベント",
    sSeverity: "S 重要度",
    aSeverity: "A 重要度",
    latest: "最新"
  },
  badges: {
    unknown: "unknown",
    severityDescriptions: {
      S: "最優先の公開イベント。通常、政策、地政学、市場構造、または金・マクロへの高インパクトな関連性があります。",
      A: "重要な公開イベント。S ほど即時性は高くありませんが、早めの確認に値します。",
      B: "注視項目。有用なシグナルやナラティブ変化がありますが、信頼度または市場優先度は低めです。",
      C: "背景項目。広い公開ナラティブを理解するための文脈情報です。"
    },
    confirmation: {
      confirmed: "確認済み",
      partially_confirmed: "一部確認済み",
      unconfirmed: "未確認",
      contradicted: "矛盾あり"
    },
    confirmationDescriptions: {
      confirmed: "公式または複数の高品質な公開ソースにより支持されています。",
      partially_confirmed: "一部の裏付けはありますが、重要な詳細にはより強い確認が必要です。",
      unconfirmed: "単一ソース、初期報道、または裏付け不足です。注視項目として扱ってください。",
      contradicted: "公開ソース間で矛盾があるか、後続報道が元の主張を否定しています。"
    }
  },
  sources: {
    fallback: "公開ソースリンクです。ソースの役割、公開文脈、他ソースによる確認有無も考慮してください。",
    backgrounds: {
      "Federal Reserve": "米国中央銀行の公式ソースです。Fed の決定、講演、議事要旨、政策コミュニケーションで最も権威があります。",
      "White House": "米国行政府の公式ソースです。政権の立場確認に有用ですが、政治的な表現枠組みを前提に読む必要があります。",
      "Reuters": "機関投資家にも広く読まれる国際通信社です。速報性と配信範囲が強みですが、政策主張は primary source と照合してください。",
      "AP": "幅広いニュースを扱う国際通信社です。基礎報道や進行中の出来事のクロスチェックに有用です。",
      "Bloomberg": "市場フォーカスの強い金融ニュースサービスです。市場反応や政策報道に有用ですが、一部は匿名ソースに依存する場合があります。",
      "Tasnim": "保守派または IRGC-adjacent と見なされることが多いイラン系メディアです。イラン強硬派の見方を把握するのに有用ですが、中立的な公式声明ではありません。",
      "Press TV": "イラン国費系の国際放送です。対外英語発信における公式または state-aligned なイラン側の見方を追うのに有用です。",
      "IRNA": "イラン国営通信社です。イラン政府の公式メッセージや国家レベルの表現を確認するのに有用です。",
      "Mehr News": "イランの半公式通信社です。国内政治や政策ナラティブの把握に有用ですが、敏感な主張はクロスチェックしてください。",
      "US State Department": "米国外交政策の公式ソースです。外交立場、制裁通知、公式声明で高い権威があります。",
      "IDF Official": "イスラエル国防軍の公式ソースです。IDF の声明や作戦主張で高い権威がありますが、軍事主体の立場を代表します。",
      "Khamenei English": "イラン最高指導者の公式英語チャンネルです。正式な指導部メッセージやイデオロギー的表現を追うのに有用です。",
      "Trump Truth Social": "Trump-aligned な直接政治メッセージのソースです。Trump 本人の primary statement を追うのに有用ですが、事実主張は独立確認が必要です。",
      "TrumpsTruth": "Trump-aligned なソーシャル/メディア feed です。直接的な政治メッセージの把握に有用ですが、具体的な主張は独立ソースで確認してください。"
    }
  },
  format: {
    untitled: "無題の公開イベント",
    untitledRawItem: "無題の raw item",
    noSummary: "公開要約はありません。",
    noRawSummary: "公開 raw 要約はありません。",
    timeUnknown: "時刻不明",
    unscored: "未スコア",
    high: "高",
    watch: "注視",
    info: "情報",
    uncategorized: "未分類"
  },
  categories: {
    diplomacy: "外交",
    military: "軍事",
    sanctions: "制裁",
    fed: "Fed",
    energy: "エネルギー",
    market: "市場",
    domestic_politics: "国内政治",
    economy: "経済",
    technology: "テクノロジー",
    routine: "ルーティン",
    social: "社会",
    other: "その他"
  }
} satisfies Dictionary;
