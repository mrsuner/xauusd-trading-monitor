export type UiLanguage = "en" | "zh-Hant" | "ja" | "th";

export const builtInLanguages = ["en", "zh-Hant", "ja", "th"] as const satisfies readonly UiLanguage[];
export const supportedLanguages = runtimeSupportedLanguages();
export const supportedLanguageSet = new Set<string>(supportedLanguages);
export const defaultLanguage = runtimeDefaultLanguage(supportedLanguages);

export const languageLabels: Record<UiLanguage, string> = {
  en: "EN",
  "zh-Hant": "繁中",
  ja: "日本語",
  th: "ไทย"
};

function runtimeSupportedLanguages(): UiLanguage[] {
  const configured = parseLanguageList(
    window.__TICKBASE_NEWS_CONFIG__?.PUBLIC_SUPPORTED_LANGUAGES ||
      import.meta.env.VITE_PUBLIC_SUPPORTED_LANGUAGES
  );
  const supported = configured.filter(isBuiltInLanguage);
  return supported.length > 0 ? supported : [...builtInLanguages];
}

function runtimeDefaultLanguage(supported: UiLanguage[]): UiLanguage {
  const configured =
    window.__TICKBASE_NEWS_CONFIG__?.PUBLIC_DEFAULT_LANGUAGE || import.meta.env.VITE_PUBLIC_DEFAULT_LANGUAGE;
  if (isBuiltInLanguage(configured) && supported.includes(configured)) {
    return configured;
  }
  if (supported.includes("en")) {
    return "en";
  }
  return supported[0] ?? "en";
}

function parseLanguageList(value: string | string[] | undefined): string[] {
  if (Array.isArray(value)) {
    return value;
  }
  return String(value ?? "")
    .split(",")
    .map((language) => language.trim())
    .filter(Boolean);
}

function isBuiltInLanguage(value: string | undefined): value is UiLanguage {
  return Boolean(value && (builtInLanguages as readonly string[]).includes(value));
}
