import type { EventTranslation } from "../api/types";

export function eventSummary(translations: EventTranslation[] | undefined, language?: string | null) {
  const preferred = language?.startsWith("zh") ? "zh-Hant" : "en";
  return (
    translations?.find((item) => item.language === preferred)?.summary
    ?? translations?.find((item) => item.language === "zh-Hant")?.summary
    ?? translations?.find((item) => item.language === "en")?.summary
    ?? translations?.[0]?.summary
  );
}
