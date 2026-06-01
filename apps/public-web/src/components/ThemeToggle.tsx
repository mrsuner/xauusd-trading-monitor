import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

const themes = ["tickbase-dark", "tickbase-light"] as const;
type Theme = (typeof themes)[number];

function readTheme(): Theme {
  const current = document.documentElement.getAttribute("data-theme");
  return current === "tickbase-light" ? "tickbase-light" : "tickbase-dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document === "undefined" ? "tickbase-dark" : readTheme()
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("tickbase-theme", theme);
  }, [theme]);

  return (
    <button
      type="button"
      className="btn btn-ghost btn-circle btn-sm"
      aria-label="Toggle theme"
      title="Toggle theme"
      onClick={() => setTheme(theme === "tickbase-dark" ? "tickbase-light" : "tickbase-dark")}
    >
      {theme === "tickbase-dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
