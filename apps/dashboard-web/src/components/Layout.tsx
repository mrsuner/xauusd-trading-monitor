import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { persistLanguage, type Language } from "../i18n";

const navItems = [
  { to: "/", labelKey: "nav.overview" },
  { to: "/timeline", labelKey: "nav.timeline" },
  { to: "/events", labelKey: "nav.events" },
  { to: "/sources", labelKey: "nav.sources" },
  { to: "/processing", labelKey: "nav.processing" },
  { to: "/alerts", labelKey: "nav.alerts" }
];

type Theme = "radar-light" | "radar-dark";

function currentTheme(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "radar-dark" ? "radar-dark" : "radar-light";
}

function ThemeToggle() {
  const { t } = useTranslation();
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
  const label = next === "radar-dark" ? t("layout.switchToDark") : t("layout.switchToLight");
  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm btn-circle"
      aria-label={label}
      title={label}
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

function LanguageToggle() {
  const { t, i18n } = useTranslation();
  const current = (i18n.resolvedLanguage ?? "en") as Language;
  const next: Language = current === "zh-Hant" ? "en" : "zh-Hant";
  const shortLabel = current === "zh-Hant" ? "中" : "EN";

  const switchLanguage = () => {
    void i18n.changeLanguage(next);
    persistLanguage(next);
    document.documentElement.lang = next;
  };

  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm btn-circle text-xs font-semibold"
      aria-label={t("layout.switchLanguage")}
      title={t("layout.switchLanguage")}
      onClick={switchLanguage}
    >
      {shortLabel}
    </button>
  );
}

function MenuIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function Brand() {
  const { t } = useTranslation();
  return (
    <div className="min-w-0">
      <div className="truncate text-lg font-semibold">{t("common.brand")}</div>
      <div className="truncate text-xs text-base-content/55">{t("common.tagline")}</div>
    </div>
  );
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();
  return (
    <nav className="flex flex-col gap-1">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={onNavigate}
          className={({ isActive }) =>
            [
              "rounded px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-content"
                : "text-base-content/72 hover:bg-base-200 hover:text-base-content"
            ].join(" ")
          }
        >
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="hidden min-h-screen border-r border-base-300 bg-base-100 lg:flex lg:flex-col">
        <div className="border-b border-base-300 px-4 py-4">
          <Brand />
        </div>
        <div className="flex min-h-0 flex-1 flex-col justify-between gap-4 p-3">
          <Navigation />
          <div className="flex items-center justify-between rounded border border-base-300 bg-base-200/60 px-3 py-2">
            <span className="text-xs text-base-content/60">{t("common.theme")}</span>
            <div className="flex items-center gap-1">
              <LanguageToggle />
              <ThemeToggle />
            </div>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 border-b border-base-300 bg-base-100/95 backdrop-blur lg:hidden">
          <div className="flex min-w-0 items-center justify-between gap-3 px-3 py-3">
            <button
              type="button"
              className="btn btn-ghost btn-sm btn-circle shrink-0"
              aria-label={t("layout.openNav")}
              title={t("layout.openNav")}
              onClick={() => setMobileNavOpen(true)}
            >
              <MenuIcon />
            </button>
            <Brand />
            <div className="flex shrink-0 items-center gap-1">
              <LanguageToggle />
              <ThemeToggle />
            </div>
          </div>
        </header>

        {mobileNavOpen ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              className="absolute inset-0 bg-black/35"
              aria-label={t("layout.closeNav")}
              onClick={() => setMobileNavOpen(false)}
            />
            <aside className="relative flex h-full w-72 max-w-[86vw] flex-col border-r border-base-300 bg-base-100 shadow-xl">
              <div className="flex items-center justify-between gap-3 border-b border-base-300 px-4 py-4">
                <Brand />
                <button
                  type="button"
                  className="btn btn-ghost btn-sm btn-circle shrink-0"
                  aria-label={t("layout.closeNav")}
                  title={t("layout.closeNav")}
                  onClick={() => setMobileNavOpen(false)}
                >
                  <CloseIcon />
                </button>
              </div>
              <div className="p-3">
                <Navigation onNavigate={() => setMobileNavOpen(false)} />
              </div>
            </aside>
          </div>
        ) : null}

        <main className="mx-auto min-w-0 max-w-[1600px] px-3 py-4 sm:px-4 lg:px-6 lg:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-4 flex min-w-0 flex-col gap-1">
      <h1 className="break-words text-xl font-semibold">{title}</h1>
      {description ? <p className="text-sm text-base-content/60">{description}</p> : null}
    </div>
  );
}
