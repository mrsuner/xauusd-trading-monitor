import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EventDetailPage } from "../pages/EventDetailPage";
import { RawItemDetailPage } from "../pages/RawItemDetailPage";
import { PublicApiError } from "../api/client";

const api = vi.hoisted(() => ({ getEvent: vi.fn(), getRawItem: vi.fn() }));
vi.mock("../api/client", async (original) => ({
  ...(await original<typeof import("../api/client")>()),
  getEvent: api.getEvent,
  getRawItem: api.getRawItem,
  listRawItems: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));
vi.mock(
  "../features/reader-preferences/domain/useAppliedReaderPreferences",
  () => ({
    useAppliedReaderPreferences: () => ({ ready: true, contentLanguage: "en" }),
  }),
);
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("withdrawn content details", () => {
  for (const [path, Component, request] of [
    ["events/:eventId", EventDetailPage, api.getEvent],
    ["raw/:rawItemId", RawItemDetailPage, api.getRawItem],
  ] as const) {
    it.each([404, 410])(
      `${path} shows an unavailable state without retries for HTTP %s`,
      async (status) => {
        request.mockRejectedValue(new PublicApiError(status));
        const client = new QueryClient();
        render(
          <QueryClientProvider client={client}>
            <MemoryRouter
              initialEntries={[`/en/${path.split("/")[0]}/withdrawn`]}
            >
              <Routes>
                <Route path={`/:lang/${path}`} element={<Component />} />
              </Routes>
            </MemoryRouter>
          </QueryClientProvider>,
        );
        expect(
          await screen.findByText(
            "This public event does not exist or has been hidden.",
          ),
        ).toBeTruthy();
        expect(request).toHaveBeenCalledTimes(1);
        expect(
          screen.queryByText(`Public API request failed: ${status}`),
        ).toBeNull();
        client.clear();
      },
    );
  }
});
