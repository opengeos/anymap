import maplibregl from "https://cdn.skypack.dev/maplibre-gl@5.5.0";

function render({ model, el }) {
  // Create unique ID for this widget instance
  const widgetId = `anymap-${Math.random().toString(36).substr(2, 9)}`;

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

  // Clear any existing content and cleanup
  if (el._map) {
    el._map.remove();
    el._map = null;
  }
  if (el._markers) {
    el._markers.forEach(marker => marker.remove());
    el._markers = [];
  }

  el.innerHTML = "";
  el.appendChild(container);

  // Load and register protocols dynamically
  const loadProtocols = async () => {
    try {
      // Load COG protocol
      if (!window.MaplibreCOGProtocol) {
        const cogScript = document.createElement('script');
        cogScript.src = 'https://unpkg.com/@geomatico/maplibre-cog-protocol@0.4.0/dist/index.js';

        await new Promise((resolve, reject) => {
          cogScript.onload = resolve;
          cogScript.onerror = reject;
          document.head.appendChild(cogScript);
        });
      }

      // Load PMTiles protocol
      if (!window.pmtiles) {
        const pmtilesScript = document.createElement('script');
        pmtilesScript.src = 'https://unpkg.com/pmtiles@3.2.0/dist/pmtiles.js';

        await new Promise((resolve, reject) => {
          pmtilesScript.onload = resolve;
          pmtilesScript.onerror = reject;
          document.head.appendChild(pmtilesScript);
        });
      }

      // Register the COG protocol
      if (window.MaplibreCOGProtocol && window.MaplibreCOGProtocol.cogProtocol) {
        maplibregl.addProtocol("cog", window.MaplibreCOGProtocol.cogProtocol);
        console.log("COG protocol registered successfully");
      } else {
        console.warn("MaplibreCOGProtocol not available");
      }

      // Register the PMTiles protocol
      if (window.pmtiles) {
        const pmtilesProtocol = new window.pmtiles.Protocol();
        maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);
        console.log("PMTiles protocol registered successfully");
      } else {
        console.warn("PMTiles not available");
      }
    } catch (error) {
      console.warn("Failed to load protocols:", error);
    }
  };

  // Load protocols before initializing map
  loadProtocols().then(() => {
    // Initialize MapLibre map after protocols are loaded
    const map = new maplibregl.Map({
      container: container,
      style: model.get("style"),
      center: model.get("center").slice().reverse(), // [lng, lat] for MapLibre
      zoom: model.get("zoom"),
      bearing: model.get("bearing"),
      pitch: model.get("pitch"),
      antialias: model.get("antialias")
    });

    // Store map instance for cleanup
    el._map = map;
    el._markers = [];
    el._controls = new Map(); // Track added controls by type and position
    el._widgetId = widgetId;

    // Restore layers, sources, controls, and projection from model state
    const restoreMapState = () => {
      const layers = model.get("_layers") || {};
      const sources = model.get("_sources") || {};
      const controls = model.get("_controls") || {};
      const projection = model.get("_projection") || {};

      // Add sources first
      Object.entries(sources).forEach(([sourceId, sourceConfig]) => {
        if (!map.getSource(sourceId)) {
          try {
            map.addSource(sourceId, sourceConfig);
          } catch (error) {
            console.warn(`Failed to restore source ${sourceId}:`, error);
          }
        }
      });

      // Then add layers
      Object.entries(layers).forEach(([layerId, layerConfig]) => {
        if (!map.getLayer(layerId)) {
          try {
            map.addLayer(layerConfig);
          } catch (error) {
            console.warn(`Failed to restore layer ${layerId}:`, error);
          }
        }
      });

      // Finally add controls
      Object.entries(controls).forEach(([controlKey, controlConfig]) => {
        if (!el._controls.has(controlKey)) {
          try {
            const { type: controlType, position, options: controlOptions } = controlConfig;
            let control;

            switch (controlType) {
              case 'navigation':
                control = new maplibregl.NavigationControl(controlOptions || {});
                break;
              case 'scale':
                control = new maplibregl.ScaleControl(controlOptions || {});
                break;
              case 'fullscreen':
                control = new maplibregl.FullscreenControl(controlOptions || {});
                break;
              case 'geolocate':
                control = new maplibregl.GeolocateControl(controlOptions || {});
                break;
              case 'attribution':
                control = new maplibregl.AttributionControl(controlOptions || {});
                break;
              case 'globe':
                control = new maplibregl.GlobeControl(controlOptions || {});
                break;
              default:
                console.warn(`Unknown control type during restore: ${controlType}`);
                return;
            }

            map.addControl(control, position);
            el._controls.set(controlKey, control);
          } catch (error) {
            console.warn(`Failed to restore control ${controlKey}:`, error);
          }
        }
      });

      // Finally set projection if it exists
      if (Object.keys(projection).length > 0) {
        try {
          map.setProjection(projection);
        } catch (error) {
          console.warn('Failed to restore projection:', error);
        }
      }
    };

    // Setup resize observer to handle container size changes
    let resizeObserver;
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        // Trigger map resize after a short delay to ensure container is sized
        setTimeout(() => {
          if (map && map.getContainer()) {
            map.resize();
          }
        }, 100);
      });
      resizeObserver.observe(el);
      resizeObserver.observe(container);
    }

    // Force initial resize after map loads and when container becomes visible
    map.on('load', () => {
      setTimeout(() => {
        map.resize();
        // Restore state after map is fully loaded
        restoreMapState();
      }, 200);
    });

    // Additional resize handling for late-rendered widgets
    const checkAndResize = () => {
      if (map && map.getContainer() && map.getContainer().offsetWidth > 0) {
        map.resize();
      }
    };

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
      setTimeout(checkAndResize, 100);
      setTimeout(checkAndResize, 500);
      setTimeout(checkAndResize, 1000);
    });

    // Handle map events and send to Python
    const sendEvent = (eventType, eventData) => {
      const currentEvents = model.get("_js_events") || [];
      const newEvents = [...currentEvents, { type: eventType, ...eventData }];
      model.set("_js_events", newEvents);
      model.save_changes();
    };

    // Map event handlers
    map.on('load', () => {
      sendEvent('load', {});
    });

    map.on('click', (e) => {
      sendEvent('click', {
        lngLat: [e.lngLat.lng, e.lngLat.lat],
        point: [e.point.x, e.point.y]
      });
    });

    map.on('moveend', () => {
      const center = map.getCenter();
      sendEvent('moveend', {
        center: [center.lat, center.lng],
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch()
      });
    });

    map.on('zoomend', () => {
      sendEvent('zoomend', {
        zoom: map.getZoom()
      });
    });

    // Listen for trait changes from Python
    model.on("change:center", () => {
      const center = model.get("center");
      map.setCenter([center[1], center[0]]); // Convert [lat, lng] to [lng, lat]
    });

    model.on("change:zoom", () => {
      map.setZoom(model.get("zoom"));
    });

    model.on("change:style", () => {
      map.setStyle(model.get("style"));
    });

    model.on("change:bearing", () => {
      map.setBearing(model.get("bearing"));
    });

    model.on("change:pitch", () => {
      map.setPitch(model.get("pitch"));
    });

    // Handle JavaScript method calls from Python
    model.on("change:_js_calls", () => {
      const calls = model.get("_js_calls") || [];
      calls.forEach(call => {
        executeMapMethod(map, call, el);
      });
      // Clear the calls after processing
      model.set("_js_calls", []);
      model.save_changes();
    });

    // Method execution function
    function executeMapMethod(map, call, el) {
      const { method, args, kwargs } = call;

      try {
        switch (method) {
          case 'flyTo':
            const flyToOptions = args[0] || {};
            if (flyToOptions.center) {
              flyToOptions.center = [flyToOptions.center[1], flyToOptions.center[0]]; // [lat,lng] to [lng,lat]
            }
            map.flyTo(flyToOptions);
            break;

          case 'addSource':
            const [sourceId, sourceConfig] = args;
            if (!map.getSource(sourceId)) {
              map.addSource(sourceId, sourceConfig);
              // Persist source in model state
              const currentSources = model.get("_sources") || {};
              currentSources[sourceId] = sourceConfig;
              model.set("_sources", currentSources);
              model.save_changes();
            }
            break;

          case 'removeSource':
            const removeSourceId = args[0];
            if (map.getSource(removeSourceId)) {
              map.removeSource(removeSourceId);
              // Remove from model state
              const currentSources = model.get("_sources") || {};
              delete currentSources[removeSourceId];
              model.set("_sources", currentSources);
              model.save_changes();
            }
            break;

          case 'addLayer':
            const [layerConfig, layerId] = args;
            const actualLayerId = layerId || layerConfig.id;
            if (!map.getLayer(actualLayerId)) {
              map.addLayer(layerConfig);
              // Persist layer in model state
              const currentLayers = model.get("_layers") || {};
              currentLayers[actualLayerId] = layerConfig;
              model.set("_layers", currentLayers);
              model.save_changes();
            }
            break;

          case 'removeLayer':
            const removeLayerId = args[0];
            if (map.getLayer(removeLayerId)) {
              map.removeLayer(removeLayerId);
              // Remove from model state
              const currentLayers = model.get("_layers") || {};
              delete currentLayers[removeLayerId];
              model.set("_layers", currentLayers);
              model.save_changes();
            }
            break;

          case 'setStyle':
            map.setStyle(args[0]);
            break;

          case 'addMarker':
            const markerData = args[0];
            const marker = new maplibregl.Marker()
              .setLngLat(markerData.coordinates)
              .addTo(map);

            if (markerData.popup) {
              const popup = new maplibregl.Popup()
                .setHTML(markerData.popup);
              marker.setPopup(popup);
            }

            el._markers.push(marker);
            break;

          case 'fitBounds':
            const [bounds, options] = args;
            // Convert [[lat,lng], [lat,lng]] to [[lng,lat], [lng,lat]]
            const mapBounds = bounds.map(bound => [bound[1], bound[0]]);
            map.fitBounds(mapBounds, options || {});
            break;

          case 'addControl':
            const [controlType, controlOptions] = args;
            const position = controlOptions?.position || 'top-right';
            const controlKey = `${controlType}_${position}`;

            // Check if this control is already added
            if (el._controls.has(controlKey)) {
              console.warn(`Control ${controlType} at position ${position} already exists`);
              return;
            }

            let control;
            switch (controlType) {
              case 'navigation':
                control = new maplibregl.NavigationControl(controlOptions || {});
                break;
              case 'scale':
                control = new maplibregl.ScaleControl(controlOptions || {});
                break;
              case 'fullscreen':
                control = new maplibregl.FullscreenControl(controlOptions || {});
                break;
              case 'geolocate':
                control = new maplibregl.GeolocateControl(controlOptions || {});
                break;
              case 'attribution':
                control = new maplibregl.AttributionControl(controlOptions || {});
                break;
              case 'globe':
                control = new maplibregl.GlobeControl(controlOptions || {});
                break;
              default:
                console.warn(`Unknown control type: ${controlType}`);
                return;
            }

            map.addControl(control, position);
            el._controls.set(controlKey, control);
            break;

          case 'removeControl':
            const [removeControlType, removePosition] = args;
            const removeControlKey = `${removeControlType}_${removePosition}`;

            if (el._controls.has(removeControlKey)) {
              const controlToRemove = el._controls.get(removeControlKey);
              map.removeControl(controlToRemove);
              el._controls.delete(removeControlKey);
            } else {
              console.warn(`Control ${removeControlType} at position ${removePosition} not found`);
            }
            break;

          case 'setProjection':
            const [projectionConfig] = args;
            try {
              map.setProjection(projectionConfig);
            } catch (error) {
              console.warn('Failed to set projection:', error);
            }
            break;

          default:
            // Try to call the method directly on the map object
            if (typeof map[method] === 'function') {
              map[method](...args);
            } else {
              console.warn(`Unknown map method: ${method}`);
            }
        }
      } catch (error) {
        console.error(`Error executing map method ${method}:`, error);
        sendEvent('error', { method, error: error.message });
      }
    }

    // Cleanup function
    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (el._markers) {
        el._markers.forEach(marker => marker.remove());
        el._markers = [];
      }
      if (el._controls) {
        el._controls.clear();
      }
      if (el._map) {
        el._map.remove();
        el._map = null;
      }
    };

  }); // End of loadProtocols().then()
}

export default { render };