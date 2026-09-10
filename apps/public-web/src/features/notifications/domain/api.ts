import type { ChannelDto, DeliveryLanguage, DigestEditionDto, DigestPreferences, DigestPreferencesDto, DigestTopic, NewsAccess, NotificationPreferences, PreferencesDto } from "./models";
import { mapChannel, mapDigestPreferences, mapPreferences, preferencesDto } from "./models";

const runtimeConfig = window.__TICKBASE_NEWS_CONFIG__ ?? {};
const accountApiBaseUrl =
  runtimeConfig.ACCOUNT_API_BASE_URL ||
  import.meta.env.VITE_ACCOUNT_API_BASE_URL ||
  "https://account.thetickbase.com/api/v1";

const mutatingMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;

export class AccountApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields?: Record<string, string[]>
  ) {
    super(message);
    this.name = "AccountApiError";
  }
}

export async function getPreferences(): Promise<{ access: NewsAccess; preferences: NotificationPreferences }> {
  const body = await request<{ data: { access: NewsAccess; preferences: PreferencesDto } }>("/news/preferences");
  return { access: body.data.access, preferences: mapPreferences(body.data.preferences) };
}

export async function savePreferences(preferences: NotificationPreferences): Promise<NotificationPreferences> {
  const body = await request<{ data: { preferences: PreferencesDto } }>("/news/preferences", {
    method: "PUT",
    body: preferencesDto(preferences)
  });
  return mapPreferences(body.data.preferences);
}

export async function getChannels() {
  const body = await request<{ data: ChannelDto[] }>("/news/channels");
  return body.data.map(mapChannel);
}

export async function createTelegramLink(): Promise<{ deepLink: string; expiresAt: string }> {
  const body = await request<{ data: { deep_link: string; expires_at: string } }>(
    "/news/channels/telegram/link",
    { method: "POST", body: {} }
  );
  return { deepLink: body.data.deep_link, expiresAt: body.data.expires_at };
}

export async function setTelegramEnabled(enabled: boolean) {
  const body = await request<{ data: ChannelDto }>("/news/channels/telegram", {
    method: "PATCH",
    body: { enabled }
  });
  return mapChannel(body.data);
}

export async function unlinkTelegram(): Promise<void> {
  await request<null>("/news/channels/telegram", { method: "DELETE" });
}

export async function getDigestPreferences(): Promise<{ access: NewsAccess; preferences: DigestPreferences; availableTopics: DigestTopic[] }> {
  const body = await request<{ data: { access: NewsAccess; preferences: DigestPreferencesDto; available_topics: DigestTopic[] } }>("/news/digest-preferences");
  return { access: body.data.access, preferences: mapDigestPreferences(body.data.preferences), availableTopics: body.data.available_topics };
}

export async function saveDigestPreferences(input: Pick<DigestPreferences, "enabled" | "topics">): Promise<DigestPreferences> {
  const body = await request<{ data: { preferences: DigestPreferencesDto } }>("/news/digest-preferences", {
    method: "PUT",
    body: { enabled: input.enabled, topics: input.topics }
  });
  return mapDigestPreferences(body.data.preferences);
}

export async function getDigests(language: DeliveryLanguage): Promise<DigestEditionDto[]> {
  const body = await request<{ data: DigestEditionDto[] }>(`/news/digests?language=${encodeURIComponent(language)}`);
  return body.data;
}

export async function getDigest(id: string, language: DeliveryLanguage): Promise<DigestEditionDto> {
  const body = await request<{ data: DigestEditionDto }>(`/news/digests/${encodeURIComponent(id)}?language=${encodeURIComponent(language)}`);
  return body.data;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (mutatingMethods.has(method)) {
    headers["X-CSRF-TOKEN"] = await ensureCsrfToken();
  }
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`${accountApiBaseUrl.replace(/\/$/, "")}${path}`, {
    method,
    headers,
    body,
    credentials: "include"
  });
  if (response.status === 204) return null as T;
  const payload = await parseJson(response);
  if (!response.ok) {
    if (response.status === 419) csrfToken = null;
    const error = payload as { error?: string; message?: string; fields?: Record<string, string[]> } | null;
    throw new AccountApiError(
      response.status,
      error?.error ?? "request_failed",
      error?.message ?? "Account request failed.",
      error?.fields
    );
  }
  return payload as T;
}

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch(`${accountApiBaseUrl.replace(/\/$/, "")}/auth/web/csrf-token`, {
    credentials: "include",
    headers: { Accept: "application/json" }
  });
  const payload = await parseJson(response) as { data?: { csrf_token?: string }; message?: string } | null;
  if (!response.ok || !payload?.data?.csrf_token) {
    throw new AccountApiError(response.status || 500, "csrf_unavailable", payload?.message ?? "CSRF protection is unavailable.");
  }
  csrfToken = payload.data.csrf_token;
  return csrfToken;
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
