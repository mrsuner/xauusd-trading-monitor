/* Firebase public web config is supplied in the service-worker script URL. */
const params = new URL(self.location.href).searchParams;
const config = JSON.parse(params.get("config") || "null");

if (config && config.apiKey && config.appId && config.messagingSenderId) {
  self.addEventListener("notificationclick", (event) => {
    const url = event.notification.data?.url;
    if (!url) return;
    try {
      if (new URL(url).origin !== self.location.origin) return;
    } catch {
      return;
    }
    event.stopImmediatePropagation();
    event.notification.close();
    event.waitUntil(self.clients.openWindow(url));
  });

  importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js");
  importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js");
  firebase.initializeApp(config);
  firebase.messaging();
}
