import { useLanguage } from "../i18n";
import type { UiLanguage } from "../i18n";

/**
 * Final fallback support URL, used when no per-language override is configured.
 * Mirrors the historical hardcoded Ko-fi link.
 */
export const DEFAULT_SUPPORT_URL = "https://ko-fi.com/alphablue";

/**
 * Per-language support links, configured at runtime via
 * `window.__TICKBASE_NEWS_CONFIG__.PUBLIC_SUPPORT_URLS` (preferred, set at deploy
 * time) or the build-time `VITE_PUBLIC_SUPPORT_URLS` fallback.
 *
 * Format: comma-separated `lang=url` pairs, e.g.
 *   "en=https://ko-fi.com/alphablue,zh-Hant=https://example.com/zh"
 */
const supportUrlMap = parseSupportUrls(
  window.__TICKBASE_NEWS_CONFIG__?.PUBLIC_SUPPORT_URLS || import.meta.env.VITE_PUBLIC_SUPPORT_URLS
);

export function supportUrlFor(lang: UiLanguage): string {
  return supportUrlMap[lang] ?? DEFAULT_SUPPORT_URL;
}

export function useSupportUrl(): string {
  return supportUrlFor(useLanguage());
}

function parseSupportUrls(value: string | undefined): Partial<Record<UiLanguage, string>> {
  const map: Partial<Record<UiLanguage, string>> = {};
  for (const entry of String(value ?? "").split(",")) {
    const trimmed = entry.trim();
    if (!trimmed) {
      continue;
    }
    // Split on the FIRST "=" only, so "=" in URL query strings is preserved.
    const separator = trimmed.indexOf("=");
    if (separator === -1) {
      continue;
    }
    const lang = trimmed.slice(0, separator).trim();
    const url = trimmed.slice(separator + 1).trim();
    if (lang && url) {
      map[lang as UiLanguage] = url;
    }
  }
  return map;
}
