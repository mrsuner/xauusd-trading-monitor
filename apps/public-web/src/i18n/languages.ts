export type UiLanguage = "en" | "zh-Hant";

export const defaultLanguage: UiLanguage = "en";
export const supportedLanguages = ["en", "zh-Hant"] as const satisfies readonly UiLanguage[];
export const supportedLanguageSet = new Set<string>(supportedLanguages);

export const languageLabels: Record<UiLanguage, string> = {
  en: "EN",
  "zh-Hant": "繁中"
};
