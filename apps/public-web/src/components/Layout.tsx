import { Menu } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

const navLinks = [
  { to: "/events", label: "Latest" },
  { to: "/events?severity=S", label: "High Impact" },
  { to: "/tags/iran", label: "Tags" },
  { to: "/about", label: "About" },
  { to: "/status", label: "Status" }
];

export function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-base-100 text-base-content">
      <header className="sticky top-0 z-50 border-b border-base-300/60 bg-base-100/80 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
          <NavLink to="/events" className="shrink-0" aria-label="TickBase News home">
            <Logo />
          </NavLink>
          <ul className="ml-6 hidden items-center gap-1 md:flex">
            {navLinks.map((link) => (
              <li key={link.to}>
                <Link
                  to={link.to}
                  className={`rounded-field px-3 py-2 text-sm font-medium transition-colors hover:bg-base-200 hover:text-base-content ${
                    isNavActive(link.to, location.pathname, location.search)
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
                  <li key={link.to}>
                    <NavLink to={link.to}>{link.label}</NavLink>
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

function isNavActive(to: string, pathname: string, search: string): boolean {
  if (to === "/events") {
    return pathname === "/events" && !new URLSearchParams(search).get("severity");
  }
  if (to === "/events?severity=S") {
    return pathname === "/events" && new URLSearchParams(search).get("severity") === "S";
  }
  if (to.startsWith("/tags")) {
    return pathname.startsWith("/tags");
  }
  return pathname === to;
}

function Footer() {
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
            <NavLink to="/events" className="hover:text-primary">
              Latest events
            </NavLink>
            <NavLink to="/about" className="hover:text-primary">
              Methodology
            </NavLink>
            <NavLink to="/status" className="hover:text-primary">
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
