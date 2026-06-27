import type {
  EventFilters,
  HealthResponse,
  Language,
  OverviewStats,
  PageResponse,
  PublicCategory,
  PublicEvent,
  PublicRawItem,
  PublicTag,
  RawItemFilters
} from "./types";

const runtimeConfig = window.__TICKBASE_NEWS_CONFIG__ ?? {};

export const apiBaseUrl =
  runtimeConfig.PUBLIC_API_BASE_URL ||
  import.meta.env.VITE_PUBLIC_API_BASE_URL ||
  (import.meta.env.DEV ? "/api" : "");

export async function listEvents(filters: EventFilters = {}): Promise<PageResponse<PublicEvent>> {
  return request<PageResponse<PublicEvent>>("/events", filters);
}

export async function getEvent(id: string, lang?: Language): Promise<PublicEvent> {
  return request<PublicEvent>(`/events/${encodeURIComponent(id)}`, { lang });
}

export async function listRawItems(filters: RawItemFilters = {}): Promise<PageResponse<PublicRawItem>> {
  return request<PageResponse<PublicRawItem>>("/raw-items", filters);
}

export async function getRawItem(id: string, lang?: Language): Promise<PublicRawItem> {
  return request<PublicRawItem>(`/raw-items/${encodeURIComponent(id)}`, { lang });
}

export async function listTags(): Promise<PublicTag[]> {
  const response = await request<{ items: PublicTag[] }>("/tags");
  return response.items;
}

export async function listCategories(): Promise<PublicCategory[]> {
  const response = await request<{ items: PublicCategory[] }>("/categories");
  return response.items;
}

export async function getOverviewStats(): Promise<OverviewStats> {
  return request<OverviewStats>("/stats/overview");
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

async function request<T>(
  path: string,
  params?: Record<string, string | number | undefined> | EventFilters | RawItemFilters
): Promise<T> {
  if (!apiBaseUrl) {
    throw new Error("PUBLIC_API_BASE_URL is not configured");
  }
  const url = new URL(`${apiBaseUrl.replace(/\/$/, "")}${path}`, window.location.origin);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Public API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
