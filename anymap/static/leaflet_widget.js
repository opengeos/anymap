// Leaflet widget implementation for anywidget
import L from "https://cdn.skypack.dev/leaflet@1.9.4";

if (!document.querySelector(`link[href*="leaflet.css"]`)) {
    const cssLink = document.createElement("link");
    cssLink.rel = "stylesheet";
    cssLink.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    cssLink.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
    cssLink.crossOrigin = '';
    document.head.appendChild(cssLink);
}

function render({ model, el }) {
    // Create unique ID for this widget instance
    const widgetId = `leaflet-map-${Math.random().toString(36).substr(2, 9)}`;

    // Create container for the map
    const container = document.createElement("div");
    container.id = widgetId;
    container.style.width = model.get("width");
    container.style.height = model.get("height");
    container.style.position = "relative";
    container.style.overflow = "hidden";

    // Ensure parent element has proper styling
    el.style.width = "100%";
    el.style.display = "block";

    // Cleanup any existing content
    if (el._map) {
        el._map.remove();
        el._map = null;
    }
    if (el._layers) {
        el._layers = {};
    }
    if (el._resizeObserver) {
        el._resizeObserver.disconnect();
        el._resizeObserver = null;
    }

    el.innerHTML = "";
    el.appendChild(container);

    // Initialize the map after ensuring Leaflet is loaded
    const initializeMap = async () => {
        try {
            // Double-check that container exists in DOM
            if (!document.getElementById(widgetId)) {
                console.error("Map container not found in DOM:", widgetId);
                return;
            }

            // Initialize Leaflet map
            const map = L.map(widgetId, {
                center: model.get("center"),
                zoom: model.get("zoom"),
                ...model.get("map_options")
            });

            // Store references for cleanup and updates
            el._map = map;
            el._layers = {};

            // Throttle model updates for performance
            let updateTimeout = null;
            const throttledModelUpdate = () => {
                if (updateTimeout) {
                    clearTimeout(updateTimeout);
                }
                updateTimeout = setTimeout(() => {
                    const center = map.getCenter();
                    model.set("center", [center.lat, center.lng]);
                    model.set("zoom", map.getZoom());
                    model.save_changes();
                    updateTimeout = null;
                }, 150); // Throttle to 150ms
            };

            // Add default tile layer
            const tileLayer = model.get("tile_layer");
            addDefaultTileLayer(map, tileLayer);

            // Load existing layers
            loadExistingLayers(map, el, model);

            // Listen for model changes
            model.on("change:center", () => {
                const center = model.get("center");
                map.setView(center, map.getZoom());
            });

            model.on("change:zoom", () => {
                const zoom = model.get("zoom");
                map.setView(map.getCenter(), zoom);
            });

            model.on("change:_js_calls", () => {
                handleJSCalls(map, el, model);
            });

            model.on("change:_layers", () => {
                updateLayers(map, el, model);
            });

            // Handle map events - update model when map changes (throttled)
            map.on("moveend", throttledModelUpdate);
            map.on("zoomend", throttledModelUpdate);

            // Handle resize
            const resizeObserver = new ResizeObserver(() => {
                map.invalidateSize();
            });
            resizeObserver.observe(container);
            el._resizeObserver = resizeObserver;

        } catch (error) {
            console.error("Error initializing Leaflet map:", error);
        }
    };

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
        setTimeout(initializeMap, 100);
    });
}

function addDefaultTileLayer(map, tileLayerName) {
    const tileProviders = {
        "OpenStreetMap": {
            url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        },
        "CartoDB.Positron": {
            url: "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://cartodb.com/attributions">CartoDB</a>'
        },
        "CartoDB.DarkMatter": {
            url: "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://cartodb.com/attributions">CartoDB</a>'
        },
        "Stamen.Terrain": {
            url: "https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
            attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.'
        },
        "Stamen.Watercolor": {
            url: "https://stamen-tiles-{s}.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
            attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://creativecommons.org/licenses/by-sa/3.0">CC BY SA</a>.'
        }
    };

    const provider = tileProviders[tileLayerName] || tileProviders["OpenStreetMap"];

    // Handle custom URL template
    if (!tileProviders[tileLayerName] && tileLayerName.includes("{z}")) {
        L.tileLayer(tileLayerName, {
            attribution: '© Map data providers'
        }).addTo(map);
    } else {
        L.tileLayer(provider.url, {
            attribution: provider.attribution,
            subdomains: ['a', 'b', 'c']
        }).addTo(map);
    }
}

function loadExistingLayers(map, el, model) {
    const layers = model.get("_layers");
    for (const layerId in layers) {
        addLayerToMap(map, el, layerId, layers[layerId]);
    }
}

function updateLayers(map, el, model) {
    const currentLayers = model.get("_layers");
    const existingLayerIds = Object.keys(el._layers);

    // Remove layers that no longer exist
    for (const layerId of existingLayerIds) {
        if (!currentLayers[layerId]) {
            removeLayerFromMap(map, el, layerId);
        }
    }

    // Add new layers
    for (const layerId in currentLayers) {
        if (!el._layers[layerId]) {
            addLayerToMap(map, el, layerId, currentLayers[layerId]);
        }
    }
}

function bindTooltip(layer, layerConfig){
    if (layerConfig.tooltip) {
        if (layerConfig.tooltip_options){
            layer.bindTooltip(layerConfig.tooltip,
                layerConfig.tooltip_options
            );
        }else{
            layer.bindTooltip(layerConfig.tooltip);
        }
    }
}

function addLayerToMap(map, el, layerId, layerConfig) {
    let layer = null;

    try {
        if (layerConfig.type === "tile") {
            layer = L.tileLayer(layerConfig.url, {
                attribution: layerConfig.attribution || ""
            });
        } else if (layerConfig.type === "marker") {
            layer = L.marker(layerConfig.latlng, {
                draggable: layerConfig.draggable || false
            });

            if (layerConfig.popup) {
                layer.bindPopup(layerConfig.popup);
            }

            bindTooltip(layer, layerConfig)

            if (layerConfig.icon) {
                const icon = L.icon(layerConfig.icon);
                layer.setIcon(icon);
            }
        } else if (layerConfig.type === "circle") {
            layer = L.circle(layerConfig.latlng, {
                radius: layerConfig.radius,
                color: layerConfig.color || "blue",
                fillColor: layerConfig.fillColor || "blue",
                fillOpacity: layerConfig.fillOpacity || 0.2,
                weight: layerConfig.weight || 3
            });
            bindTooltip(layer, layerConfig);
        } else if (layerConfig.type === "polygon") {
            layer = L.polygon(layerConfig.latlngs, {
                color: layerConfig.color || "blue",
                fillColor: layerConfig.fillColor || "blue",
                fillOpacity: layerConfig.fillOpacity || 0.2,
                weight: layerConfig.weight || 3
            });
            bindTooltip(layer, layerConfig);
        } else if (layerConfig.type === "polyline") {
            layer = L.polyline(layerConfig.latlngs, {
                color: layerConfig.color || "blue",
                weight: layerConfig.weight || 3
            });
            bindTooltip(layer, layerConfig);
        } else if (layerConfig.type === "geojson") {
            layer = L.geoJSON(layerConfig.data, layerConfig.style || {});
        } else if (layerConfig.type === "geotiff") {
            // Defer to async loader for georaster-layer-for-leaflet
            addGeotiffLayer(map, el, layerId, layerConfig);
            return; // early exit; layer added asynchronously
        }

        if (layer) {
            layer.addTo(map);
            el._layers[layerId] = layer;
        }
    } catch (error) {
        console.error("Error adding layer:", error);
    }
}

function loadScriptWithFallback(urls) {
    return new Promise((resolve, reject) => {
        let index = 0;
        const tryNext = () => {
            if (index >= urls.length) return reject(new Error('All script sources failed'));
            const url = urls[index++];
            const s = document.createElement('script');
            s.async = true;
            s.src = url;
            s.onload = () => resolve({ ok: true, url });
            s.onerror = () => {
                console.warn('Script failed, trying fallback:', url);
                s.remove();
                tryNext();
            };
            document.head.appendChild(s);
        };
        tryNext();
    });
}

function ensureGeorasterScripts() {
    if (window.GeoRasterLayer && window.parseGeoraster) return Promise.resolve(true);
    if (window._georasterLoadingPromise) return window._georasterLoadingPromise;

    const georasterUrls = [
        // Local vendor preferred
        '/files/anymap/static/vendor/georaster.browser.bundle.min.js',
        '/files/anymap/static/vendor/georaster.bundle.min.js',
        '/files/anymap/static/vendor/georaster.browser.min.js',
        // CDNs
        'https://cdn.jsdelivr.net/npm/georaster@1.6.0/dist/georaster.browser.bundle.min.js',
        'https://fastly.jsdelivr.net/npm/georaster@1.6.0/dist/georaster.browser.bundle.min.js',
        'https://unpkg.com/georaster@1.6.0/dist/georaster.browser.bundle.min.js'
    ];
    // Pin to a pre-ESM UMD build to avoid georaster-stack ESM import
    const layerUrls = [
        // Local vendor preferred
        '/files/anymap/static/vendor/georaster-layer-for-leaflet.min.js',
        // CDN pinned to 2.0.2 which provides UMD min.js
        'https://cdn.jsdelivr.net/npm/georaster-layer-for-leaflet@2.0.2/dist/georaster-layer-for-leaflet.min.js',
        'https://fastly.jsdelivr.net/npm/georaster-layer-for-leaflet@2.0.2/dist/georaster-layer-for-leaflet.min.js',
        'https://unpkg.com/georaster-layer-for-leaflet@2.0.2/dist/georaster-layer-for-leaflet.min.js'
    ];

    // Temporarily ensure UMD path in case environment exposes CommonJS globals
    const prevModule = window.module; const prevExports = window.exports; try { delete window.module; delete window.exports; } catch(e) {}
    window._georasterLoadingPromise = loadScriptWithFallback(georasterUrls)
        .then(() => loadScriptWithFallback(layerUrls))
        .then(() => true)
        .catch((err) => {
            console.error('Failed to load georaster scripts from all sources:', err);
            throw err;
        })
        .finally(() => { if (prevModule !== undefined) window.module = prevModule; if (prevExports !== undefined) window.exports = prevExports; });

    return window._georasterLoadingPromise;
}

function addGeotiffLayer(map, el, layerId, layerConfig) {
    ensureGeorasterScripts()
        .then(() => window.parseGeoraster(layerConfig.url))
        .then((georaster) => {
            const opts = { ...layerConfig, georaster };
            delete opts.type; delete opts.url; delete opts.fit_bounds;

            try {
                const bands = georaster.numberOfRasters || (georaster.bands ? georaster.bands.length : 1);
                if (!opts.pixelValuesToColorFn && bands === 1 && georaster.mins && georaster.maxs) {
                    const min = georaster.mins[0];
                    const max = georaster.maxs[0];
                    const opacity = (typeof layerConfig.opacity === 'number') ? layerConfig.opacity : 1.0;
                    opts.pixelValuesToColorFn = (values) => {
                        const v = values[0];
                        if (v === null || v === undefined || Number.isNaN(v)) return null;
                        let t = (v - min) / (max - min);
                        t = Math.max(0, Math.min(1, t));
                        const gray = Math.round(255 * t);
                        return `rgba(${gray},${gray},${gray},${opacity})`;
                    };
                }
            } catch (e) { console.warn('Default color mapping failed:', e); }

            const geoLayer = new GeoRasterLayer(opts);
            geoLayer.addTo(map);
            el._layers[layerId] = geoLayer;
            if (layerConfig.fit_bounds !== false && geoLayer.getBounds) {
                try { map.fitBounds(geoLayer.getBounds()); } catch (e) {}
            }
        })
        .catch((err) => {
            console.error('Error adding GeoTIFF layer:', err);
        });
}

function removeLayerFromMap(map, el, layerId) {
    const layer = el._layers[layerId];
    if (layer) {
        map.removeLayer(layer);
        delete el._layers[layerId];
    }
}

function handleJSCalls(map, el, model) {
    const calls = model.get("_js_calls");

    for (const call of calls) {
        try {
            if (call.method === "flyTo") {
                const options = call.args[0];
                map.flyTo(options.center, options.zoom || map.getZoom());
            } else if (call.method === "setView") {
                const center = call.args[0];
                const zoom = call.args[1] || map.getZoom();
                map.setView(center, zoom);
            } else if (call.method === "fitBounds") {
                const bounds = call.args[0];
                map.fitBounds(bounds);
            } else if (call.method === "zoomIn") {
                map.zoomIn();
            } else if (call.method === "zoomOut") {
                map.zoomOut();
            } else if (call.method === "panTo") {
                const latlng = call.args[0];
                map.panTo(latlng);
            } else if (call.method === "addLayer") {
                const layerConfig = call.args[0];
                const layerId = call.args[1];
                addLayerToMap(map, el, layerId, layerConfig);
            } else if (call.method === "removeLayer") {
                const layerId = call.args[0];
                removeLayerFromMap(map, el, layerId);
            }
        } catch (error) {
            console.error("Error executing JS call:", error);
        }
    }
}

export default { render };
