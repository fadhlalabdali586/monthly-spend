const CACHE = 'tawzee-v4';
const CORE = ['./', './index.html', './manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(CORE.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting())
  );
});

// نسخة جديدة = نمسح كل الكاش القديم (هذا اللي كان مخلّي الأيقونة القديمة تطلع)
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// كل شي من النت أولاً، والكاش بس لو ما فيه نت — فأي تحديث أو أيقونة جديدة تطلع على طول
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  const isPage = req.mode === 'navigate' || /\/(index\.html)?$/.test(new URL(req.url).pathname);
  e.respondWith(
    fetch(req, { cache: 'no-store' }).then(res => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(isPage ? './index.html' : req, copy)); }
      return res;
    }).catch(() => caches.match(isPage ? './index.html' : req).then(h => h || caches.match('./')))
  );
});
