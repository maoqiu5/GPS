const STATIC_CACHE = "gps-static-v9";
const TILE_CACHE = "gps-tiles-v1";
const STATIC_ASSETS = [
  "./",
  "./index.html",
];
const TILE_HOSTS = new Set([
  "server.arcgisonline.com",
  "tile.openstreetmap.org",
]);

self.addEventListener("install", event => {
  event.waitUntil(caches.open(STATIC_CACHE).then(cache => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches
      .keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith("gps-static-") && key !== STATIC_CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (TILE_HOSTS.has(url.hostname)) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async cache => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const response = await fetch(event.request);
        cache.put(event.request, response.clone());
        return response;
      })
    );
    return;
  }

  if (url.origin === self.location.origin && event.request.method === "GET") {
    if (event.request.mode === "navigate" || event.request.destination === "document") {
      event.respondWith(fetch(event.request).catch(() => caches.match("./index.html")));
      return;
    }

    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
  }
});
