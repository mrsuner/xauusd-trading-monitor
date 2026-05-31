import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/timeline", label: "Timeline" },
  { to: "/events", label: "Events" },
  { to: "/sources", label: "Sources" },
  { to: "/processing", label: "Processing" },
  { to: "/alerts", label: "Alerts" }
];

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-base-300 bg-base-100">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div>
            <div className="text-lg font-semibold">XAUUSD Event Radar</div>
            <div className="text-xs text-base-content/55">News operations dashboard</div>
          </div>
          <nav className="flex flex-wrap gap-1">
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
