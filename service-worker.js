const VERSION='3.0.0';
const CACHE='docpilot-shell-v300';
const SHELL=['/','/static/app.css?v=3.0.0','/static/app.js?v=3.0.0','/manifest.webmanifest','/static/icon-192.png','/static/icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.pathname.startsWith('/api/'))return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))))});

self.addEventListener('message',event=>{if(event.data?.type!=='DOC_PILOT_VERSION')return;event.ports?.[0]?.postMessage({version:VERSION,cache:CACHE})});
