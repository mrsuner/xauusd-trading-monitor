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

export type AIUsageBreakdown = {
  provider?: string | null;
  model_name?: string | null;
  route_name?: string | null;
  ai_layer?: string | null;
  source_id?: string | null;
  source_name?: string | null;
  source_type?: string | null;
  source_group?: string | null;
  priority?: string | null;
  call_count: number;
  success_count?: number;
  failure_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: string | number;
  avg_latency_ms?: number | null;
};

export type AIUsageStats = {
  hours: number;
  totals: AIUsageBreakdown;
  by_model: AIUsageBreakdown[];
  by_layer: AIUsageBreakdown[];
  by_source: AIUsageBreakdown[];
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
  telegram_alert_enabled: boolean;
  pushover_alert_enabled: boolean;
  telegram_min_severity: string;
  pushover_min_severity: string;
  alert_weight: number;
  alert_rate_limit_per_hour?: number | null;
  alert_cooldown_minutes?: number | null;
  enabled: boolean;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
  last_raw_item_at?: string | null;
  raw_items_24h?: number;
  events_24h?: number;
};

export type SourcePayload = {
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
  telegram_alert_enabled: boolean;
  pushover_alert_enabled: boolean;
  telegram_min_severity: string;
  pushover_min_severity: string;
  alert_weight: number;
  alert_rate_limit_per_hour?: number | null;
  alert_cooldown_minutes?: number | null;
  enabled: boolean;
  source_config?: Record<string, unknown>;
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

export type RawItemTranslation = {
  language: string;
  summary?: string | null;
  full_translation?: string | null;
  status: string;
  model_provider?: string | null;
  model?: string | null;
  error?: string | null;
  input_chars?: number | null;
  updated_at?: string | null;
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
  translations?: RawItemTranslation[];
  content_category?: string | null;
  topic_tags?: string[];
  mentioned_actors?: string[];
  translation_status?: string | null;
  translation_model_provider?: string | null;
  translation_model?: string | null;
  translation_error?: string | null;
  translation_input_chars?: number | null;
  translation_updated_at?: string | null;
  classification_stage?: string | null;
  classification_status?: string | null;
  is_relevant?: boolean | null;
  relevance_score?: number | null;
  filter_reason?: string | null;
  classification_model_provider?: string | null;
  classification_model_name?: string | null;
  classification_updated_at?: string | null;
  has_event?: boolean | null;
  event_id?: string | null;
  event_severity?: string | null;
  event_confidence?: number | null;
  event_relevance_score?: number | null;
  event_title?: string | null;
  text_raw?: string | null;
  language?: string | null;
  url?: string | null;
  published_at?: string | null;
  ingested_at: string;
  media_type: string;
  dedupe_key: string;
};

export type RawItemFilterOptions = {
  content_categories: string[];
  topic_tags: string[];
  mentioned_actors: string[];
};

export type ContentCategory = {
  key: string;
  label_zh: string;
  label_en: string;
  description?: string | null;
  sort_order: number;
  enabled: boolean;
  is_system: boolean;
};

export type TagOption = {
  key: string;
  label: string;
  tag_type: string;
  aliases: string[];
  usage_count: number;
  enabled: boolean;
  is_system: boolean;
};

export type ListEnvelope<T> = {
  items: T[];
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

export type ProcessingPipelineItem = {
  raw_item_id: string;
  source_id: string;
  source_name: string;
  source_type: string;
  source_group: string;
  priority: string;
  official_level: string;
  title?: string | null;
  language?: string | null;
  url?: string | null;
  published_at?: string | null;
  ingested_at: string;
  summary_zh?: string | null;
  summary_en?: string | null;
  translations?: RawItemTranslation[];
  translation_status: string;
  translation_model_provider?: string | null;
  translation_model?: string | null;
  translation_error?: string | null;
  translation_input_chars?: number | null;
  translation_updated_at?: string | null;
  translation_call_count: number;
  translation_input_tokens: number;
  translation_output_tokens: number;
  translation_total_tokens: number;
  translation_estimated_cost_usd: string | number;
  classification_processing_id?: string | null;
  classification_stage?: string | null;
  classification_status?: string | null;
  is_relevant?: boolean | null;
  relevance_score?: number | null;
  filter_reason?: string | null;
  classification_model_provider?: string | null;
  classification_model_name?: string | null;
  classification_attempt_count?: number | null;
  classification_locked_at?: string | null;
  classification_error?: string | null;
  classification_updated_at?: string | null;
  classification_call_count: number;
  classification_input_tokens: number;
  classification_output_tokens: number;
  classification_total_tokens: number;
  classification_estimated_cost_usd: string | number;
  pipeline_updated_at: string;
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

export type SourceLink = {
  label?: string | null;
  url?: string | null;
  source_name?: string | null;
};

export type PublicOutboxTranslation = {
  language: string;
  title?: string | null;
  summary?: string | null;
  status: string;
  updated_at?: string | null;
};

export type PublicOutboxItem = {
  id: string;
  event_id: string;
  public_title_zh?: string | null;
  public_summary_zh?: string | null;
  public_title_en?: string | null;
  public_summary_en?: string | null;
  translations?: PublicOutboxTranslation[];
  public_source_links: SourceLink[];
  severity: string;
  relevance_score?: number | null;
  confirmation_state?: string | null;
  topic_tags: string[];
  approved_for_public: boolean;
  publish_status_web: string;
  publish_status_telegram: string;
  publish_status_x: string;
  retry_count_web: number;
  retry_count_telegram: number;
  retry_count_x: number;
  last_error_web?: string | null;
  last_error_telegram?: string | null;
  last_error_x?: string | null;
  external_telegram_message_id?: string | null;
  external_x_post_id?: string | null;
  external_web_id?: string | null;
  next_retry_telegram_at?: string | null;
  next_retry_x_at?: string | null;
  next_retry_web_at?: string | null;
  generated_at: string;
  published_web_at?: string | null;
  published_telegram_at?: string | null;
  published_x_at?: string | null;
  created_at: string;
  updated_at: string;
  event_title?: string | null;
  event_summary_zh?: string | null;
  event_type?: string | null;
  event_detected_at?: string | null;
};
