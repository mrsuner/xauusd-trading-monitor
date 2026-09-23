import { accountRequest } from "../../account/domain/api";
import { mapReaderPreferences, readerPreferencesDto, type ReaderPreferences, type ReaderPreferencesDto } from "./models";

export async function getReaderPreferences(): Promise<ReaderPreferences> {
  const body = await accountRequest<{ data: ReaderPreferencesDto }>("/news/reader-preferences");
  return mapReaderPreferences(body.data);
}

export async function saveReaderPreferences(preferences: ReaderPreferences): Promise<ReaderPreferences> {
  const body = await accountRequest<{ data: ReaderPreferencesDto }>("/news/reader-preferences", {
    method: "PUT",
    body: readerPreferencesDto(preferences)
  });
  return mapReaderPreferences(body.data);
}
