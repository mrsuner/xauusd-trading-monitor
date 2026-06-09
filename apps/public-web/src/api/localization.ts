import type { Language, PublicEvent, PublicEventTranslation } from "./types";

export const defaultContentLanguage = "en";
export const legacyChineseLanguage = "zh-Hant";

export function normalizeContentLanguage(lang: Language | null | undefined): Language {
  const normalized = String(lang ?? "").trim();
  return normalized || defaultContentLanguage;
}

export function localizePublicEvent(event: PublicEvent, lang: Language | null | undefined = defaultContentLanguage): PublicEvent {
  const requestedLanguage = normalizeContentLanguage(lang);
  const translations = publicEventTranslationRows(event);
  const selectedLanguage = selectPublicEventLanguage(translations, requestedLanguage);

  return {
    ...event,
    title: localizedPublicEventValue(translations, "title", selectedLanguage) ?? event.title,
    summary: localizedPublicEventValue(translations, "summary", selectedLanguage) ?? event.summary,
    language: selectedLanguage,
    available_languages: translations.map((translation) => translation.language),
    translations
  };
}

export function publicEventTranslationRows(event: PublicEvent): PublicEventTranslation[] {
  const rows: PublicEventTranslation[] = [];
  const seen = new Set<Language>();

  for (const translation of event.translations ?? []) {
    addTranslation(rows, seen, translation.language, translation.title, translation.summary);
  }

  addTranslation(rows, seen, defaultContentLanguage, event.public_title_en, event.public_summary_en);
  addTranslation(rows, seen, legacyChineseLanguage, event.public_title_zh, event.public_summary_zh);
  addTranslation(rows, seen, event.language, event.title, event.summary);

  return rows.sort(
    (a, b) => languageSortKey(a.language) - languageSortKey(b.language) || a.language.localeCompare(b.language)
  );
}

export function localizedPublicEventValue(
  translations: PublicEventTranslation[],
  field: "title" | "summary",
  selectedLanguage: Language
): string | null {
  const selectedValue = translationValue(translations, selectedLanguage, field);
  if (selectedValue) {
    return selectedValue;
  }
  const englishValue = translationValue(translations, defaultContentLanguage, field);
  if (englishValue) {
    return englishValue;
  }
  return translations.find((translation) => translation[field])?.[field] ?? null;
}

function selectPublicEventLanguage(translations: PublicEventTranslation[], requestedLanguage: Language): Language {
  if (hasPublicContent(translations, requestedLanguage)) {
    return requestedLanguage;
  }
  if (hasPublicContent(translations, defaultContentLanguage)) {
    return defaultContentLanguage;
  }
  return translations.find((translation) => hasTranslationContent(translation))?.language ?? requestedLanguage;
}

function addTranslation(
  rows: PublicEventTranslation[],
  seen: Set<Language>,
  language: Language | null | undefined,
  title: string | null | undefined,
  summary: string | null | undefined
) {
  const normalizedLanguage = normalizeContentLanguage(language);
  if (seen.has(normalizedLanguage)) {
    return;
  }
  const normalizedTitle = normalizeOptionalText(title);
  const normalizedSummary = normalizeOptionalText(summary);
  if (!normalizedTitle && !normalizedSummary) {
    return;
  }
  rows.push({ language: normalizedLanguage, title: normalizedTitle, summary: normalizedSummary });
  seen.add(normalizedLanguage);
}

function normalizeOptionalText(value: string | null | undefined): string | null {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function hasPublicContent(translations: PublicEventTranslation[], language: Language): boolean {
  return translations.some((translation) => translation.language === language && hasTranslationContent(translation));
}

function hasTranslationContent(translation: PublicEventTranslation): boolean {
  return Boolean(translation.title || translation.summary);
}

function translationValue(
  translations: PublicEventTranslation[],
  language: Language,
  field: "title" | "summary"
): string | null {
  return translations.find((translation) => translation.language === language)?.[field] ?? null;
}

function languageSortKey(language: Language): number {
  if (language === defaultContentLanguage) {
    return 0;
  }
  if (language === legacyChineseLanguage) {
    return 1;
  }
  return 2;
}
