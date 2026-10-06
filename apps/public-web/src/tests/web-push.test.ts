import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  accountRequest: vi.fn(),
  getToken: vi.fn(),
  deleteToken: vi.fn(),
  isSupported: vi.fn(),
  registerWorker: vi.fn(),
  requestPermission: vi.fn()
}));

vi.mock("firebase/app", () => ({ getApps: () => [], initializeApp: () => ({}) }));
vi.mock("firebase/messaging", () => ({
  getMessaging: () => ({}),
  getToken: mocks.getToken,
  deleteToken: mocks.deleteToken,
  isSupported: mocks.isSupported,
  onMessage: vi.fn()
}));
vi.mock("../features/account/domain/api", () => ({ accountRequest: mocks.accountRequest }));

import { disableCurrentBrowser, enableCurrentBrowser, getWebPushStatus, refreshCurrentBrowser } from "../features/notifications/domain/webPush";

let permission: NotificationPermission;

beforeEach(() => {
  vi.clearAllMocks();
  const stored = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => { stored.set(key, value); },
    removeItem: (key: string) => { stored.delete(key); }
  });
  permission = "default";
  Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { register: mocks.registerWorker } });
  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: { get permission() { return permission; }, requestPermission: mocks.requestPermission }
  });
  mocks.isSupported.mockResolvedValue(true);
  mocks.getToken.mockResolvedValue("web-token");
  mocks.deleteToken.mockResolvedValue(true);
  mocks.registerWorker.mockResolvedValue({});
  mocks.requestPermission.mockImplementation(async () => { permission = "granted"; return "granted"; });
  mocks.accountRequest.mockImplementation(async (path: string) => path === "/devices" ? { data: { id: "device-1" } } : null);
});

describe("News browser push", () => {
  it("asks permission on enable, registers only a News web device, then removes it", async () => {
    expect(await getWebPushStatus("reader-1")).toBe("available");
    await enableCurrentBrowser("reader-1");

    expect(mocks.requestPermission).toHaveBeenCalledOnce();
    expect(mocks.registerWorker).toHaveBeenCalledWith(expect.stringContaining("firebase-messaging-sw.js?config="), { scope: "/" });
    expect(mocks.accountRequest).toHaveBeenCalledWith("/devices", {
      method: "POST",
      body: expect.objectContaining({ platform: "web", provider: "fcm", product: "news", push_token: "web-token" })
    });
    expect(await getWebPushStatus("reader-1")).toBe("enabled");

    await disableCurrentBrowser();
    expect(mocks.accountRequest).toHaveBeenCalledWith("/devices/device-1", { method: "DELETE" });
    expect(mocks.deleteToken).toHaveBeenCalledOnce();
    expect(await getWebPushStatus("reader-1")).toBe("available");
  });

  it("does not create a token when permission is denied", async () => {
    mocks.requestPermission.mockResolvedValue("denied");
    await expect(enableCurrentBrowser("reader-1")).rejects.toThrow("blocked");
    expect(mocks.getToken).not.toHaveBeenCalled();
    expect(mocks.accountRequest).not.toHaveBeenCalled();
  });

  it("revokes the previous token before registering for another signed-in account", async () => {
    await enableCurrentBrowser("reader-1");
    mocks.accountRequest.mockRejectedValueOnce(new Error("device belongs to another account"));
    mocks.getToken.mockResolvedValueOnce("new-account-token");

    await refreshCurrentBrowser("reader-2");

    expect(mocks.deleteToken).toHaveBeenCalledOnce();
    expect(mocks.accountRequest).toHaveBeenLastCalledWith("/devices", {
      method: "POST",
      body: expect.objectContaining({ push_token: "new-account-token", product: "news" })
    });
    expect(await getWebPushStatus("reader-1")).toBe("available");
    expect(await getWebPushStatus("reader-2")).toBe("enabled");
  });
});
