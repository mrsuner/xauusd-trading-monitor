/* Firebase public web config is supplied in the service-worker script URL. */
const params = new URL(self.location.href).searchParams;
const config = JSON.parse(params.get("config") || "null");

if (config && config.apiKey && config.appId && config.messagingSenderId) {
  self.addEventListener("notificationclick", (event) => {
    const data = event.notification.data;
    const url = data?.FCM_MSG?.data?.url ?? data?.url;
    if (!url) return;
    try {
      if (new URL(url).origin !== self.location.origin) return;
    } catch {
      return;
    }
    event.stopImmediatePropagation();
    event.notification.close();
    event.waitUntil((async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
      if (existing) {
        const navigated = await existing.navigate(url);
        if (navigated) return navigated.focus();
      }
      return self.clients.openWindow(url);
    })());
  });

  importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js");
  importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js");
  firebase.initializeApp(config);
  firebase.messaging();
}
