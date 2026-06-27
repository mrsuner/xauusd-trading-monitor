export type Severity = "S" | "A" | "B" | "C";
export type Language = string;

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

export interface PublicEventTranslation {
  language: Language;
  title: string | null;
  summary: string | null;
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
  translations?: PublicEventTranslation[];
  public_source_links: PublicSourceLink[];
  topic_tags: string[];
  content_category: string | null;
  mentioned_actors: string[];
  route_metadata: Record<string, unknown>;
}

export interface PublicRawItemTranslation {
  language: Language;
  summary: string | null;
  full_translation: string | null;
  status?: string | null;
  is_truncated?: boolean;
  source_chars?: number | null;
  translation_chars?: number | null;
}

export interface PublicRawItem {
  id: string;
  upstream_raw_item_id: string;
  idempotency_key: string;
  schema_version: string;
  source_name: string | null;
  source_type: string | null;
  source_group: string | null;
  official_level: string | null;
  priority: string | null;
  source_url: string | null;
  published_at: string | null;
  ingested_at: string | null;
  edited_at: string | null;
  received_at: string;
  title: string | null;
  original_content: string | null;
  source_language: Language | null;
  media_type: string | null;
  summary: string | null;
  full_translation: string | null;
  language: Language;
  available_languages: Language[];
  translations?: PublicRawItemTranslation[];
  content_category: string | null;
  topic_tags: string[];
  mentioned_actors: string[];
  upstream_event_ids: string[];
  is_relevant: boolean | null;
  relevance_score: number | null;
  filter_reason: string | null;
  classification_stage: string | null;
  classification_status: string | null;
  is_truncated: boolean;
  source_text_chars: number | null;
  translation_chars: number | null;
  scrub_metadata: Record<string, unknown>;
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

export interface RawItemFilters {
  source_type?: string;
  source_group?: string;
  tag?: string;
  category?: string;
  q?: string;
  event_id?: string;
  lang?: Language;
  min_relevance_score?: number;
  page?: number;
  page_size?: number;
}
