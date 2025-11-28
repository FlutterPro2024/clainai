// Service Worker for ClainAI
const CACHE_NAME = 'clainai-v2';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/app.js',
  '/login'
];

self.addEventListener('install', function(event) {
  console.log('ClainAI Service Worker installed');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});
