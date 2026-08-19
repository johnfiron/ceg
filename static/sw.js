const C='ash-terminal-v11-prefix';
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll([new URL('manifest.webmanifest',self.registration.scope).href])))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  const u=e.request.url;
  if(u.includes('/api/'))return;
  const html=e.request.mode==='navigate'||(e.request.headers.get('accept')||'').includes('text/html');
  if(html){e.respondWith(fetch(e.request));return}
  e.respondWith(fetch(e.request).then(r=>{
    if(e.request.method==='GET' && r.ok){const copy=r.clone();caches.open(C).then(c=>c.put(e.request,copy));}
    return r
  }).catch(()=>caches.match(e.request)))
});
