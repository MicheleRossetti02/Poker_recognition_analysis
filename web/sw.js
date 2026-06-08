// Service worker: cache the app shell + python engine for offline play (W4).
const CACHE = "vpoker-v1";
const ASSETS = [
  "./", "./index.html", "./style.css", "./app.js",
  "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
  "./py/web_api.py",
  "./py/poker/__init__.py", "./py/poker/cards.py", "./py/poker/evaluator.py",
  "./py/poker/equity.py", "./py/poker/ranges.py", "./py/poker/range_model.py",
  "./py/poker/profiling.py", "./py/poker/engine.py", "./py/poker/table.py",
  "./py/poker/simulator.py", "./py/poker/tournament.py", "./py/poker/history.py",
  "./py/poker/render.py", "./py/poker/bots.py", "./py/poker/arena.py",
  "./py/poker/fast_equity.py",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Never cache the Pyodide CDN; let it use the browser cache.
  if (url.origin !== location.origin) return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match("./index.html")))
  );
});
