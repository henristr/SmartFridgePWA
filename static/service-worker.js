self.addEventListener("install", (event) => {
  console.log("Service Worker installiert");
});

self.addEventListener("activate", (event) => {
  console.log("Service Worker aktiv");
});

self.addEventListener("fetch", (event) => {
  // später für Offline-Modus interessant
});
