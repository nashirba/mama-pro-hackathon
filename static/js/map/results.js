// Glue of the results page map. Loaded once from <head>: htmx re-executes inline scripts on history restore,
// this file is never swapped, so there is one instance and one set of listeners for the page lifetime.
(function () {
  "use strict";
  if (window.kamqorResultsMapLoaded) return;
  window.kamqorResultsMapLoaded = true;

  var current = null;

  function readJson(id) {
    var node = document.getElementById(id);
    return node ? JSON.parse(node.textContent) : null;
  }

  function destroy() {
    if (!current) return;
    try { current.destroy(); } catch (error) { console.error(error); }
    current = null;
  }

  // `#map-config` lives inside `#results`, so every htmx swap brings the center, zoom and GeoJSON URL of the new filters
  function init() {
    destroy();
    var el = document.getElementById("map");
    var cfg = readJson("map-config");
    if (!el || !cfg || !window.kamqorMap) return;
    // a history snapshot may bring back stale maplibre DOM; keep the server-rendered "Список" pill and status
    el.querySelectorAll(".maplibregl-canvas-container, .maplibregl-control-container").forEach(function (n) { n.remove(); });
    el.classList.remove("maplibregl-map");
    current = window.kamqorMap.create(el, {
      center: cfg.center, zoom: cfg.zoom, geojsonUrl: cfg.geojsonUrl, labels: readJson("map-labels"), listButton: true,
    });
    current.config = cfg;
  }

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("htmx:historyRestore", init);
  document.addEventListener("htmx:afterSwap", function (event) {
    if (!current || !event.target || event.target.id !== "results") return;
    var cfg = readJson("map-config");
    if (!cfg) return;
    if (JSON.stringify([cfg.center, cfg.zoom]) !== JSON.stringify([current.config.center, current.config.zoom])) {
      current.setView(cfg.center, cfg.zoom);
    }
    current.config = cfg;
    current.load(cfg.geojsonUrl);
  });
})();
