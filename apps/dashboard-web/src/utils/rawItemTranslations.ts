import type { RawItemTranslation } from "../api/types";

const ENGLISH = "en";
const ZH_HANT = "zh-Hant";

type RawItemTranslationSource = {
  translations?: RawItemTranslation[];
  summary_zh?: string | null;
  summary_en?: string | null;
  full_translation_zh?: string | null;
  full_translation_en?: string | null;
  text_clean?: string | null;
  text_raw?: string | null;
  title?: string | null;
};

export type RawItemFullTranslation = {
  language: string;
  text: string;
};

function text(value?: string | null): string | undefined {
  return value && value.trim() ? value : undefined;
}

export function normalizeRawItemLanguage(language?: string | null): string {
  return language?.startsWith("zh") ? ZH_HANT : ENGLISH;
}

function preferredLanguages(language?: string | null): string[] {
  const preferred = normalizeRawItemLanguage(language);
  return [preferred, ENGLISH, ZH_HANT].filter((value, index, values) => values.indexOf(value) === index);
}

function translationFor(item: RawItemTranslationSource, language: string): RawItemTranslation | undefined {
  return item.translations?.find((translation) => translation.language === language);
}

function summaryForLanguage(item: RawItemTranslationSource, language: string): string | undefined {
  const translated = text(translationFor(item, language)?.summary);
  if (translated) return translated;
  return language === ZH_HANT ? text(item.summary_zh) : text(item.summary_en);
}

function fullTranslationForLanguage(item: RawItemTranslationSource, language: string): string | undefined {
  const translated = text(translationFor(item, language)?.full_translation);
  if (translated) return translated;
  return language === ZH_HANT ? text(item.full_translation_zh) : text(item.full_translation_en);
}

export function rawItemSummary(item: RawItemTranslationSource, language?: string | null): string | undefined {
  for (const candidate of preferredLanguages(language)) {
    const summary = summaryForLanguage(item, candidate);
    if (summary) return summary;
  }

  const translated = item.translations?.find((translation) => text(translation.summary));
  return text(translated?.summary);
}

export function rawItemFullTranslation(item: RawItemTranslationSource, language?: string | null): string | undefined {
  for (const candidate of preferredLanguages(language)) {
    const fullTranslation = fullTranslationForLanguage(item, candidate);
    if (fullTranslation) return fullTranslation;
  }

  const translated = item.translations?.find((translation) => text(translation.full_translation));
  return text(translated?.full_translation);
}

export function rawItemFullTranslations(item: RawItemTranslationSource, language?: string | null): RawItemFullTranslation[] {
  const languages = [
    ...preferredLanguages(language),
    ...(item.translations?.map((translation) => translation.language) ?? [])
  ].filter((value, index, values) => values.indexOf(value) === index);

  return languages.flatMap((candidate) => {
    const fullTranslation = fullTranslationForLanguage(item, candidate);
    return fullTranslation ? [{ language: candidate, text: fullTranslation }] : [];
  });
}

export function rawItemOriginalContent(item: RawItemTranslationSource): string | undefined {
  return text(item.text_clean) || text(item.text_raw) || text(item.title);
}

export function rawItemDisplaySummary(item: RawItemTranslationSource, language?: string | null, fallback = "-"): string {
  return rawItemSummary(item, language) || rawItemOriginalContent(item) || fallback;
}
