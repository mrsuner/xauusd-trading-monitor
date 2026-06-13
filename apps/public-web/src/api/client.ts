import { demoCategories, demoEvents, demoRawItems, demoStats, demoTags } from "./demoData";
import { localizePublicEvent, localizePublicRawItem, publicEventTranslationRows, publicRawItemTranslationRows } from "./localization";
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

const envDemo = String(import.meta.env.VITE_PUBLIC_WEB_DEMO ?? "").toLowerCase();
const runtimeDemo = String(runtimeConfig.PUBLIC_WEB_DEMO ?? "").toLowerCase();

export const useDemoData =
  runtimeDemo === "true" || runtimeDemo === "1" || envDemo === "true" || envDemo === "1";

export const apiBaseUrl =
  runtimeConfig.PUBLIC_API_BASE_URL ||
  import.meta.env.VITE_PUBLIC_API_BASE_URL ||
  (import.meta.env.DEV ? "/api" : "");

export async function listEvents(filters: EventFilters = {}): Promise<PageResponse<PublicEvent>> {
  if (useDemoData) {
    return demoListEvents(filters);
  }
  return request<PageResponse<PublicEvent>>("/events", filters);
}

export async function getEvent(id: string, lang?: Language): Promise<PublicEvent> {
  if (useDemoData) {
    const event = demoEvents.find((item) => item.id === id);
    if (!event) {
      throw new Error("Event not found");
    }
    return localizePublicEvent(event, lang);
  }
  return request<PublicEvent>(`/events/${encodeURIComponent(id)}`, { lang });
}

export async function listRawItems(filters: RawItemFilters = {}): Promise<PageResponse<PublicRawItem>> {
  if (useDemoData) {
    return demoListRawItems(filters);
  }
  return request<PageResponse<PublicRawItem>>("/raw-items", filters);
}

export async function getRawItem(id: string, lang?: Language): Promise<PublicRawItem> {
  if (useDemoData) {
    const item = demoRawItems.find((rawItem) => rawItem.id === id);
    if (!item) {
      throw new Error("Raw item not found");
    }
    return localizePublicRawItem(item, lang);
  }
  return request<PublicRawItem>(`/raw-items/${encodeURIComponent(id)}`, { lang });
}

export async function listTags(): Promise<PublicTag[]> {
  if (useDemoData) {
    return demoTags;
  }
  const response = await request<{ items: PublicTag[] }>("/tags");
  return response.items;
}

export async function listCategories(): Promise<PublicCategory[]> {
  if (useDemoData) {
    return demoCategories;
  }
  const response = await request<{ items: PublicCategory[] }>("/categories");
  return response.items;
}

export async function getOverviewStats(): Promise<OverviewStats> {
  if (useDemoData) {
    return demoStats;
  }
  return request<OverviewStats>("/stats/overview");
}

export async function getHealth(): Promise<HealthResponse> {
  if (useDemoData) {
    return { status: "ok", database: "ok", service: "public-api" };
  }
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

function demoListEvents(filters: EventFilters): PageResponse<PublicEvent> {
  const page = Number(filters.page ?? 1);
  const pageSize = Number(filters.page_size ?? 20);
  let items = [...demoEvents];
  if (filters.severity) {
    items = items.filter((item) => item.severity === filters.severity);
  }
  if (filters.confirmation_state) {
    items = items.filter((item) => item.confirmation_state === filters.confirmation_state);
  }
  if (filters.tag) {
    items = items.filter((item) => item.topic_tags.includes(String(filters.tag)));
  }
  if (filters.category) {
    items = items.filter((item) => item.content_category === filters.category);
  }
  if (filters.q) {
    const q = String(filters.q).toLowerCase();
    items = items.filter((item) =>
      [
        item.public_title_zh,
        item.public_summary_zh,
        item.public_title_en,
        item.public_summary_en,
        ...publicEventTranslationRows(item).flatMap((translation) => [translation.title, translation.summary]),
        ...item.topic_tags,
        ...item.mentioned_actors
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    );
  }
  const total = items.length;
  const offset = (page - 1) * pageSize;
  return {
    items: items.slice(offset, offset + pageSize).map((item) => localizePublicEvent(item, filters.lang)),
    page,
    page_size: pageSize,
    total
  };
}

function demoListRawItems(filters: RawItemFilters): PageResponse<PublicRawItem> {
  const page = Number(filters.page ?? 1);
  const pageSize = Number(filters.page_size ?? 20);
  let items = [...demoRawItems];
  if (filters.event_id) {
    const event = demoEvents.find((item) => item.id === filters.event_id);
    items = event ? items.filter((item) => item.upstream_event_ids.includes(event.upstream_event_id)) : [];
  }
  if (filters.source_type) {
    items = items.filter((item) => item.source_type === filters.source_type);
  }
  if (filters.source_group) {
    items = items.filter((item) => item.source_group === filters.source_group);
  }
  if (filters.tag) {
    items = items.filter((item) => item.topic_tags.includes(String(filters.tag)));
  }
  if (filters.category) {
    items = items.filter((item) => item.content_category === filters.category);
  }
  if (filters.q) {
    const q = String(filters.q).toLowerCase();
    items = items.filter((item) =>
      [
        item.title,
        item.original_content,
        item.summary_zh,
        item.summary_en,
        item.full_translation_zh,
        item.full_translation_en,
        ...publicRawItemTranslationRows(item).flatMap((translation) => [
          translation.summary,
          translation.full_translation
        ]),
        ...item.topic_tags,
        ...item.mentioned_actors,
        item.source_name
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    );
  }
  const total = items.length;
  const offset = (page - 1) * pageSize;
  return {
    items: items.slice(offset, offset + pageSize).map((item) => localizePublicRawItem(item, filters.lang)),
    page,
    page_size: pageSize,
    total
  };
}
