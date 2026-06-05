import type { Language, PublicEvent } from "../api/types";
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

export function eventTitle(event: PublicEvent, t: Dictionary = dictionaries.en): string {
  return event.title || event.public_title_en || event.public_title_zh || t.format.untitled;
}

export function eventSummary(event: PublicEvent, t: Dictionary = dictionaries.en): string {
  return event.summary || event.public_summary_en || event.public_summary_zh || t.format.noSummary;
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
