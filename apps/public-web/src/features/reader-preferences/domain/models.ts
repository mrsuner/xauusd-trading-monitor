import type { Severity } from "../../../api/types";

export type ContentLanguage = "zh-Hant" | "en";
export type ColorSchemePreference = "system" | "light" | "dark";

export interface ReaderPreferences {
  contentLanguage: ContentLanguage;
  minSeverity: Severity;
  colorScheme: ColorSchemePreference;
}

export interface ReaderPreferencesDto {
  content_language: ContentLanguage;
  min_severity: Severity;
  color_scheme: ColorSchemePreference;
}

export function mapReaderPreferences(dto: ReaderPreferencesDto): ReaderPreferences {
  return {
    contentLanguage: dto.content_language,
    minSeverity: dto.min_severity,
    colorScheme: dto.color_scheme
  };
}

export function readerPreferencesDto(preferences: ReaderPreferences): ReaderPreferencesDto {
  return {
    content_language: preferences.contentLanguage,
    min_severity: preferences.minSeverity,
    color_scheme: preferences.colorScheme
  };
}
