// Service worker: เก็บหน้าแอปไว้เปิดได้แม้เน็ตหลุด ส่วน /api ไปที่เซิร์ฟเวอร์เสมอ
const CACHE = 'recycle-shell-v3';
const SHELL = ['/', '/styles.css', '/fonts.css', '/app.js', '/portal.js', '/manifest.webmanifest', '/icons/icon-192.png',
  '/fonts/anuphan-thai-400.woff2', '/fonts/anuphan-latin-400.woff2', '/fonts/athiti-thai-500.woff2', '/fonts/athiti-latin-500.woff2', '/fonts/athiti-thai-600.woff2', '/fonts/athiti-latin-600.woff2', '/fonts/athiti-thai-700.woff2', '/fonts/athiti-latin-700.woff2'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  // network-first: ได้ของใหม่เสมอเมื่อมีเน็ต และใช้ของที่เก็บไว้เมื่อไม่มี
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request).then((hit) => hit || caches.match('/')))
  );
});
