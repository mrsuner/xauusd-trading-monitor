import { initializeApp, getApps } from "firebase/app";
import { deleteToken, getMessaging, getToken, isSupported, onMessage } from "firebase/messaging";
import { accountRequest } from "../../account/domain/api";

const storageKey = "tickbase-news-web-push";
const runtime = window.__TICKBASE_NEWS_CONFIG__ ?? {};
const config = {
  apiKey: runtime.FIREBASE_API_KEY || import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: runtime.FIREBASE_AUTH_DOMAIN || import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: runtime.FIREBASE_PROJECT_ID || import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
  messagingSenderId: runtime.FIREBASE_MESSAGING_SENDER_ID || import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: runtime.FIREBASE_APP_ID || import.meta.env.VITE_FIREBASE_APP_ID || ""
};
const vapidKey = runtime.FIREBASE_VAPID_KEY || import.meta.env.VITE_FIREBASE_VAPID_KEY || "";
let foregroundListenerReady = false;

interface BrowserRegistration {
  userId: string;
  deviceId: string;
  token: string;
}

export type WebPushStatus = "unsupported" | "unconfigured" | "blocked" | "available" | "enabled";

export function isCurrentBrowserRegistered(userId: string): boolean {
  return readRegistration()?.userId === userId;
}

export async function getWebPushStatus(userId: string): Promise<WebPushStatus> {
  if (!window.isSecureContext || !("serviceWorker" in navigator) || !("Notification" in window)) {
    return "unsupported";
  }
  if (Object.values(config).some((value) => !value) || !vapidKey) return "unconfigured";
  if (!(await isSupported().catch(() => false))) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  return isCurrentBrowserRegistered(userId) && Notification.permission === "granted" ? "enabled" : "available";
}

export async function enableCurrentBrowser(userId: string): Promise<void> {
  if (!window.isSecureContext || !("Notification" in window) || !("serviceWorker" in navigator)) {
    throw new Error("unsupported");
  }
  if (Object.values(config).some((value) => !value) || !vapidKey) throw new Error("unconfigured");
  if (Notification.permission === "denied") throw new Error("blocked");
  // Request permission before any asynchronous support check, preserving the click gesture.
  if (Notification.permission !== "granted" && await Notification.requestPermission() !== "granted") {
    throw new Error("blocked");
  }
  const status = await getWebPushStatus(userId);
  if (status === "unsupported" || status === "unconfigured") throw new Error(status);
  await registerCurrentBrowser(userId);
}

export async function refreshCurrentBrowser(userId: string): Promise<void> {
  const saved = readRegistration();
  if (!saved || !("Notification" in window) || Notification.permission !== "granted") return;
  const status = await getWebPushStatus(userId);
  if (status === "unsupported" || status === "unconfigured" || status === "blocked") return;
  if (saved.userId !== userId) await disableCurrentBrowser();
  await registerCurrentBrowser(userId);
}

async function registerCurrentBrowser(userId: string): Promise<void> {
  const messaging = getMessaging(getApps()[0] ?? initializeApp(config));
  if (!foregroundListenerReady) {
    onMessage(messaging, () => {
      // Foreground pages already display the event feed; do not show another system alert.
    });
    foregroundListenerReady = true;
  }
  const script = `/firebase-messaging-sw.js?config=${encodeURIComponent(JSON.stringify(config))}`;
  const worker = await navigator.serviceWorker.register(script, { scope: "/" });
  const token = await getToken(messaging, { vapidKey, serviceWorkerRegistration: worker });
  if (!token) throw new Error("token_unavailable");

  const previous = readRegistration();
  if (previous && previous.token !== token && previous.userId === userId) {
    await accountRequest(`/devices/${encodeURIComponent(previous.deviceId)}`, { method: "DELETE" });
  }
  const body = await accountRequest<{ data: { id: string } }>("/devices", {
    method: "POST",
    body: { platform: "web", provider: "fcm", product: "news", push_token: token, device_name: "TickBase News browser" }
  });
  localStorage.setItem(storageKey, JSON.stringify({ userId, deviceId: body.data.id, token } satisfies BrowserRegistration));
}

export async function disableCurrentBrowser(): Promise<void> {
  const saved = readRegistration();
  if (!saved) return;
  let removedFromAccount = false;
  let revokedAtFirebase = false;
  try {
    await accountRequest(`/devices/${encodeURIComponent(saved.deviceId)}`, { method: "DELETE" });
    removedFromAccount = true;
  } catch {
    // Firebase revocation below is an independent way to stop this browser receiving messages.
  }
  try {
    if (Object.values(config).every(Boolean) && await isSupported()) {
      revokedAtFirebase = await deleteToken(getMessaging(getApps()[0] ?? initializeApp(config)));
    }
  } catch {
    // Preserve the local record so the user can retry unless the server has removed it.
  }
  if (!removedFromAccount && !revokedAtFirebase) throw new Error("unregister_failed");
  localStorage.removeItem(storageKey);
}

function readRegistration(): BrowserRegistration | null {
  try {
    const value = localStorage.getItem(storageKey);
    if (!value) return null;
    const record = JSON.parse(value) as BrowserRegistration;
    return record.userId && record.deviceId && record.token ? record : null;
  } catch {
    return null;
  }
}
