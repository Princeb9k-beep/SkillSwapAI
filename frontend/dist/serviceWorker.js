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
