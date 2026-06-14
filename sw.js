// Service worker: caches the site so 504s and dead cellular don't break it.
//
// Strategy:
//   - index.html (navigation): network-first, fall back to cache.
//     Ensures she sees updates when online, still works offline / on 504.
//   - WASM + JS glue (?v=N): cache-first. The query string is the version,
//     so a deploy that bumps ?v=N naturally fetches fresh.
//   - Cross-origin (Google Fonts, Google Maps redirects): we don't touch.
//
// Bump VERSION on every site deploy; old caches get evicted on activate.

const VERSION = "8";
const CACHE_NAME = `tacobell-v${VERSION}`;
const PRECACHE = [
  "./",
  "./index.html",
  `./pkg/tacobell_finder.js?v=${VERSION}`,
  `./pkg/tacobell_finder_bg.wasm?v=${VERSION}`,
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // individual adds, since one missing asset shouldn't tank the whole install
      Promise.all(
        PRECACHE.map((url) =>
          cache.add(url).catch((err) => console.warn("[sw] precache miss", url, err))
        )
      )
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // let browser handle fonts / maps

  // Navigation requests: network-first with cache fallback.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          return resp;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match("./")))
    );
    return;
  }

  // Static assets (WASM, JS glue, anything else same-origin): cache-first.
  event.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((resp) => {
        if (resp && resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        }
        return resp;
      });
    })
  );
});
