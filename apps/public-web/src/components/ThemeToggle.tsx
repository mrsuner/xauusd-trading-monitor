import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import { useAccountSession } from "../features/account/domain/queries";
import { useReaderPreferences, useSaveReaderPreferences } from "../features/reader-preferences/domain/queries";

const themes = ["tickbase-dark", "tickbase-light"] as const;
type Theme = (typeof themes)[number];

function readTheme(): Theme {
  const current = document.documentElement.getAttribute("data-theme");
  return current === "tickbase-light" ? "tickbase-light" : "tickbase-dark";
}

export function ThemeToggle() {
  const t = useI18n();
  const session = useAccountSession();
  const preferences = useReaderPreferences(session.isSuccess);
  const savePreferences = useSaveReaderPreferences();
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document === "undefined" ? "tickbase-dark" : readTheme()
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("tickbase-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!preferences.data) return;
    if (preferences.data.colorScheme !== "system") {
      setTheme(preferences.data.colorScheme === "dark" ? "tickbase-dark" : "tickbase-light");
      return;
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const followSystem = () => setTheme(media.matches ? "tickbase-dark" : "tickbase-light");
    followSystem();
    media.addEventListener("change", followSystem);
    return () => media.removeEventListener("change", followSystem);
  }, [preferences.data]);

  function toggleTheme() {
    const next = theme === "tickbase-dark" ? "tickbase-light" : "tickbase-dark";
    setTheme(next);
    if (preferences.data) {
      savePreferences.mutate(
        { ...preferences.data, colorScheme: next === "tickbase-dark" ? "dark" : "light" },
        { onError: () => setTheme(theme) }
      );
    }
  }

  return (
    <button
      type="button"
      className="btn btn-ghost btn-circle btn-sm"
      aria-label={t.nav.toggleTheme}
      title={t.nav.toggleTheme}
      disabled={session.isSuccess && (preferences.isPending || savePreferences.isPending)}
      onClick={toggleTheme}
    >
      {theme === "tickbase-dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
