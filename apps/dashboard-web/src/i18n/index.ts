import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import zhHant from "./locales/zh-Hant.json";

export const SUPPORTED_LANGUAGES = ["en", "zh-Hant"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

const STORAGE_KEY = "language";
const FALLBACK_LANGUAGE: Language = "en";

function storedLanguage(): Language {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value && (SUPPORTED_LANGUAGES as readonly string[]).includes(value)) {
      return value as Language;
    }
  } catch {
    // Ignore storage failures (e.g. private mode); fall back to default.
  }
  return FALLBACK_LANGUAGE;
}

export function persistLanguage(language: Language) {
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // Ignore storage failures (e.g. private mode); the in-page language still applies.
  }
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    "zh-Hant": { translation: zhHant }
  },
  lng: storedLanguage(),
  fallbackLng: FALLBACK_LANGUAGE,
  interpolation: { escapeValue: false }
});

document.documentElement.lang = i18n.resolvedLanguage ?? FALLBACK_LANGUAGE;

export default i18n;
