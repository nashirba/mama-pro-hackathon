// One map provider: MapLibre GL JS (vendored in static/vendor) with OpenFreeMap tiles.
// The OpenFreeMap style is the only external resource; the attribution control is always expanded.
window.kamqorMap = (function () {
  "use strict";

  var STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
  var EMPTY = { type: "FeatureCollection", features: [] };
  var COLOR = "#0f766e";
  var SOURCE = "specialists";

  function formatPrice(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function link(href, text, className) {
    var a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    a.className = className;
    return a;
  }

  // The content is built with DOM nodes and textContent: names come from user-entered profiles.
  function popupContent(props, labels) {
    var root = document.createElement("div");
    root.className = "kamqor-popup";
    var name = document.createElement("p");
    name.style.fontWeight = "600";
    name.textContent = props.name;
    root.appendChild(name);
    var price;
    if (props.is_free) {
      price = labels.free;
    } else if (props.price_from !== null && props.price_from !== undefined) {
      price = labels.from.replace("__PRICE__", formatPrice(props.price_from));
    } else {
      price = labels.onRequest;
    }
    if (price) {
      var p = document.createElement("p");
      p.textContent = price;
      root.appendChild(p);
    }
    var links = document.createElement("p");
    links.style.marginTop = "6px";
    links.style.display = "flex";
    links.style.gap = "12px";
    var details = link(props.url, labels.details, "");
    var gis = link(props.two_gis_url, labels.twoGis, "");
    gis.target = "_blank";
    gis.rel = "noopener";
    [details, gis].forEach(function (a) {
      a.style.color = COLOR;
      a.style.fontWeight = "500";
      links.appendChild(a);
    });
    root.appendChild(links);
    return root;
  }

  function create(el, opts) {
    if ((opts.geojsonUrl == null) === (opts.geojson == null)) {
      throw new Error("kamqorMap.create: pass exactly one of geojsonUrl and geojson");
    }
    var clustered = opts.geojsonUrl != null;
    var labels = Object.assign({ free: "", from: "__PRICE__", onRequest: "", details: "", twoGis: "" }, opts.labels);
    var map = new maplibregl.Map({
      container: el,
      style: STYLE_URL,
      center: opts.center,
      zoom: opts.zoom,
      attributionControl: { compact: false },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    var ready = false;
    var pending = opts.geojson || null;
    var controller = null;
    var destroyed = false;

    function fit(geojson) {
      var features = geojson.features || [];
      if (clustered || features.length < 2) return;
      var bounds = new maplibregl.LngLatBounds();
      features.forEach(function (f) { bounds.extend(f.geometry.coordinates); });
      map.fitBounds(bounds, { padding: 48, maxZoom: opts.zoom, duration: 0 });
    }

    function setData(geojson) {
      if (!ready) { pending = geojson; return; }
      map.getSource(SOURCE).setData(geojson);
      fit(geojson);
    }

    function load(url) {
      if (controller) controller.abort();
      controller = new AbortController();
      var own = controller;
      return fetch(url, { signal: own.signal, headers: { Accept: "application/json" } })
        .then(function (response) {
          if (!response.ok) throw new Error("GeoJSON request failed: " + response.status);
          return response.json();
        })
        .then(function (geojson) { if (!destroyed && controller === own) setData(geojson); })
        .catch(function (error) { if (error.name !== "AbortError") console.error(error); });
    }

    function addLayers() {
      map.addSource(SOURCE, {
        type: "geojson",
        data: EMPTY,
        cluster: clustered,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });
      if (clustered) {
        map.addLayer({
          id: "clusters",
          type: "circle",
          source: SOURCE,
          filter: ["has", "point_count"],
          paint: {
            "circle-color": COLOR,
            "circle-opacity": 0.85,
            "circle-radius": ["step", ["get", "point_count"], 16, 10, 20, 50, 26],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
        map.addLayer({
          id: "cluster-count",
          type: "symbol",
          source: SOURCE,
          filter: ["has", "point_count"],
          layout: {
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Noto Sans Regular"],
            "text-size": 13,
          },
          paint: { "text-color": "#ffffff" },
        });
      }
      map.addLayer({
        id: "points",
        type: "circle",
        source: SOURCE,
        filter: clustered ? ["!", ["has", "point_count"]] : ["all"],
        paint: {
          "circle-color": COLOR,
          "circle-radius": 8,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "points", function (event) {
        var feature = event.features[0];
        new maplibregl.Popup({ offset: 12 })
          .setLngLat(feature.geometry.coordinates.slice())
          .setDOMContent(popupContent(feature.properties, labels))
          .addTo(map);
      });
      if (clustered) {
        map.on("click", "clusters", function (event) {
          var feature = event.features[0];
          map.getSource(SOURCE).getClusterExpansionZoom(feature.properties.cluster_id).then(function (zoom) {
            map.easeTo({ center: feature.geometry.coordinates, zoom: zoom });
          });
        });
      }
      (clustered ? ["clusters", "points"] : ["points"]).forEach(function (layer) {
        map.on("mouseenter", layer, function () { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, function () { map.getCanvas().style.cursor = ""; });
      });
    }

    map.on("load", function () {
      addLayers();
      ready = true;
      if (pending) { setData(pending); pending = null; }
    });

    // the container may be created hidden (mobile list/map toggle) or change its size
    var observer = new ResizeObserver(function () { map.resize(); });
    observer.observe(el);

    if (opts.geojsonUrl) load(opts.geojsonUrl);

    return {
      setData: setData,
      load: load,
      setView: function (center, zoom) { map.jumpTo({ center: center, zoom: zoom }); },
      destroy: function () {
        destroyed = true;
        if (controller) controller.abort();
        observer.disconnect();
        map.remove();
      },
    };
  }

  return { create: create };
})();
