import {
  localizedPublicEventValue,
  localizedPublicRawItemValue,
  publicEventTranslationRows,
  publicRawItemTranslationRows
} from "../api/localization";
import type { Language, PublicEvent, PublicRawItem, PublicSourceLink } from "../api/types";
import { dictionaries, type Dictionary } from "../i18n";

function dateFormatter(lang: Language) {
  return new Intl.DateTimeFormat(lang, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

function fullDateFormatter(lang: Language) {
  return new Intl.DateTimeFormat(lang, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

export function eventTitle(event: PublicEvent, t: Dictionary = dictionaries.en, lang: Language = "en"): string {
  const translations = publicEventTranslationRows(event);
  return localizedPublicEventValue(translations, "title", lang) || event.title || t.format.untitled;
}

export function eventSummary(event: PublicEvent, t: Dictionary = dictionaries.en, lang: Language = "en"): string {
  const translations = publicEventTranslationRows(event);
  return localizedPublicEventValue(translations, "summary", lang) || event.summary || t.format.noSummary;
}

export function eventTimestamp(event: PublicEvent): string | null {
  return event.event_time || event.generated_at || event.received_at;
}

export function rawItemTitle(item: PublicRawItem, t: Dictionary = dictionaries.en): string {
  return item.title || t.format.untitledRawItem;
}

export function rawItemSummary(item: PublicRawItem, t: Dictionary = dictionaries.en, lang: Language = "en"): string {
  const translations = publicRawItemTranslationRows(item);
  return localizedPublicRawItemValue(translations, "summary", lang) || item.summary || t.format.noRawSummary;
}

export function rawItemFullTranslation(item: PublicRawItem, lang: Language = "en"): string | null {
  const translations = publicRawItemTranslationRows(item);
  return localizedPublicRawItemValue(translations, "full_translation", lang) || item.full_translation || null;
}

export function rawItemTimestamp(item: PublicRawItem): string | null {
  return item.published_at || item.ingested_at || item.received_at;
}

export function rawItemSourceLabel(item: PublicRawItem, t: Dictionary = dictionaries.en): string {
  return item.source_name || item.source_group || t.raw.sourceFallback;
}

export function formatTime(value: string | null | undefined, lang: Language = "en", t: Dictionary = dictionaries.en): string {
  if (!value) {
    return t.format.timeUnknown;
  }
  return dateFormatter(lang).format(new Date(value));
}

export function formatFullTime(value: string | null | undefined, lang: Language = "en", t: Dictionary = dictionaries.en): string {
  if (!value) {
    return t.format.timeUnknown;
  }
  return fullDateFormatter(lang).format(new Date(value));
}

export function relevanceBand(score: number | null, t: Dictionary = dictionaries.en): { label: string; className: string } {
  if (score === null || score === undefined) {
    return { label: t.format.unscored, className: "badge-ghost" };
  }
  if (score >= 85) {
    return { label: t.format.high, className: "badge-primary" };
  }
  if (score >= 65) {
    return { label: t.format.watch, className: "badge-warning" };
  }
  return { label: t.format.info, className: "badge-ghost" };
}

export function displayCategory(category: string | null, t: Dictionary = dictionaries.en): string {
  if (!category) {
    return t.format.uncategorized;
  }
  return category.replaceAll("_", " ");
}

export function sourceLabel(source: PublicSourceLink, t: Dictionary = dictionaries.en): string {
  return source.source_name || source.label || t.detail.source;
}

export function sourceBackground(source: PublicSourceLink, t: Dictionary = dictionaries.en): string {
  const backgrounds: Record<string, string> = t.sources.backgrounds;
  const label = sourceLabel(source, t);
  const exactMatch = backgrounds[label];
  if (exactMatch) {
    return exactMatch;
  }
  const normalizedLabel = label.toLowerCase();
  const aliasMatch = Object.entries(backgrounds).find(([sourceName]) => {
    const normalizedSourceName = sourceName.toLowerCase();
    return (
      normalizedSourceName.length > 3 &&
      (normalizedLabel.includes(normalizedSourceName) || normalizedSourceName.includes(normalizedLabel))
    );
  });
  return aliasMatch?.[1] ?? t.sources.fallback;
}
