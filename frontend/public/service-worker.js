// service-worker.js — Thakuma's Recipe PWA Service Worker
const CACHE_VERSION = 'thakuma-v1';
const CACHE_STATIC_NAME = `${CACHE_VERSION}-static`;
const CACHE_RUNTIME_NAME = `${CACHE_VERSION}-runtime`;

// Essential application shell assets to precache on install
const PRECACHE_ASSETS = [
  '/offline.html',
  '/manifest.webmanifest',
  '/css/navigation.css',
  '/assets/icons.css',
  '/assets/images/thakuma_brand_mark.webp',
  '/assets/icons/pwa-192x192.png',
  '/assets/icons/pwa-512x512.png',
  '/apple-touch-icon.png'
];

// Security guard: URLs and patterns that must NEVER be cached
function isNonCacheable(request) {
  const url = new URL(request.url);

  // 1. Non-GET requests (POST, PUT, DELETE, etc.)
  if (request.method !== 'GET') {
    return true;
  }

  // 2. Authenticated API calls and Supabase endpoints
  if (url.pathname.startsWith('/api/') || url.pathname.includes('/api')) {
    return true;
  }
  if (url.hostname.includes('supabase.co')) {
    return true;
  }

  // 3. Requests with Authorization header (cannot inspect headers directly for cross-origin, but check if custom auth header exists)
  if (request.headers && request.headers.has('Authorization')) {
    return true;
  }

  // 4. ImageKit signed media, private audio, or temporary signed URLs
  if (url.hostname.includes('imagekit.io') && (url.searchParams.has('ik-s') || url.pathname.includes('audio') || url.pathname.includes('recipes/'))) {
    return true;
  }

  // 5. Browser extension schemas or non-http(s)
  if (!url.protocol.startsWith('http')) {
    return true;
  }

  return false;
}

// Install Event — Precache essential offline assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_STATIC_NAME).then((cache) => {
      // Use cache.addAll with individual catch to avoid total failure if one asset is missing
      return Promise.allSettled(
        PRECACHE_ASSETS.map((asset) =>
          cache.add(asset).catch((err) => {
            console.warn(`[PWA SW] Precache failed for ${asset}:`, err);
          })
        )
      );
    })
  );
});

// Activate Event — Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name.startsWith('thakuma-') && name !== CACHE_STATIC_NAME && name !== CACHE_RUNTIME_NAME)
          .map((name) => {
            console.log(`[PWA SW] Deleting obsolete cache: ${name}`);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// Listen for skipWaiting command from client (for seamless update flow)
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Fetch Event
self.addEventListener('fetch', (event) => {
  const request = event.request;

  // STRICT SECURITY CHECK: Never cache authenticated APIs or user-sensitive endpoints
  if (isNonCacheable(request)) {
    return; // Let the browser handle standard network request without service worker intervention
  }

  // Navigation requests (HTML documents) — Network-First with /offline.html fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            // Optional: Clone and update cached page shell
            const responseClone = response.clone();
            caches.open(CACHE_RUNTIME_NAME).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(async () => {
          // If network failed, try cached version of requested page first
          const cachedPage = await caches.match(request);
          if (cachedPage) {
            return cachedPage;
          }
          // Otherwise fall back to the dedicated offline.html page
          const offlineFallback = await caches.match('/offline.html');
          if (offlineFallback) {
            return offlineFallback;
          }
          return new Response('Offline — Please check your connection.', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'text/plain; charset=utf-8' }
          });
        })
    );
    return;
  }

  // Static Assets (CSS, JS, Fonts, Images) — Cache-First with Network Revalidation (Stale-While-Revalidate)
  const url = new URL(request.url);
  const isStaticAsset =
    url.pathname.startsWith('/assets/') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.webp') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.woff2') ||
    url.pathname.endsWith('.woff') ||
    url.hostname.includes('fonts.googleapis.com') ||
    url.hostname.includes('fonts.gstatic.com');

  if (isStaticAsset) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_STATIC_NAME).then((cache) => {
                cache.put(request, responseToCache);
              });
            }
            return networkResponse;
          })
          .catch(() => cachedResponse); // fallback to cached if network fails

        return cachedResponse || fetchPromise;
      })
    );
  }
});

