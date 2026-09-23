import { useLanguage } from "../../../i18n";
import { useAccountSession } from "../../account/domain/queries";
import { useReaderPreferences } from "./queries";

/** Public reading remains available when the account API is unavailable. */
export function useAppliedReaderPreferences() {
  const interfaceLanguage = useLanguage();
  const session = useAccountSession();
  const preferences = useReaderPreferences(session.isSuccess);

  return {
    contentLanguage: preferences.data?.contentLanguage ?? interfaceLanguage,
    minSeverity: preferences.data?.minSeverity,
    ready: !session.isPending && (!session.isSuccess || !preferences.isPending),
  };
}
