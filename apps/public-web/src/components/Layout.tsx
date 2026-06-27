import { Coffee, Languages, Menu } from "lucide-react";
import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { KOFI_URL } from "../pages/SupportPage";
import {
  languageLabels,
  localizedPath,
  stripLanguagePrefix,
  supportedLanguages,
  useI18n,
  useLanguage,
  useLocalizedPath
} from "../i18n";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

export function Layout() {
  const location = useLocation();
  const lang = useLanguage();
  const t = useI18n();
  const to = useLocalizedPath();
  const currentPath = stripLanguagePrefix(location.pathname);
  const navLinks = [
    { path: "/events", label: t.nav.latest },
    { path: "/raw", label: t.nav.raw },
    { path: "/events", search: "?severity=S", label: t.nav.highImpact },
    { path: "/tags/iran", label: t.nav.tags },
    { path: "/about", label: t.nav.about },
    { path: "/status", label: t.nav.status },
    { path: "/support", label: t.nav.support }
  ];

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <div className="min-h-screen bg-base-100 text-base-content">
      <header className="sticky top-0 z-50 border-b border-base-300/60 bg-base-100/80 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
          <NavLink to={to("/events")} className="shrink-0" aria-label={t.nav.tickbaseHome}>
            <Logo />
          </NavLink>
          <ul className="ml-6 hidden items-center gap-1 md:flex">
            {navLinks.map((link) => (
              <li key={`${link.path}${link.search ?? ""}`}>
                <Link
                  to={to(link.path, link.search)}
                  className={`rounded-field px-3 py-2 text-sm font-medium transition-colors hover:bg-base-200 hover:text-base-content ${
                    isNavActive(link.path, link.search, currentPath, location.search)
                      ? "text-primary"
                      : "text-base-content/70"
                  }`}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="ml-auto flex items-center gap-2">
            <LanguageSwitcher />
            <ThemeToggle />
            <a
              href={KOFI_URL}
              target="_blank"
              className="btn btn-primary btn-sm hidden sm:inline-flex"
              rel="noreferrer"
            >
              <Coffee className="h-4 w-4" />
              {t.nav.supportCta}
            </a>
            <a
              href="https://thetickbase.com"
              className="btn btn-ghost btn-sm hidden sm:inline-flex"
              rel="noreferrer"
            >
              TickBase
            </a>
            <div className="dropdown dropdown-end md:hidden">
              <button tabIndex={0} className="btn btn-ghost btn-circle btn-sm" aria-label="Open menu">
                <Menu className="h-5 w-5" />
              </button>
              <ul
                tabIndex={0}
                className="menu dropdown-content z-50 mt-3 w-56 rounded-box border border-base-300 bg-base-200 p-2 shadow-lg"
              >
                {navLinks.map((link) => (
                  <li key={`${link.path}${link.search ?? ""}`}>
                    <NavLink to={to(link.path, link.search)}>{link.label}</NavLink>
                  </li>
                ))}
                <li className="menu-title">
                  <span>{t.nav.language}</span>
                </li>
                {supportedLanguages.map((language) => (
                  <li key={language}>
                    <NavLink
                      to={localizedPath(language, currentPath, location.search)}
                      className={language === lang ? "active" : undefined}
                    >
                      {languageLabels[language]}
                    </NavLink>
                  </li>
                ))}
                <li>
                  <a href="https://thetickbase.com" rel="noreferrer">
                    TickBase
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      </header>

      <main>
        <Outlet />
      </main>

      <Footer />
    </div>
  );
}

function isNavActive(path: string, linkSearch: string | undefined, currentPath: string, search: string): boolean {
  if (path === "/events" && !linkSearch) {
    return currentPath === "/events" && !new URLSearchParams(search).get("severity");
  }
  if (path === "/events" && linkSearch === "?severity=S") {
    return currentPath === "/events" && new URLSearchParams(search).get("severity") === "S";
  }
  if (path === "/raw") {
    return currentPath.startsWith("/raw");
  }
  if (path.startsWith("/tags")) {
    return currentPath.startsWith("/tags");
  }
  return currentPath === path;
}

function LanguageSwitcher() {
  const location = useLocation();
  const lang = useLanguage();
  const currentPath = stripLanguagePrefix(location.pathname);

  return (
    <div className="join hidden sm:inline-flex" aria-label="Language switcher">
      {supportedLanguages.map((language) => (
        <Link
          key={language}
          to={localizedPath(language, currentPath, location.search)}
          className={`btn join-item btn-xs ${language === lang ? "btn-primary" : "btn-ghost"}`}
          aria-current={language === lang ? "page" : undefined}
          title={`${languageLabels[language]}`}
        >
          <Languages className="h-3.5 w-3.5" />
          {languageLabels[language]}
        </Link>
      ))}
    </div>
  );
}

function Footer() {
  const to = useLocalizedPath();
  const t = useI18n();

  return (
    <footer className="border-t border-base-300/60 bg-base-200/60">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr] lg:px-8">
        <div className="max-w-md">
          <Logo />
          <p className="mt-4 text-sm leading-6 text-base-content/60">
            {t.footer.summary}
          </p>
        </div>
        <div>
          <h3 className="text-sm font-semibold">{t.footer.explore}</h3>
          <div className="mt-3 grid gap-2 text-sm text-base-content/60">
            <NavLink to={to("/events")} className="hover:text-primary">
              {t.footer.latestEvents}
            </NavLink>
            <NavLink to={to("/raw")} className="hover:text-primary">
              {t.footer.rawFeed}
            </NavLink>
            <NavLink to={to("/about")} className="hover:text-primary">
              {t.footer.methodology}
            </NavLink>
            <NavLink to={to("/support")} className="hover:text-primary">
              {t.footer.support}
            </NavLink>
            <NavLink to={to("/status")} className="hover:text-primary">
              {t.footer.apiStatus}
            </NavLink>
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold">{t.footer.dataBoundary}</h3>
          <p className="mt-3 text-sm leading-6 text-base-content/60">
            {t.footer.dataBoundaryBody}
          </p>
        </div>
      </div>
    </footer>
  );
}
