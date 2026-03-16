// BITOS Companion — Service Worker (network-first, cache fallback)
const CACHE_NAME = 'bitos-companion-v4';
const ASSETS = [
  '/',
  '/dashboard.html',
  '/chat.html',
  '/tasks.html',
  '/calendar.html',
  '/activity.html',
  '/settings.html',
  '/setup.html',
  '/pair.html',
  '/test_crypto.html',
  '/css/shared.css',
  '/js/nav.js',
  '/js/ble.js',
  '/js/auth.js',
  '/js/crypto.js',
  '/js/settings.js',
  '/manifest.json',
  '/icon-192.svg',
  '/icon-512.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Only cache same-origin app shell assets, not API calls
  const isSameOrigin = event.request.url.startsWith(self.location.origin);
  const isGET = event.request.method === 'GET';

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && isSameOrigin && isGET) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => isSameOrigin ? caches.match(event.request) : Response.error())
  );
});
