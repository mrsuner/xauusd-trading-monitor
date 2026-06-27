import type { ConfirmationState } from "../../api/types";

export const en = {
  nav: {
    latest: "Latest",
    raw: "Raw Feed",
    highImpact: "High Impact",
    tags: "Tags",
    about: "About",
    status: "Status",
    support: "Support",
    supportCta: "Support",
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
    support: "Support this site",
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
  support: {
    eyebrow: "Support",
    title: "Powered by goodwill — keep the radar running",
    body:
      "TickBase News is free and has no subscription. Unlike TickBase's monthly plan, this site runs on a \"pay it forward\" model: if it creates value for you, a small donation helps keep it online for everyone.",
    costsTitle: "Where your support goes",
    costs: [
      {
        title: "AI inference",
        body: "Translation, summarization, and relevance judgement run on paid model APIs. This is the largest recurring cost as coverage grows."
      },
      {
        title: "Servers & infrastructure",
        body: "The public site, public API, and database run on a VPS that has to stay online around the clock to keep the feed fresh."
      },
      {
        title: "Ongoing development",
        body: "Daily maintenance, new sources, and feature work that keep the event radar accurate, fast, and useful."
      }
    ],
    ctaTitle: "Buy the radar a minute — or an hour",
    ctaBody:
      "On Ko-fi you can chip in any amount to \"top up\" the site's running time, by the minute or by the hour. Every bit directly offsets AI, server, and upkeep costs.",
    ctaButton: "Support on Ko-fi",
    ctaNote: "Donations are voluntary and do not unlock paywalled content — everything here stays public.",
    disclaimer: "Support keeps the lights on; it does not buy investment advice. All content remains information and research only."
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

export type Dictionary = typeof en;
