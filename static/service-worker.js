const CACHE_NAME = 'mini-supply-app-v2'; // v2 کر دیا تاکہ پرانا Cache ڈیلیٹ ہو
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/static/icon-192.png',     // یہ Fix کیا - تمہارے پاس logo نہیں icon ہے
  '/static/icon-512.png'      // یہ Fix کیا
  // '/static/style.css' ہٹا دیا - تمہارے پاس یہ فائل نہیں ہے
  // '/static/script.js' ہٹا دیا - تمہارے پاس یہ فائل نہیں ہے
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting(); // یہ Add کیا - فوراً نیا ورژن چلے
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response; // Cache سے دو
        }
        return fetch(event.request).then(networkResponse => {
          // نئی ریکویسٹ کو Cache میں Save کرو
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        });
      })
      .catch(error => {
        // انٹرنیٹ نہیں تو Offline پیج دکھاؤ - اگر ہے تو
        return caches.match('/offline.html');
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName); // پرانا Cache ڈیلیٹ
          }
        })
      );
    })
  );
  return self.clients.claim();
});