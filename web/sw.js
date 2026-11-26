/* MAS AI Agents â€” service worker (app shell only; never caches API or user data). */
const VERSION = "mas-v15";
const SHELL = [
  "/",
  "/static/style.css?v=25",
  "/static/i18n.js?v=25",
  "/static/app.js?v=25",
  "/static/manifest.json",
  "/static/assets/fav/icon-192.png",
  "/static/assets/fav/icon-512.png",
  "/static/assets/fav/icon-maskable-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(SHELL).catch(() => undefined)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // API, shares, uploads and library files must always hit the live server.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/share/")) return;

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put("/", copy)).catch(() => undefined);
          return res;
        })
        .catch(() => caches.match("/").then((r) => r || new Response("Offline", { status: 503 })))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    // Network-first: local updates (new JS/CSS) apply immediately on reload;
    // the cache is only a fallback when the server is unreachable.
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) caches.open(VERSION).then((c) => c.put(req, res.clone())).catch(() => undefined);
          return res;
        })
        .catch(() => caches.match(req))
    );
  }
});





