// OpenLayers widget implementation for anywidget

// Load OpenLayers from CDN if not already loaded
async function loadOpenLayers() {
    if (typeof ol !== 'undefined') {
        return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
        // Load CSS first
        const cssLink = document.createElement('link');
        cssLink.rel = 'stylesheet';
        cssLink.href = 'https://cdn.jsdelivr.net/npm/ol@v10.6.1/ol.css';
        cssLink.crossOrigin = '';
        document.head.appendChild(cssLink);

        // Load JS
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/ol@v10.6.1/dist/ol.js';
        script.crossOrigin = '';
        script.onload = () => resolve();
        script.onerror = () => reject(new Error('Failed to load OpenLayers'));
        document.head.appendChild(script);
    });
}

function render({ model, el }) {
    // Create unique ID for this widget instance
    const widgetId = `openlayers-map-${Math.random().toString(36).substr(2, 9)}`;

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
        el._map.dispose();
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

    // Initialize the map after ensuring OpenLayers is loaded
    const initializeMap = async () => {
        try {
            // Wait for OpenLayers to load
            await loadOpenLayers();

            // Double-check that container exists in DOM
            if (!document.getElementById(widgetId)) {
                console.error("Map container not found in DOM:", widgetId);
                return;
            }

            // Import OpenLayers modules
            const { Map, View } = ol;
            const { Tile: TileLayer, Vector: VectorLayer } = ol.layer;
            const { OSM, XYZ, Vector: VectorSource } = ol.source;
            const { Feature } = ol;
            const { Point, Circle: CircleGeom, Polygon, LineString } = ol.geom;
            const { Style, Fill, Stroke, Icon, Circle: CircleStyle } = ol.style;
            const { fromLonLat, toLonLat } = ol.proj;
            const { Overlay } = ol;
            const { GeoJSON } = ol.format;

            // Initialize OpenLayers map
            const view = new View({
                center: fromLonLat(model.get("center")),
                zoom: model.get("zoom"),
                projection: model.get("projection") || 'EPSG:3857'
            });

            const map = new Map({
                target: widgetId,
                view: view
            });

            // Store references for cleanup and updates
            el._map = map;
            el._layers = {};
            el._view = view;

            // Throttle model updates for performance
            let updateTimeout = null;
            const throttledModelUpdate = () => {
                if (updateTimeout) {
                    clearTimeout(updateTimeout);
                }
                updateTimeout = setTimeout(() => {
                    const center = toLonLat(view.getCenter());
                    model.set("center", center);
                    model.set("zoom", view.getZoom());
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
                view.setCenter(fromLonLat(center));
            });

            model.on("change:zoom", () => {
                const zoom = model.get("zoom");
                view.setZoom(zoom);
            });

            model.on("change:_js_calls", () => {
                handleJSCalls(map, el, model);
            });

            model.on("change:_layers", () => {
                updateLayers(map, el, model);
            });

            // Handle map events - update model when map changes (throttled)
            view.on("change:center", throttledModelUpdate);
            view.on("change:resolution", throttledModelUpdate);

            // Handle resize
            const resizeObserver = new ResizeObserver(() => {
                map.updateSize();
            });
            resizeObserver.observe(container);
            el._resizeObserver = resizeObserver;

        } catch (error) {
            console.error("Error initializing OpenLayers map:", error);
        }
    };

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
        setTimeout(initializeMap, 100);
    });
}

function addDefaultTileLayer(map, tileLayerName) {
    const { Tile: TileLayer } = ol.layer;
    const { OSM, XYZ } = ol.source;

    const tileProviders = {
        "OSM": {
            source: () => new OSM()
        },
        "CartoDB.Positron": {
            source: () => new XYZ({
                url: "https://cartodb-basemaps-{a-c}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
                attributions: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://cartodb.com/attributions">CartoDB</a>'
            })
        },
        "CartoDB.DarkMatter": {
            source: () => new XYZ({
                url: "https://cartodb-basemaps-{a-c}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
                attributions: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://cartodb.com/attributions">CartoDB</a>'
            })
        },
        "Stamen.Terrain": {
            source: () => new XYZ({
                url: "https://stamen-tiles-{a-c}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
                attributions: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.'
            })
        }
    };

    const provider = tileProviders[tileLayerName] || tileProviders["OSM"];

    // Handle custom URL template
    let source;
    if (!tileProviders[tileLayerName] && tileLayerName.includes("{z}")) {
        source = new XYZ({
            url: tileLayerName,
            attributions: '© Map data providers'
        });
    } else {
        source = provider.source();
    }

    const layer = new TileLayer({ source });
    map.addLayer(layer);
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

function addLayerToMap(map, el, layerId, layerConfig) {
    let layer = null;

    try {
        const { Tile: TileLayer, Vector: VectorLayer } = ol.layer;
        const { XYZ, Vector: VectorSource } = ol.source;
        const { Feature } = ol;
        const { Point, Circle: CircleGeom, Polygon, LineString } = ol.geom;
        const { Style, Fill, Stroke, Icon, Circle: CircleStyle } = ol.style;
        const { fromLonLat } = ol.proj;
        const { GeoJSON } = ol.format;

        if (layerConfig.type === "tile") {
            layer = new TileLayer({
                source: new XYZ({
                    url: layerConfig.url,
                    attributions: layerConfig.attribution || ""
                })
            });
        } else if (layerConfig.type === "marker") {
            const feature = new Feature({
                geometry: new Point(fromLonLat(layerConfig.coordinate))
            });

            if (layerConfig.popup) {
                feature.set('popup', layerConfig.popup);
            }

            const vectorSource = new VectorSource({
                features: [feature]
            });

            let style = new Style({
                image: new CircleStyle({
                    radius: 8,
                    fill: new Fill({ color: 'red' }),
                    stroke: new Stroke({ color: 'white', width: 2 })
                })
            });

            if (layerConfig.icon && layerConfig.icon.src) {
                style = new Style({
                    image: new Icon({
                        src: layerConfig.icon.src,
                        scale: layerConfig.icon.scale || 1
                    })
                });
            }

            layer = new VectorLayer({
                source: vectorSource,
                style: style
            });
        } else if (layerConfig.type === "circle") {
            const feature = new Feature({
                geometry: new CircleGeom(fromLonLat(layerConfig.center), layerConfig.radius)
            });

            const vectorSource = new VectorSource({
                features: [feature]
            });

            layer = new VectorLayer({
                source: vectorSource,
                style: new Style({
                    fill: new Fill({
                        color: hexToRgba(layerConfig.fillColor || 'blue', layerConfig.fillOpacity || 0.2)
                    }),
                    stroke: new Stroke({
                        color: layerConfig.color || 'blue',
                        width: layerConfig.strokeWidth || 2
                    })
                })
            });
        } else if (layerConfig.type === "polygon") {
            const feature = new Feature({
                geometry: new Polygon(layerConfig.coordinates.map(ring =>
                    ring.map(coord => fromLonLat(coord))
                ))
            });

            const vectorSource = new VectorSource({
                features: [feature]
            });

            layer = new VectorLayer({
                source: vectorSource,
                style: new Style({
                    fill: new Fill({
                        color: hexToRgba(layerConfig.fillColor || 'blue', layerConfig.fillOpacity || 0.2)
                    }),
                    stroke: new Stroke({
                        color: layerConfig.color || 'blue',
                        width: layerConfig.strokeWidth || 2
                    })
                })
            });
        } else if (layerConfig.type === "linestring") {
            const feature = new Feature({
                geometry: new LineString(layerConfig.coordinates.map(coord => fromLonLat(coord)))
            });

            const vectorSource = new VectorSource({
                features: [feature]
            });

            layer = new VectorLayer({
                source: vectorSource,
                style: new Style({
                    stroke: new Stroke({
                        color: layerConfig.color || 'blue',
                        width: layerConfig.strokeWidth || 3
                    })
                })
            });
        } else if (layerConfig.type === "geojson") {
            const vectorSource = new VectorSource({
                features: new GeoJSON().readFeatures(layerConfig.data, {
                    featureProjection: 'EPSG:3857'
                })
            });

            layer = new VectorLayer({
                source: vectorSource,
                style: layerConfig.style ? createStyleFromConfig(layerConfig.style) : undefined
            });
        } else if (layerConfig.type === "vector") {
            const features = layerConfig.features.map(featureConfig => {
                const feature = new Feature(featureConfig.geometry);
                if (featureConfig.properties) {
                    for (const [key, value] of Object.entries(featureConfig.properties)) {
                        feature.set(key, value);
                    }
                }
                return feature;
            });

            const vectorSource = new VectorSource({ features });

            layer = new VectorLayer({
                source: vectorSource,
                style: layerConfig.style ? createStyleFromConfig(layerConfig.style) : undefined
            });
        }

        if (layer) {
            map.addLayer(layer);
            el._layers[layerId] = layer;
        }
    } catch (error) {
        console.error("Error adding layer:", error);
    }
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
    const { fromLonLat } = ol.proj;

    for (const call of calls) {
        try {
            if (call.method === "flyTo") {
                const options = call.args[0];
                const view = el._view;
                view.animate({
                    center: fromLonLat(options.center),
                    zoom: options.zoom || view.getZoom(),
                    duration: 1000
                });
            } else if (call.method === "setView") {
                const center = call.args[0];
                const zoom = call.args[1] || el._view.getZoom();
                el._view.setCenter(fromLonLat(center));
                el._view.setZoom(zoom);
            } else if (call.method === "fitExtent") {
                const extent = call.args[0];
                el._view.fit(extent, { duration: 1000 });
            } else if (call.method === "zoomIn") {
                el._view.setZoom(el._view.getZoom() + 1);
            } else if (call.method === "zoomOut") {
                el._view.setZoom(el._view.getZoom() - 1);
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

// Helper functions
function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function createStyleFromConfig(styleConfig) {
    const { Style, Fill, Stroke, Circle: CircleStyle } = ol.style;

    const style = new Style();

    if (styleConfig.fill) {
        style.setFill(new Fill(styleConfig.fill));
    }

    if (styleConfig.stroke) {
        style.setStroke(new Stroke(styleConfig.stroke));
    }

    if (styleConfig.image) {
        if (styleConfig.image.circle) {
            style.setImage(new CircleStyle(styleConfig.image.circle));
        }
    }

    return style;
}

export default { render };