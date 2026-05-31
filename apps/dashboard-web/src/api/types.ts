export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type Health = {
  status: string;
  database: string;
  service: string;
};

export type OverviewStats = {
  active_sources: number;
  raw_items_1h: number;
  raw_items_24h: number;
  events_1h: number;
  events_24h: number;
  high_impact_events_24h: number;
  failed_processing: number;
  failed_alerts: number;
};

export type Source = {
  id: string;
  name: string;
  handle_or_url: string;
  source_type: string;
  source_group: string;
  official_level: string;
  stance?: string | null;
  language?: string | null;
  priority: string;
  reliability_score: number;
  latency_score: number;
  requires_confirmation: boolean;
  translation_policy: string;
  translation_priority: string;
  translation_max_chars?: number | null;
  always_full_translate: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type SourceHealth = {
  id: string;
  source_id: string;
  source_name: string;
  handle_or_url: string;
  source_type: string;
  source_group: string;
  service_name: string;
  status: string;
  last_seen_at?: string | null;
  last_polled_at?: string | null;
  last_message_at?: string | null;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_error_message?: string | null;
  messages_ingested_1h: number;
  messages_ingested_24h: number;
  updated_at: string;
};

export type RawItem = {
  id: string;
  source_id: string;
  source_name: string;
  source_type: string;
  source_group: string;
  official_level: string;
  priority: string;
  title?: string | null;
  text_clean?: string | null;
  summary_zh?: string | null;
  summary_en?: string | null;
  full_translation_zh?: string | null;
  full_translation_en?: string | null;
  translation_status?: string | null;
  translation_model_provider?: string | null;
  translation_model?: string | null;
  translation_error?: string | null;
  translation_input_chars?: number | null;
  translation_updated_at?: string | null;
  text_raw?: string | null;
  language?: string | null;
  url?: string | null;
  published_at?: string | null;
  ingested_at: string;
  media_type: string;
  dedupe_key: string;
};

export type ProcessingItem = {
  id: string;
  raw_item_id: string;
  source_name: string;
  source_group: string;
  title?: string | null;
  stage: string;
  status: string;
  is_relevant?: boolean | null;
  relevance_score?: number | null;
  model_provider?: string | null;
  model_name?: string | null;
  attempt_count: number;
  locked_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  updated_at: string;
};

export type EventItem = {
  id: string;
  event_time?: string | null;
  detected_at: string;
  event_type: string;
  source_group?: string | null;
  severity: string;
  relevance_score: number;
  confidence?: number | null;
  confirmation_state: string;
  title?: string | null;
  summary_zh: string;
  market_relevance?: string | null;
  xauusd_impact_channel: string[];
  requires_confirmation: boolean;
  source_name?: string | null;
  official_level?: string | null;
  priority?: string | null;
};

export type EventDetail = EventItem & {
  claims: EventClaim[];
  alerts: AlertItem[];
  raw_items: RawItem[];
  model_provider?: string | null;
  model_name?: string | null;
  model_output_json?: unknown;
};

export type EventClaim = {
  id: string;
  claim_text: string;
  claim_direction: string;
  stance?: string | null;
  confidence?: number | null;
  source_name?: string | null;
  source_group?: string | null;
  official_level?: string | null;
  created_at: string;
};

export type AlertItem = {
  id: string;
  event_id: string;
  event_title?: string | null;
  event_severity?: string | null;
  event_type?: string | null;
  channel: string;
  priority: string;
  delivery_status: string;
  message: string;
  sent_at?: string | null;
  error_message?: string | null;
  created_at: string;
};
