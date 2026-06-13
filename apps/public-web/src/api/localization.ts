import type { Language, PublicEvent, PublicEventTranslation, PublicRawItem, PublicRawItemTranslation } from "./types";

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

export function localizePublicRawItem(
  item: PublicRawItem,
  lang: Language | null | undefined = defaultContentLanguage
): PublicRawItem {
  const requestedLanguage = normalizeContentLanguage(lang);
  const translations = publicRawItemTranslationRows(item);
  const selectedLanguage = selectPublicRawItemLanguage(translations, requestedLanguage);

  return {
    ...item,
    summary: localizedPublicRawItemValue(translations, "summary", selectedLanguage) ?? item.summary,
    full_translation:
      localizedPublicRawItemValue(translations, "full_translation", selectedLanguage) ?? item.full_translation,
    language: selectedLanguage,
    available_languages: translations.map((translation) => translation.language),
    translations
  };
}

export function publicRawItemTranslationRows(item: PublicRawItem): PublicRawItemTranslation[] {
  const rows: PublicRawItemTranslation[] = [];
  const seen = new Set<Language>();

  for (const translation of item.translations ?? []) {
    addRawItemTranslation(rows, seen, translation);
  }

  addRawItemTranslation(rows, seen, {
    language: defaultContentLanguage,
    summary: item.summary_en,
    full_translation: item.full_translation_en,
    is_truncated: item.is_truncated,
    source_chars: item.source_text_chars,
    translation_chars: item.translation_chars
  });
  addRawItemTranslation(rows, seen, {
    language: legacyChineseLanguage,
    summary: item.summary_zh,
    full_translation: item.full_translation_zh,
    is_truncated: item.is_truncated,
    source_chars: item.source_text_chars,
    translation_chars: item.translation_chars
  });
  addRawItemTranslation(rows, seen, {
    language: item.language,
    summary: item.summary,
    full_translation: item.full_translation,
    is_truncated: item.is_truncated,
    source_chars: item.source_text_chars,
    translation_chars: item.translation_chars
  });

  return rows.sort(
    (a, b) => languageSortKey(a.language) - languageSortKey(b.language) || a.language.localeCompare(b.language)
  );
}

export function localizedPublicRawItemValue(
  translations: PublicRawItemTranslation[],
  field: "summary" | "full_translation",
  selectedLanguage: Language
): string | null {
  const selectedValue = rawItemTranslationValue(translations, selectedLanguage, field);
  if (selectedValue) {
    return selectedValue;
  }
  const englishValue = rawItemTranslationValue(translations, defaultContentLanguage, field);
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

function selectPublicRawItemLanguage(translations: PublicRawItemTranslation[], requestedLanguage: Language): Language {
  if (hasRawItemContent(translations, requestedLanguage)) {
    return requestedLanguage;
  }
  if (hasRawItemContent(translations, defaultContentLanguage)) {
    return defaultContentLanguage;
  }
  return translations.find((translation) => hasRawItemTranslationContent(translation))?.language ?? requestedLanguage;
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

function addRawItemTranslation(
  rows: PublicRawItemTranslation[],
  seen: Set<Language>,
  translation: PublicRawItemTranslation
) {
  const normalizedLanguage = normalizeContentLanguage(translation.language);
  if (seen.has(normalizedLanguage)) {
    return;
  }
  const normalizedSummary = normalizeOptionalText(translation.summary);
  const normalizedFullTranslation = normalizeOptionalText(translation.full_translation);
  if (!normalizedSummary && !normalizedFullTranslation) {
    return;
  }
  rows.push({
    ...translation,
    language: normalizedLanguage,
    summary: normalizedSummary,
    full_translation: normalizedFullTranslation
  });
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

function hasRawItemContent(translations: PublicRawItemTranslation[], language: Language): boolean {
  return translations.some((translation) => translation.language === language && hasRawItemTranslationContent(translation));
}

function hasRawItemTranslationContent(translation: PublicRawItemTranslation): boolean {
  return Boolean(translation.summary || translation.full_translation);
}

function translationValue(
  translations: PublicEventTranslation[],
  language: Language,
  field: "title" | "summary"
): string | null {
  return translations.find((translation) => translation.language === language)?.[field] ?? null;
}

function rawItemTranslationValue(
  translations: PublicRawItemTranslation[],
  language: Language,
  field: "summary" | "full_translation"
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
