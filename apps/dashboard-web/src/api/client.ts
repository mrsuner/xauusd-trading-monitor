import type {
  AlertItem,
  AIUsageStats,
  EventDetail,
  EventItem,
  Health,
  OverviewStats,
  Page,
  ProcessingItem,
  ProcessingPipelineItem,
  RawItem,
  Source,
  SourceHealth
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

async function request<T>(path: string, params?: Record<string, QueryValue>): Promise<T> {
  const headers: HeadersInit = {};
  if (apiConfig.token) headers.Authorization = `Bearer ${apiConfig.token}`;

  const response = await fetch(`${apiConfig.baseUrl}${path}${toQuery(params)}`, { headers });
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
  sourceHealth: (params?: Record<string, QueryValue>) => request<Page<SourceHealth>>("/source-health", params),
  rawItems: (params?: Record<string, QueryValue>) => request<Page<RawItem>>("/raw-items", params),
  processing: (params?: Record<string, QueryValue>) => request<Page<ProcessingItem>>("/processing", params),
  processingPipeline: (params?: Record<string, QueryValue>) => request<Page<ProcessingPipelineItem>>("/processing/pipeline", params),
  events: (params?: Record<string, QueryValue>) => request<Page<EventItem>>("/events", params),
  event: (eventId: string) => request<EventDetail>(`/events/${eventId}`),
  alerts: (params?: Record<string, QueryValue>) => request<Page<AlertItem>>("/alerts", params)
};
