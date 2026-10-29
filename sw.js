/* RUMOURPRINT AI offline library only. Never cache private investigations or external APIs. */
const CACHE="rumourprint-offline-v1";
const FILES=["/","/index.html","/offline.html","/offline-library.json","/manifest.webmanifest","/privacy.html","/offline-icon.svg"];
self.addEventListener("install",event=>{
 event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",event=>{
 event.waitUntil(Promise.all([caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("rumourprint-offline-")&&k!==CACHE).map(k=>caches.delete(k)))),self.clients.claim()]));
});
self.addEventListener("fetch",event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=="GET"||url.origin!==self.location.origin)return;
 if(!FILES.includes(url.pathname))return;
 event.respondWith(
  fetch(request).then(async response=>{
   if(response.ok){const cache=await caches.open(CACHE);await cache.put(request,response.clone())}
   return response;
  }).catch(async()=>await caches.match(request)||await caches.match("/offline.html"))
 );
});