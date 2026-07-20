// Minimal offline cache for the app shell. Network-first for navigation so users
// always get fresh content when online, falling back to cache when offline.
const CACHE = "skillswap-v1";
const SHELL = ["/", "/index.html"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Paths owned by the API — never cached, since the frontend and backend now
// share an origin (single-app deploy). Everything else same-origin is shell/assets.
const API_PREFIXES = [
  "/health", "/users", "/roadmap", "/projects",
  "/resume", "/interview", "/lessons", "/docs", "/openapi.json",
];

// --- Web Push -------------------------------------------------------------
// Show a notification when a push arrives (even if the app/tab is closed).
self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "SkillSwap AI", body: event.data ? event.data.text() : "" };
  }
  const title = payload.title || "SkillSwap AI";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: payload.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { link: payload.link || "/" },
    })
  );
});

// Focus an existing tab (or open one) at the notification's link when clicked.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.focus();
          if ("navigate" in client) client.navigate(link).catch(() => {});
          return;
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(link);
    })
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  // Only handle same-origin GETs, and only for the shell/assets — never the API.
  if (request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }
  if (API_PREFIXES.some((p) => url.pathname === p || url.pathname.startsWith(p + "/"))) {
    return;
  }
  event.respondWith(
    fetch(request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(request, copy));
        return res;
      })
      .catch(() => caches.match(request).then((r) => r || caches.match("/")))
  );
});
