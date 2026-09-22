import {
  Bell,
  BookOpen,
  ChevronDown,
  ExternalLink,
  Languages,
  LogOut,
  Menu,
  RotateCw,
  X
} from "lucide-react";
import { ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { accountDashboardUrl } from "../config/account";
import { AccountApiError } from "../features/account/domain/api";
import { useAccountSession, useLogout } from "../features/account/domain/queries";
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname, location.search]);

  return (
    <div className="min-h-screen bg-base-100 text-base-content">
      <header className="sticky top-0 z-50 border-b border-base-300/60 bg-base-100/90 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
          <NavLink to={to("/events")} className="shrink-0" aria-label={t.nav.tickbaseHome}>
            <Logo />
          </NavLink>

          <ul className="ml-7 hidden h-full items-center gap-1 lg:flex">
            <li className="h-full">
              <HeaderNavLink
                to={to("/events")}
                active={isNavActive("/events", undefined, currentPath, location.search)}
              >
                {t.nav.latest}
              </HeaderNavLink>
            </li>
            <li className="h-full">
              <HeaderNavLink
                to={to("/events", "?severity=S")}
                active={isNavActive("/events", "?severity=S", currentPath, location.search)}
              >
                {t.nav.highImpact}
              </HeaderNavLink>
            </li>
            <li className="flex h-full items-center">
              <ExploreMenu active={currentPath === "/topics" || currentPath.startsWith("/tags/") || currentPath.startsWith("/raw")} />
            </li>
          </ul>

          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            <LanguageSwitcher />
            <ThemeToggle />
            {!currentPath.startsWith("/sign-in") && !currentPath.startsWith("/register") && <AccountControl />}
            <button
              className="btn btn-ghost btn-circle btn-sm lg:hidden"
              type="button"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-navigation"
              aria-label={mobileMenuOpen ? t.nav.closeMenu : t.nav.openMenu}
              onClick={() => setMobileMenuOpen((open) => !open)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </nav>

        {mobileMenuOpen && (
          <div id="mobile-navigation" className="border-t border-base-300/60 bg-base-100 px-4 py-4 lg:hidden">
            <div className="mx-auto grid max-w-7xl gap-1">
              <MobileNavLink to={to("/events")} active={isNavActive("/events", undefined, currentPath, location.search)}>{t.nav.latest}</MobileNavLink>
              <MobileNavLink to={to("/events", "?severity=S")} active={isNavActive("/events", "?severity=S", currentPath, location.search)}>{t.nav.highImpact}</MobileNavLink>
              <MobileNavLink to={to("/raw")} active={currentPath.startsWith("/raw")}>{t.nav.raw}</MobileNavLink>
              <MobileNavLink to={to("/topics")} active={currentPath === "/topics" || currentPath.startsWith("/tags/")}>{t.nav.topics}</MobileNavLink>
              <div className="mt-3 border-t border-base-300/60 pt-3">
                <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.14em] text-base-content/45">
                  {t.nav.language}
                </p>
                <div className="grid grid-cols-2 gap-1">
                  {supportedLanguages.map((language) => (
                    <NavLink
                      key={language}
                      to={localizedPath(language, currentPath, location.search)}
                      className={({ isActive }) =>
                        `rounded-field px-3 py-2 text-sm ${isActive ? "bg-primary/10 font-medium text-primary" : "text-base-content/65 hover:bg-base-200"}`
                      }
                    >
                      {languageLabels[language]}
                    </NavLink>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </header>

      <main>
        <Outlet />
      </main>

      <Footer />
    </div>
  );
}

function HeaderNavLink({ to, active, children }: { to: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={`relative flex h-full items-center px-3 text-sm font-medium transition-colors after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-primary after:transition-opacity ${
        active
          ? "text-base-content after:opacity-100"
          : "text-base-content/65 after:opacity-0 hover:text-base-content"
      }`}
    >
      {children}
    </Link>
  );
}

function ExploreMenu({ active }: { active: boolean }) {
  const t = useI18n();
  const to = useLocalizedPath();

  return (
    <MenuPopover
      label={t.nav.explore}
      buttonClassName={`btn btn-ghost btn-sm gap-1 ${active ? "text-primary" : "text-base-content/65"}`}
      buttonContent={<><span>{t.nav.explore}</span><ChevronDown className="h-3.5 w-3.5" /></>}
    >
      {(close) => (
        <ul className="menu w-52 p-2">
          <li><Link to={to("/raw")} onClick={close}>{t.nav.raw}</Link></li>
          <li><Link to={to("/topics")} onClick={close}>{t.nav.topics}</Link></li>
        </ul>
      )}
    </MenuPopover>
  );
}

function AccountControl() {
  const t = useI18n();
  const to = useLocalizedPath();
  const location = useLocation();
  const navigate = useNavigate();
  const session = useAccountSession();
  const logout = useLogout();

  if (session.isPending) {
    return <div className="skeleton h-8 w-20 rounded-field" aria-label={t.account.loading} />;
  }

  if (session.error instanceof AccountApiError && session.error.status === 401) {
    const returnTo = `${location.pathname}${location.search}`;
    return (
      <Link
        className="btn btn-outline btn-sm whitespace-nowrap"
        to={to("/sign-in", `?returnTo=${encodeURIComponent(returnTo)}`)}
      >
        {t.nav.signIn}
      </Link>
    );
  }

  if (session.isError || !session.data) {
    return (
      <button
        className="btn btn-ghost btn-sm gap-2 text-base-content/60"
        type="button"
        title={t.account.unavailable}
        onClick={() => session.refetch()}
      >
        <RotateCw className="h-4 w-4" />
        <span className="hidden sm:inline">{t.account.retry}</span>
      </button>
    );
  }

  const { user, news } = session.data;
  const initials = getInitials(user.name, user.email);
  return (
    <MenuPopover
      align="end"
      label={t.nav.accountMenu}
      buttonClassName="btn btn-ghost btn-sm gap-2 px-1.5 sm:px-2"
      buttonContent={
        <>
          <span className="grid h-7 w-7 place-items-center rounded-full bg-primary text-xs font-bold text-primary-content">
            {initials}
          </span>
          <span className="hidden max-w-28 truncate sm:inline">{firstName(user.name)}</span>
          <ChevronDown className="hidden h-3.5 w-3.5 text-base-content/45 sm:block" />
        </>
      }
    >
      {(close) => (
        <div className="w-72 p-2">
          <div className="px-3 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-semibold">{user.name}</p>
                <p className="mt-0.5 truncate text-xs text-base-content/55">{user.email}</p>
              </div>
              <span className={`badge badge-sm ${news.accessAllowed ? "badge-primary" : "badge-ghost"}`}>
                {news.accessAllowed ? t.account.newsPro : t.account.free}
              </span>
            </div>
          </div>
          <ul className="menu border-t border-base-300/60 pt-2">
            <li>
              <Link to={to("/digests")} onClick={close}>
                <BookOpen className="h-4 w-4" />{t.nav.digests}
                {!news.accessAllowed && <span className="badge badge-ghost badge-xs ml-auto">PRO</span>}
              </Link>
            </li>
            <li>
              <Link to={to("/notifications")} onClick={close}>
                <Bell className="h-4 w-4" />{t.nav.notifications}
                {!news.accessAllowed && <span className="badge badge-ghost badge-xs ml-auto">PRO</span>}
              </Link>
            </li>
            {accountDashboardUrl && (
              <li>
                <a href={accountDashboardUrl} target="_blank" rel="noreferrer" onClick={close}>
                  {t.account.accountSubscription}<ExternalLink className="ml-auto h-4 w-4" />
                </a>
              </li>
            )}
          </ul>
          <div className="mt-2 border-t border-base-300/60 pt-2">
            <button
              className="btn btn-ghost btn-sm w-full justify-start font-normal"
              type="button"
              disabled={logout.isPending}
              onClick={async () => {
                try {
                  await logout.mutateAsync();
                  close();
                  // Leave authenticated screens immediately so their local
                  // form state cannot remain visible after the session ends.
                  navigate(to("/events"), { replace: true });
                } catch {
                  // The inline error keeps the menu open so the reader can retry.
                }
              }}
            >
              <LogOut className="h-4 w-4" />
              {logout.isPending ? t.account.signingOut : t.account.signOut}
            </button>
            {logout.isError && <p className="px-3 pt-2 text-xs text-error">{t.account.signOutError}</p>}
          </div>
        </div>
      )}
    </MenuPopover>
  );
}

function LanguageSwitcher() {
  const location = useLocation();
  const lang = useLanguage();
  const t = useI18n();
  const currentPath = stripLanguagePrefix(location.pathname);

  return (
    <div className="hidden lg:block">
      <MenuPopover
        align="end"
        label={t.nav.language}
        buttonClassName="btn btn-ghost btn-sm min-w-28 justify-between gap-2"
        buttonContent={
          <><Languages className="h-4 w-4" /><span className="truncate">{languageLabels[lang]}</span><ChevronDown className="h-3.5 w-3.5" /></>
        }
      >
        {(close) => (
          <ul className="menu w-44 p-2">
            {supportedLanguages.map((language) => (
              <li key={language}>
                <Link
                  to={localizedPath(language, currentPath, location.search)}
                  className={language === lang ? "active" : undefined}
                  aria-current={language === lang ? "page" : undefined}
                  onClick={close}
                >
                  {languageLabels[language]}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </MenuPopover>
    </div>
  );
}

function MenuPopover({
  label,
  buttonClassName,
  buttonContent,
  align = "start",
  children
}: {
  label: string;
  buttonClassName: string;
  buttonContent: ReactNode;
  align?: "start" | "end";
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function dismiss(event: PointerEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        className={buttonClassName}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {buttonContent}
      </button>
      {open && (
        <div
          className={`absolute top-full z-50 mt-2 rounded-box border border-base-300 bg-base-200 shadow-lg ${align === "end" ? "right-0" : "left-0"}`}
          role="menu"
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

function MobileNavLink({ to, active, children }: { to: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={`rounded-field px-3 py-2.5 text-sm font-medium ${active ? "bg-primary/10 text-primary" : "text-base-content/70 hover:bg-base-200"}`}
    >
      {children}
    </Link>
  );
}

function Footer() {
  const to = useLocalizedPath();
  const t = useI18n();

  return (
    <footer className="border-t border-base-300/60 bg-base-200/60">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-2 sm:px-6 lg:grid-cols-[1.3fr_0.8fr_0.9fr_1.2fr] lg:px-8">
        <div className="max-w-sm sm:col-span-2 lg:col-span-1">
          <Logo />
          <p className="mt-4 text-sm leading-6 text-base-content/60">{t.footer.summary}</p>
        </div>
        <FooterGroup title={t.footer.explore}>
          <NavLink to={to("/events")}>{t.footer.latestEvents}</NavLink>
          <NavLink to={to("/events", "?severity=S")}>{t.footer.highImpact}</NavLink>
          <NavLink to={to("/raw")}>{t.footer.rawFeed}</NavLink>
          <NavLink to={to("/topics")}>{t.footer.topics}</NavLink>
        </FooterGroup>
        <FooterGroup title={t.footer.product}>
          <NavLink to={to("/about")}>{t.footer.methodology}</NavLink>
          <NavLink to={to("/status")}>{t.footer.apiStatus}</NavLink>
          <NavLink to={to("/support")}>{t.footer.support}</NavLink>
          <a href="https://thetickbase.com" rel="noreferrer">{t.footer.mainTickBase}</a>
        </FooterGroup>
        <div>
          <h3 className="text-sm font-semibold">{t.footer.dataBoundary}</h3>
          <p className="mt-3 text-sm leading-6 text-base-content/60">{t.footer.dataBoundaryBody}</p>
        </div>
      </div>
    </footer>
  );
}

function FooterGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-3 grid gap-2 text-sm text-base-content/60 [&_a:hover]:text-primary">{children}</div>
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
  return currentPath === path;
}

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

function getInitials(name: string, email: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length > 1) return `${parts[0][0]}${parts.at(-1)?.[0] ?? ""}`.toUpperCase();
  return (parts[0]?.slice(0, 2) || email.slice(0, 2)).toUpperCase();
}
