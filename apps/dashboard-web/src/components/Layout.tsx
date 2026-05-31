import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/timeline", label: "Timeline" },
  { to: "/events", label: "Events" },
  { to: "/sources", label: "Sources" },
  { to: "/processing", label: "Processing" },
  { to: "/alerts", label: "Alerts" }
];

type Theme = "radar-light" | "radar-dark";

function currentTheme(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "radar-dark" ? "radar-dark" : "radar-light";
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch {
      // Ignore storage failures (e.g. private mode); the in-page theme still applies.
    }
  }, [theme]);

  const next = theme === "radar-dark" ? "radar-light" : "radar-dark";
  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm btn-circle"
      aria-label={`Switch to ${next === "radar-dark" ? "dark" : "light"} theme`}
      title={`Switch to ${next === "radar-dark" ? "dark" : "light"} theme`}
      onClick={() => setTheme(next)}
    >
      {theme === "radar-dark" ? (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
        </svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-base-300 bg-base-100">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div>
            <div className="text-lg font-semibold">XAUUSD Event Radar</div>
            <div className="text-xs text-base-content/55">News operations dashboard</div>
          </div>
          <nav className="flex flex-wrap items-center gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `btn btn-sm ${isActive ? "btn-primary" : "btn-ghost"}`}
              >
                {item.label}
              </NavLink>
            ))}
            <ThemeToggle />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-5">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-4 flex flex-col gap-1">
      <h1 className="text-xl font-semibold">{title}</h1>
      {description ? <p className="text-sm text-base-content/60">{description}</p> : null}
    </div>
  );
}
