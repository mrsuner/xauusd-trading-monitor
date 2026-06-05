import type { PublicEvent } from "../api/types";

const dateFormatter = new Intl.DateTimeFormat("zh-Hant", {
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
});

const fullDateFormatter = new Intl.DateTimeFormat("zh-Hant", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
});

export function eventTitle(event: PublicEvent): string {
  return event.title || event.public_title_en || event.public_title_zh || "Untitled public event";
}

export function eventSummary(event: PublicEvent): string {
  return event.summary || event.public_summary_en || event.public_summary_zh || "No public summary is available.";
}

export function eventTimestamp(event: PublicEvent): string | null {
  return event.event_time || event.generated_at || event.received_at;
}

export function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "時間未定";
  }
  return dateFormatter.format(new Date(value));
}

export function formatFullTime(value: string | null | undefined): string {
  if (!value) {
    return "時間未定";
  }
  return fullDateFormatter.format(new Date(value));
}

export function relevanceBand(score: number | null): { label: string; className: string } {
  if (score === null || score === undefined) {
    return { label: "Unscored", className: "badge-ghost" };
  }
  if (score >= 85) {
    return { label: "High", className: "badge-primary" };
  }
  if (score >= 65) {
    return { label: "Watch", className: "badge-warning" };
  }
  return { label: "Info", className: "badge-ghost" };
}

export function displayCategory(category: string | null): string {
  if (!category) {
    return "uncategorized";
  }
  return category.replaceAll("_", " ");
}
