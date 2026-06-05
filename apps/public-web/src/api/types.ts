export type Severity = "S" | "A" | "B" | "C";
export type Language = "en" | "zh-Hant";

export type ConfirmationState =
  | "unconfirmed"
  | "partially_confirmed"
  | "confirmed"
  | "contradicted";

export interface PublicSourceLink {
  label?: string | null;
  source_name?: string | null;
  url: string;
}

export interface PublicEvent {
  id: string;
  upstream_event_id: string;
  idempotency_key: string;
  schema_version: string;
  event_time: string | null;
  generated_at: string | null;
  received_at: string;
  severity: Severity;
  relevance_score: number | null;
  confirmation_state: ConfirmationState | null;
  title: string | null;
  summary: string | null;
  language: Language;
  available_languages: Language[];
  public_title_zh: string | null;
  public_summary_zh: string | null;
  public_title_en: string | null;
  public_summary_en: string | null;
  public_source_links: PublicSourceLink[];
  topic_tags: string[];
  content_category: string | null;
  mentioned_actors: string[];
  route_metadata: Record<string, unknown>;
}

export interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface PublicTag {
  tag: string;
  count: number;
}

export interface PublicCategory {
  category: string;
  count: number;
}

export interface OverviewStats {
  total_events: number;
  s_events: number;
  a_events: number;
  latest_event_time: string | null;
}

export interface HealthResponse {
  status: string;
  database?: string;
  service: string;
}

export interface EventFilters {
  severity?: string;
  confirmation_state?: string;
  tag?: string;
  category?: string;
  q?: string;
  lang?: Language;
  page?: number;
  page_size?: number;
}
