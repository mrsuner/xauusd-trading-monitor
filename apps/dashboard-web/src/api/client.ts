import type {
  AlertItem,
  AIUsageStats,
  ContentCategory,
  EventDetail,
  EventItem,
  Health,
  ListEnvelope,
  OverviewStats,
  Page,
  ProcessingItem,
  ProcessingPipelineItem,
  PublicOutboxItem,
  RawItem,
  RawItemFilterOptions,
  Source,
  SourcePayload,
  SourceHealth,
  TagOption
} from "./types";

const runtimeConfig = window.__XAUUSD_DASHBOARD_CONFIG__ ?? {};

export const apiConfig = {
  baseUrl:
    runtimeConfig.DASHBOARD_API_BASE_URL ??
    import.meta.env.VITE_DASHBOARD_API_BASE_URL ??
    "http://localhost:8080",
  token: runtimeConfig.DASHBOARD_API_TOKEN ?? import.meta.env.VITE_DASHBOARD_API_TOKEN ?? ""
};

type QueryValue = string | number | boolean | null | undefined;

function toQuery(params: Record<string, QueryValue> = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, params?: Record<string, QueryValue>, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (init?.headers instanceof Headers) {
    init.headers.forEach((value, key) => {
      headers[key] = value;
    });
  } else if (Array.isArray(init?.headers)) {
    for (const [key, value] of init.headers) headers[key] = value;
  } else if (init?.headers) {
    Object.assign(headers, init.headers);
  }
  if (apiConfig.token) headers.Authorization = `Bearer ${apiConfig.token}`;

  const response = await fetch(`${apiConfig.baseUrl}${path}${toQuery(params)}`, { ...init, headers });
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message = body?.error?.message ?? body?.detail ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return body as T;
}

export const api = {
  health: () => request<Health>("/health"),
  overview: () => request<OverviewStats>("/stats/overview"),
  aiUsage: (params?: Record<string, QueryValue>) => request<AIUsageStats>("/stats/ai-usage", params),
  sources: (params?: Record<string, QueryValue>) => request<Page<Source>>("/sources", params),
  createSource: (payload: SourcePayload) =>
    request<Source>("/sources", undefined, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  updateSource: (sourceId: string, payload: Partial<SourcePayload>) =>
    request<Source>(`/sources/${sourceId}`, undefined, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  enableSource: (sourceId: string) => request<Source>(`/sources/${sourceId}/enable`, undefined, { method: "POST" }),
  disableSource: (sourceId: string) => request<Source>(`/sources/${sourceId}/disable`, undefined, { method: "POST" }),
  archiveSource: (sourceId: string) => request<Source>(`/sources/${sourceId}/archive`, undefined, { method: "POST" }),
  sourceHealth: (params?: Record<string, QueryValue>) => request<Page<SourceHealth>>("/source-health", params),
  rawItems: (params?: Record<string, QueryValue>) => request<Page<RawItem>>("/raw-items", params),
  rawItemFilters: () => request<RawItemFilterOptions>("/raw-items/filters"),
  taxonomyCategories: () => request<ListEnvelope<ContentCategory>>("/taxonomy/categories"),
  taxonomyTags: () => request<ListEnvelope<TagOption>>("/taxonomy/tags"),
  processing: (params?: Record<string, QueryValue>) => request<Page<ProcessingItem>>("/processing", params),
  processingPipeline: (params?: Record<string, QueryValue>) => request<Page<ProcessingPipelineItem>>("/processing/pipeline", params),
  events: (params?: Record<string, QueryValue>) => request<Page<EventItem>>("/events", params),
  event: (eventId: string) => request<EventDetail>(`/events/${eventId}`),
  alerts: (params?: Record<string, QueryValue>) => request<Page<AlertItem>>("/alerts", params),
  publicOutbox: (params?: Record<string, QueryValue>) => request<Page<PublicOutboxItem>>("/public-outbox", params)
};
