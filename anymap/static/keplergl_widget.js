// KeplerGL-style widget using Leaflet for interactive display
// Provides KeplerGL data handling with a working interactive map

import L from "https://cdn.skypack.dev/leaflet@1.9.4";

// Load Leaflet CSS
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
    const widgetId = `keplergl-map-${Math.random().toString(36).substr(2, 9)}`;

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
    if (el._markers) {
        el._markers.forEach(marker => marker.remove());
        el._markers = [];
    }
    if (el._resizeObserver) {
        el._resizeObserver.disconnect();
        el._resizeObserver = null;
    }

    el.innerHTML = "";

    // Create map container (full size, no header)
    const mapContainer = document.createElement("div");
    mapContainer.style.cssText = `
        width: 100%;
        height: 100%;
        position: relative;
        background: #f8f9fa;
    `;

    container.appendChild(mapContainer);
    el.appendChild(container);

    // Initialize the map after ensuring DOM is ready
    const initializeMap = () => {
        try {
            // Initialize Leaflet map
            const map = L.map(mapContainer, {
                center: model.get("center"),
                zoom: model.get("zoom"),
                zoomControl: true,
                attributionControl: true
            });

            // Add dark theme tile layer (KeplerGL style)
            L.tileLayer('https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://cartodb.com/attributions">CartoDB</a>',
                subdomains: 'abcd',
                maxZoom: 19
            }).addTo(map);

            // Store references
            el._map = map;
            el._markers = [];
            el._layers = {};

            // Load initial data
            loadDataLayers(map, el, model);

            // Listen for model changes
            model.on("change:center", () => {
                const center = model.get("center");
                map.setView(center, map.getZoom());
            });

            model.on("change:zoom", () => {
                const zoom = model.get("zoom");
                map.setView(map.getCenter(), zoom);
            });

            model.on("change:_data", () => {
                loadDataLayers(map, el, model);
            });

            model.on("change:_js_calls", () => {
                handleJSCalls(map, el, model);
            });

            // Update model when map changes
            map.on('moveend', () => {
                const center = map.getCenter();
                model.set("center", [center.lat, center.lng]);
                model.save_changes();
            });

            map.on('zoomend', () => {
                model.set("zoom", map.getZoom());
                model.save_changes();
            });

            // Handle resize
            const resizeObserver = new ResizeObserver(() => {
                map.invalidateSize();
            });
            resizeObserver.observe(container);
            el._resizeObserver = resizeObserver;

            console.log("KeplerGL-style map initialized successfully");

        } catch (error) {
            console.error("Error initializing map:", error);
            mapContainer.innerHTML = `
                <div style="
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                    color: #dc3545;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                ">
                    <div style="text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 10px;">⚠️</div>
                        <div>Failed to initialize map</div>
                        <div style="font-size: 12px; opacity: 0.7; margin-top: 5px;">${error.message}</div>
                    </div>
                </div>
            `;
        }
    };

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
        setTimeout(initializeMap, 100);
    });
}

function loadDataLayers(map, el, model) {
    // Clear existing markers
    el._markers.forEach(marker => marker.remove());
    el._markers = [];

    const data = model.get("_data") || {};

    // Define colors for different datasets
    const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F'];
    let colorIndex = 0;

    for (const [datasetName, datasetInfo] of Object.entries(data)) {
        const color = colors[colorIndex % colors.length];
        colorIndex++;

        if (datasetInfo.type === 'geojson' && datasetInfo.data && datasetInfo.data.features) {
            // Handle GeoJSON data
            datasetInfo.data.features.forEach(feature => {
                if (feature.geometry && feature.geometry.type === 'Point') {
                    const [lng, lat] = feature.geometry.coordinates;
                    const properties = feature.properties || {};

                    // Create custom marker with KeplerGL-style appearance
                    const marker = L.circleMarker([lat, lng], {
                        radius: 8,
                        fillColor: color,
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    });

                    // Create popup content
                    const popupContent = createPopupContent(properties, datasetName);
                    marker.bindPopup(popupContent);

                    marker.addTo(map);
                    el._markers.push(marker);
                }
            });
        } else if (datasetInfo.type === 'csv' && Array.isArray(datasetInfo.data)) {
            // Handle CSV data
            datasetInfo.data.forEach(row => {
                // Try to find lat/lng coordinates
                const lat = row.lat || row.latitude || row.y;
                const lng = row.lng || row.longitude || row.lon || row.x;

                if (lat !== undefined && lng !== undefined) {
                    const marker = L.circleMarker([lat, lng], {
                        radius: 8,
                        fillColor: color,
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    });

                    const popupContent = createPopupContent(row, datasetName);
                    marker.bindPopup(popupContent);

                    marker.addTo(map);
                    el._markers.push(marker);
                }
            });
        }
    }

    // Fit map to show all markers if any exist
    if (el._markers.length > 0) {
        const group = new L.featureGroup(el._markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function createPopupContent(properties, datasetName) {
    let content = `<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px;">`;
    content += `<div style="font-weight: bold; color: #1976d2; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 4px;">${datasetName}</div>`;

    for (const [key, value] of Object.entries(properties)) {
        if (value !== null && value !== undefined && value !== '') {
            content += `<div style="margin: 4px 0;"><strong>${key}:</strong> ${value}</div>`;
        }
    }

    content += `</div>`;
    return content;
}



function handleJSCalls(map, el, model) {
    const calls = model.get("_js_calls") || [];
    if (calls.length === 0) return;

    for (const call of calls) {
        if (call.method === 'fly_to' || call.method === 'flyTo') {
            const params = call.params || call.kwargs || call.args?.[0] || {};
            const lat = params.lat || params.latitude;
            const lng = params.lng || params.longitude;
            const zoom = params.zoom;

            if (lat !== undefined && lng !== undefined) {
                if (zoom !== undefined) {
                    map.setView([lat, lng], zoom);
                } else {
                    map.panTo([lat, lng]);
                }
            }
        }
    }

    // Clear the calls
    model.set("_js_calls", []);
    model.save_changes();
}

// Export the render function
export default { render };