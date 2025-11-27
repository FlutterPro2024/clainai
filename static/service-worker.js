// Service Worker for ClainAI
self.addEventListener('install', function(event) {
  console.log('ClainAI Service Worker installed');
});

self.addEventListener('fetch', function(event) {
  event.respondWith(fetch(event.request));
});
