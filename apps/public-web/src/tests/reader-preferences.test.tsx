import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import type { PublicEvent } from "../api/types";
import { ThemeToggle } from "../components/ThemeToggle";
import { EventsPage } from "../pages/EventsPage";
import { ReaderPreferencesPage } from "../features/reader-preferences/ui/ReaderPreferencesPage";

const api = vi.hoisted(() => ({
  getAccountSession: vi.fn(),
  getReaderPreferences: vi.fn(),
  saveReaderPreferences: vi.fn(),
  listEvents: vi.fn(),
  listTags: vi.fn(),
  listCategories: vi.fn(),
  getOverviewStats: vi.fn(),
}));

vi.mock("../features/account/domain/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../features/account/domain/api")>(),
  getAccountSession: api.getAccountSession,
}));
vi.mock("../features/reader-preferences/domain/api", () => ({
  getReaderPreferences: api.getReaderPreferences,
  saveReaderPreferences: api.saveReaderPreferences,
}));
vi.mock("../api/client", () => ({
  listEvents: api.listEvents,
  listTags: api.listTags,
  listCategories: api.listCategories,
  getOverviewStats: api.getOverviewStats,
}));

const event: PublicEvent = {
  id: "event-1",
  upstream_event_id: "upstream-1",
  idempotency_key: "event-1",
  schema_version: "public_event.v1",
  event_time: "2026-09-23T00:00:00Z",
  generated_at: null,
  received_at: "2026-09-23T00:00:00Z",
  severity: "A",
  relevance_score: 90,
  confirmation_state: "confirmed",
  event_type: "macro_policy",
  title: "English headline",
  summary: "English summary",
  language: "en",
  available_languages: ["en", "zh-Hant"],
  translations: [
    { language: "en", title: "English headline", summary: "English summary" },
    { language: "zh-Hant", title: "中文標題", summary: "中文摘要" },
  ],
  public_source_links: [],
  topic_tags: [],
  content_category: null,
  mentioned_actors: [],
  route_metadata: {},
};

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

function renderRoute(path: string, element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/:lang/events" element={<>{element}<LocationProbe /></>} />
          <Route path="/:lang/reading-preferences" element={<>{element}<LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { client };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getAccountSession.mockResolvedValue({ id: "reader-1" });
  api.getReaderPreferences.mockResolvedValue({ contentLanguage: "en", minSeverity: "A", colorScheme: "light" });
  api.saveReaderPreferences.mockImplementation(async (value) => value);
  api.listEvents.mockResolvedValue({ items: [event], page: 1, page_size: 20, total: 1 });
  api.listTags.mockResolvedValue([]);
  api.listCategories.mockResolvedValue([]);
  api.getOverviewStats.mockResolvedValue({ total_events: 1, s_events: 0, a_events: 1, latest_event_time: null });
  document.documentElement.setAttribute("data-theme", "tickbase-light");
  vi.stubGlobal("localStorage", { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() });
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("account-applied Web reading", () => {
  it("uses account content language and inclusive minimum on the default feed", async () => {
    renderRoute("/zh-Hant/events", <EventsPage />);

    await waitFor(() => expect(api.listEvents).toHaveBeenCalledWith(expect.objectContaining({
      lang: "en", min_severity: "A", severity: undefined,
    })));
    expect(await screen.findByText("English headline")).toBeTruthy();
    expect((screen.getByRole("combobox", { name: "分級" }) as HTMLSelectElement).value).toBe("");
    expect(screen.getByText(/帳戶預設/)).toBeTruthy();
  });

  it("keeps an exact URL filter and allows an explicit all-events override", async () => {
    const user = userEvent.setup();
    renderRoute("/en/events?severity=B", <EventsPage />);

    await waitFor(() => expect(api.listEvents).toHaveBeenCalledWith(expect.objectContaining({
      severity: "B", min_severity: undefined, lang: "en",
    })));
    await user.selectOptions(screen.getByRole("combobox", { name: "Severity" }), "all");
    await waitFor(() => expect(api.listEvents).toHaveBeenCalledWith(expect.objectContaining({
      severity: undefined, min_severity: "C",
    })));
    expect(screen.getByTestId("location").textContent).toBe("?min_severity=C");
  });

  it("falls back to public locale and unfiltered events for guests", async () => {
    api.getAccountSession.mockRejectedValue(new Error("401"));
    renderRoute("/zh-Hant/events", <EventsPage />);

    await waitFor(() => expect(api.listEvents).toHaveBeenCalledWith(expect.objectContaining({
      lang: "zh-Hant", min_severity: undefined,
    })));
    expect(await screen.findByText("中文標題")).toBeTruthy();
    expect(api.getReaderPreferences).not.toHaveBeenCalled();
  });

  it("keeps the public feed usable when account preferences cannot load", async () => {
    api.getReaderPreferences.mockRejectedValue(new Error("account unavailable"));
    renderRoute("/zh-Hant/events", <EventsPage />);

    await waitFor(() => expect(api.listEvents).toHaveBeenCalledWith(expect.objectContaining({
      lang: "zh-Hant", min_severity: undefined,
    })));
    expect(await screen.findByText("中文標題")).toBeTruthy();
  });

  it("saves changed choices and keeps them visible after an account refresh", async () => {
    const user = userEvent.setup();
    renderRoute("/en/reading-preferences", <ReaderPreferencesPage />);

    await user.click(await screen.findByRole("radio", { name: "Traditional Chinese" }));
    await user.click(screen.getByRole("radio", { name: "Major only (S)" }));
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    await waitFor(() => expect(api.saveReaderPreferences.mock.calls.at(-1)?.[0]).toEqual({
      contentLanguage: "zh-Hant", minSeverity: "S", colorScheme: "dark",
    }));
    expect(await screen.findByText("Reading preferences saved to your account.")).toBeTruthy();
  });

  it("retains the draft and shows an error when saving fails", async () => {
    api.saveReaderPreferences.mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    renderRoute("/en/reading-preferences", <ReaderPreferencesPage />);

    await user.click(await screen.findByRole("radio", { name: "Dark" }));
    await user.click(screen.getByRole("button", { name: "Save preferences" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect((screen.getByRole("radio", { name: "Dark" }) as HTMLInputElement).checked).toBe(true);
    await user.click(screen.getByRole("radio", { name: "Follow system" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("preserves unsaved page choices when the header syncs a theme change", async () => {
    const user = userEvent.setup();
    renderRoute("/en/reading-preferences", <><ThemeToggle /><ReaderPreferencesPage /></>);

    await user.click(await screen.findByRole("radio", { name: "Traditional Chinese" }));
    fireEvent.click(screen.getByRole("button", { name: "Toggle theme" }));
    await waitFor(() => expect(api.saveReaderPreferences.mock.calls.at(-1)?.[0]).toEqual(expect.objectContaining({ colorScheme: "dark" })));
    expect((screen.getByRole("radio", { name: "Traditional Chinese" }) as HTMLInputElement).checked).toBe(true);
    await waitFor(() => expect((screen.getByRole("radio", { name: "Dark" }) as HTMLInputElement).checked).toBe(true));
    expect(document.documentElement.getAttribute("data-theme")).toBe("tickbase-dark");
  });
});
