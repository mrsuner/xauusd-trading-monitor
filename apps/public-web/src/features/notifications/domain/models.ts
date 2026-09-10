export type NewsAccess = "active" | "upgrade_required";
export type DeliveryLanguage = "zh-Hant" | "en";
export type DeliverySeverity = "S" | "A" | "B" | "C";

export interface NotificationPreferences {
  masterEnabled: boolean;
  matchAllCategories: boolean;
  minSeverity: DeliverySeverity;
  contentLanguage: DeliveryLanguage;
  categories: string[];
  tags: string[];
  revision: number;
  effectiveFrom: string | null;
}

export interface NotificationChannel {
  type: "telegram";
  enabled: boolean;
  verified: boolean;
  targetHint: string | null;
  lastErrorCode: string | null;
  linkedAt: string | null;
  revision: number;
}

export interface PreferencesDto {
  master_enabled: boolean;
  match_all_categories: boolean;
  min_severity: DeliverySeverity;
  content_language: DeliveryLanguage;
  categories: string[];
  tags: string[];
  revision: number;
  effective_from: string | null;
}

export interface ChannelDto {
  type: "telegram";
  enabled: boolean;
  verified: boolean;
  target_hint: string | null;
  last_error_code: string | null;
  linked_at: string | null;
  revision: number;
}

export type DigestTopic = "geopolitics" | "monetary" | "energy" | "macro_data";

export interface DigestPreferences {
  enabled: boolean;
  topics: DigestTopic[];
  revision: number;
  effectiveFrom: string | null;
}

export interface DigestPreferencesDto {
  enabled: boolean;
  topics: DigestTopic[];
  revision: number;
  effective_from: string | null;
}

export interface DigestEditionDto {
  id: string;
  topic: DigestTopic;
  window_start: string;
  window_end: string;
  status: "ready" | "language_unavailable" | "invalidated";
  language: DeliveryLanguage | null;
  title: string | null;
  published_at: string | null;
  coverage_truncated: boolean;
  invalidation_kind: string | null;
  invalidation_reason: string | null;
  overview?: string | null;
  developments?: Array<{ text: string; event_ids: string[] }> | null;
  event_ids?: string[];
}

export function mapDigestPreferences(dto: DigestPreferencesDto): DigestPreferences {
  return { enabled: dto.enabled, topics: dto.topics, revision: dto.revision, effectiveFrom: dto.effective_from };
}

export function mapPreferences(dto: PreferencesDto): NotificationPreferences {
  return {
    masterEnabled: dto.master_enabled,
    matchAllCategories: dto.match_all_categories,
    minSeverity: dto.min_severity,
    contentLanguage: dto.content_language,
    categories: dto.categories,
    tags: dto.tags,
    revision: dto.revision,
    effectiveFrom: dto.effective_from
  };
}

export function preferencesDto(preferences: NotificationPreferences): Omit<PreferencesDto, "revision" | "effective_from"> {
  return {
    master_enabled: preferences.masterEnabled,
    match_all_categories: preferences.matchAllCategories,
    min_severity: preferences.minSeverity,
    content_language: preferences.contentLanguage,
    categories: preferences.categories,
    tags: preferences.tags
  };
}

export function mapChannel(dto: ChannelDto): NotificationChannel {
  return {
    type: dto.type,
    enabled: dto.enabled,
    verified: dto.verified,
    targetHint: dto.target_hint,
    lastErrorCode: dto.last_error_code,
    linkedAt: dto.linked_at,
    revision: dto.revision
  };
}
