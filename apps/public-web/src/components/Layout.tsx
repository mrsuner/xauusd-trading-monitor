import { Languages, Menu } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  languageLabels,
  localizedPath,
  stripLanguagePrefix,
  supportedLanguages,
  useLanguage,
  useLocalizedPath
} from "../i18n";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

const navLinks = [
  { path: "/events", label: "Latest" },
  { path: "/events", search: "?severity=S", label: "High Impact" },
  { path: "/tags/iran", label: "Tags" },
  { path: "/about", label: "About" },
  { path: "/status", label: "Status" }
];

export function Layout() {
  const location = useLocation();
  const lang = useLanguage();
  const to = useLocalizedPath();
  const currentPath = stripLanguagePrefix(location.pathname);

  return (
    <div className="min-h-screen bg-base-100 text-base-content">
      <header className="sticky top-0 z-50 border-b border-base-300/60 bg-base-100/80 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
          <NavLink to={to("/events")} className="shrink-0" aria-label="TickBase News home">
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
                  <span>Language</span>
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
          title={`Language: ${languageLabels[language]}`}
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

  return (
    <footer className="border-t border-base-300/60 bg-base-200/60">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr] lg:px-8">
        <div className="max-w-md">
          <Logo />
          <p className="mt-4 text-sm leading-6 text-base-content/60">
            Public event radar for market-moving macro, gold, geopolitics, energy, and policy news.
            Not investment advice.
          </p>
        </div>
        <div>
          <h3 className="text-sm font-semibold">Explore</h3>
          <div className="mt-3 grid gap-2 text-sm text-base-content/60">
            <NavLink to={to("/events")} className="hover:text-primary">
              Latest events
            </NavLink>
            <NavLink to={to("/about")} className="hover:text-primary">
              Methodology
            </NavLink>
            <NavLink to={to("/status")} className="hover:text-primary">
              API status
            </NavLink>
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold">Data Boundary</h3>
          <p className="mt-3 text-sm leading-6 text-base-content/60">
            This site only displays public-safe summaries and source attribution. Internal raw items,
            prompts, usage cost, sessions, and private delivery states are not published.
          </p>
        </div>
      </div>
    </footer>
  );
}
