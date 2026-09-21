import type { ChannelDto, DeliveryLanguage, DigestEditionDto, DigestPreferences, DigestPreferencesDto, DigestTopic, NewsAccess, NotificationPreferences, PreferencesDto } from "./models";
import { mapChannel, mapDigestPreferences, mapPreferences, preferencesDto } from "./models";
import { accountRequest } from "../../account/domain/api";
export { AccountApiError } from "../../account/domain/api";

export async function getPreferences(): Promise<{ access: NewsAccess; preferences: NotificationPreferences }> {
  const body = await accountRequest<{ data: { access: NewsAccess; preferences: PreferencesDto } }>("/news/preferences");
  return { access: body.data.access, preferences: mapPreferences(body.data.preferences) };
}

export async function savePreferences(preferences: NotificationPreferences): Promise<NotificationPreferences> {
  const body = await accountRequest<{ data: { preferences: PreferencesDto } }>("/news/preferences", {
    method: "PUT",
    body: preferencesDto(preferences)
  });
  return mapPreferences(body.data.preferences);
}

export async function getChannels() {
  const body = await accountRequest<{ data: ChannelDto[] }>("/news/channels");
  return body.data.map(mapChannel);
}

export async function createTelegramLink(): Promise<{ deepLink: string; expiresAt: string }> {
  const body = await accountRequest<{ data: { deep_link: string; expires_at: string } }>(
    "/news/channels/telegram/link",
    { method: "POST", body: {} }
  );
  return { deepLink: body.data.deep_link, expiresAt: body.data.expires_at };
}

export async function setTelegramEnabled(enabled: boolean) {
  const body = await accountRequest<{ data: ChannelDto }>("/news/channels/telegram", {
    method: "PATCH",
    body: { enabled }
  });
  return mapChannel(body.data);
}

export async function unlinkTelegram(): Promise<void> {
  await accountRequest<null>("/news/channels/telegram", { method: "DELETE" });
}

export async function getDigestPreferences(): Promise<{ access: NewsAccess; preferences: DigestPreferences; availableTopics: DigestTopic[] }> {
  const body = await accountRequest<{ data: { access: NewsAccess; preferences: DigestPreferencesDto; available_topics: DigestTopic[] } }>("/news/digest-preferences");
  return { access: body.data.access, preferences: mapDigestPreferences(body.data.preferences), availableTopics: body.data.available_topics };
}

export async function saveDigestPreferences(input: Pick<DigestPreferences, "enabled" | "topics">): Promise<DigestPreferences> {
  const body = await accountRequest<{ data: { preferences: DigestPreferencesDto } }>("/news/digest-preferences", {
    method: "PUT",
    body: { enabled: input.enabled, topics: input.topics }
  });
  return mapDigestPreferences(body.data.preferences);
}

export async function getDigests(language: DeliveryLanguage): Promise<DigestEditionDto[]> {
  const body = await accountRequest<{ data: DigestEditionDto[] }>(`/news/digests?language=${encodeURIComponent(language)}`);
  return body.data;
}

export async function getDigest(id: string, language: DeliveryLanguage): Promise<DigestEditionDto> {
  const body = await accountRequest<{ data: DigestEditionDto }>(`/news/digests/${encodeURIComponent(id)}?language=${encodeURIComponent(language)}`);
  return body.data;
}
