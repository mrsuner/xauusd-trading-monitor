import { useLocation, useParams } from "react-router-dom";
import type { Language } from "../api/types";

export const defaultLanguage: Language = "en";
export const supportedLanguages: Language[] = ["en", "zh-Hant"];

export const languageLabels: Record<Language, string> = {
  en: "EN",
  "zh-Hant": "繁中"
};

export function isLanguage(value: string | undefined): value is Language {
  return value === "en" || value === "zh-Hant";
}

export function normalizeLanguage(value: string | null | undefined): Language {
  const candidate = value ?? undefined;
  return isLanguage(candidate) ? candidate : defaultLanguage;
}

export function useLanguage(): Language {
  const { lang } = useParams();
  return normalizeLanguage(lang);
}

export function localizedPath(lang: Language, path: string, search = ""): string {
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

export function useLanguageSwitchPath(targetLang: Language): string {
  const location = useLocation();
  const pathWithoutLanguage = stripLanguagePrefix(location.pathname);
  return localizedPath(targetLang, pathWithoutLanguage, location.search);
}
