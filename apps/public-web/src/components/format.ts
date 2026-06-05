import type { Language, PublicEvent, PublicSourceLink } from "../api/types";
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
  const localizedTitle =
    lang === "zh-Hant"
      ? event.public_title_zh || event.public_title_en
      : event.public_title_en || event.public_title_zh;
  return event.title || localizedTitle || t.format.untitled;
}

export function eventSummary(event: PublicEvent, t: Dictionary = dictionaries.en, lang: Language = "en"): string {
  const localizedSummary =
    lang === "zh-Hant"
      ? event.public_summary_zh || event.public_summary_en
      : event.public_summary_en || event.public_summary_zh;
  return event.summary || localizedSummary || t.format.noSummary;
}

export function eventTimestamp(event: PublicEvent): string | null {
  return event.event_time || event.generated_at || event.received_at;
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
