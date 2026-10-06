// @vitest-environment node
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const source = readFileSync(new URL("../../public/firebase-messaging-sw.js", import.meta.url), "utf8");
const origin = "http://localhost:18103";
const url = `${origin}/en/events/local-qa`;

function setup(windows: unknown[] = []) {
  let handler!: (event: unknown) => void;
  const openWindow = vi.fn().mockResolvedValue(null);
  const matchAll = vi.fn().mockResolvedValue(windows);
  runInNewContext(source, {
    URL,
    self: {
      location: { origin, href: `${origin}/firebase-messaging-sw.js?config=${encodeURIComponent(JSON.stringify({ apiKey: "test", appId: "test", messagingSenderId: "test" }))}` },
      addEventListener: (_: string, callback: typeof handler) => { handler = callback; },
      clients: { openWindow, matchAll }
    },
    importScripts: vi.fn(),
    firebase: { initializeApp: vi.fn(), messaging: vi.fn() }
  });
  async function click(data: unknown) {
    const pending: Promise<unknown>[] = [];
    const event = {
      notification: { data, close: vi.fn() },
      stopImmediatePropagation: vi.fn(),
      waitUntil: (promise: Promise<unknown>) => { pending.push(promise); }
    };
    handler(event);
    await Promise.all(pending);
    return event;
  }
  return { click, openWindow, matchAll };
}

describe("News notification click", () => {
  it("opens the event from Firebase's wrapped notification data", async () => {
    const worker = setup();
    const event = await worker.click({ FCM_MSG: { data: { url } } });
    expect(worker.openWindow).toHaveBeenCalledWith(url);
    expect(event.stopImmediatePropagation).toHaveBeenCalledOnce();
    expect(event.notification.close).toHaveBeenCalledOnce();
  });

  it("navigates and focuses an existing same-origin tab instead of opening a duplicate", async () => {
    const focus = vi.fn().mockResolvedValue(null);
    const navigate = vi.fn().mockResolvedValue({ focus });
    const worker = setup([{ url: "https://example.com/", navigate: vi.fn() }, { url: `${origin}/en/notifications`, navigate }]);
    await worker.click({ FCM_MSG: { data: { url } } });
    expect(navigate).toHaveBeenCalledWith(url);
    expect(focus).toHaveBeenCalledOnce();
    expect(worker.openWindow).not.toHaveBeenCalled();
  });

  it("supports directly supplied notification data and opens a new tab if navigation returns no client", async () => {
    const navigate = vi.fn().mockResolvedValue(null);
    const worker = setup([{ url: origin, navigate }]);
    await worker.click({ url });
    expect(worker.openWindow).toHaveBeenCalledWith(url);
  });

  it.each([undefined, { url: "invalid" }, { FCM_MSG: { data: { url: "https://example.com/event" } } }])("ignores missing, invalid, or cross-origin URLs: %j", async (data) => {
    const worker = setup();
    await worker.click(data);
    expect(worker.matchAll).not.toHaveBeenCalled();
    expect(worker.openWindow).not.toHaveBeenCalled();
  });
});
