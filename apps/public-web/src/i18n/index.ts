import { useLocation, useParams } from "react-router-dom";

import { defaultLanguage, supportedLanguageSet, type UiLanguage } from "./languages";
import { en, type Dictionary } from "./locales/en";
import { zhHant } from "./locales/zh-Hant";
export { defaultLanguage, languageLabels, supportedLanguages } from "./languages";
export type { Dictionary, UiLanguage };

export const dictionaries = {
  en,
  "zh-Hant": zhHant
} satisfies Record<UiLanguage, Dictionary>;

export function isLanguage(value: string | undefined): value is UiLanguage {
  return Boolean(value && supportedLanguageSet.has(value));
}

export function normalizeLanguage(value: string | null | undefined): UiLanguage {
  const candidate = value ?? undefined;
  return isLanguage(candidate) ? candidate : defaultLanguage;
}

export function useLanguage(): UiLanguage {
  const { lang } = useParams();
  return normalizeLanguage(lang);
}

export function useI18n(): Dictionary {
  return dictionaries[useLanguage()];
}

export function localizedPath(lang: UiLanguage, path: string, search = ""): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `/${lang}${normalizedPath}${search}`;
}

export function stripLanguagePrefix(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length > 0 && isLanguage(segments[0])) {
    return `/${segments.slice(1).join("/")}`;
  }
  return pathname === "/" ? "/events" : pathname;
}

export function useLocalizedPath() {
  const lang = useLanguage();
  return (path: string, search = "") => localizedPath(lang, path, search);
}

export function useLanguageSwitchPath(targetLang: UiLanguage): string {
  const location = useLocation();
  const pathWithoutLanguage = stripLanguagePrefix(location.pathname);
  return localizedPath(targetLang, pathWithoutLanguage, location.search);
}
