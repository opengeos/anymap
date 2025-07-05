function render({ model, el }) {
  // Create unique ID for this widget instance
  const widgetId = `anymap-deckgl-${Math.random().toString(36).substr(2, 9)}`;

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
  if (el._deckgl) {
    el._deckgl.finalize();
    el._deckgl = null;
  }

  el.innerHTML = "";
  el.appendChild(container);

  // Function to load external scripts
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  // Function to load external stylesheets
  function loadStylesheet(href) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`link[href="${href}"]`)) {
        resolve();
        return;
      }
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.onload = resolve;
      link.onerror = reject;
      document.head.appendChild(link);
    });
  }

  // Initialize DeckGL after loading dependencies
  async function initializeDeckGL() {
    try {
      // Load MapLibre CSS and JS
      await loadStylesheet('https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css');
      await loadScript('https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js');

      // Load DeckGL
      await loadScript('https://unpkg.com/deck.gl@9.1.12/dist.min.js');

      // Wait a bit for global objects to be available
      await new Promise(resolve => setTimeout(resolve, 100));

      // Check if required globals are available
      if (typeof deck === 'undefined') {
        throw new Error('DeckGL not loaded');
      }
      if (typeof maplibregl === 'undefined') {
        throw new Error('MapLibre GL not loaded');
      }

      // Get initial view state
      const center = model.get("center");
      const initialViewState = {
        latitude: center[0],
        longitude: center[1],
        zoom: model.get("zoom"),
        bearing: model.get("bearing"),
        pitch: model.get("pitch")
      };

      // Get controller options
      const controllerOptions = Object.assign({
        doubleClickZoom: false
      }, model.get("controller_options") || {});

      // Handle map events and send to Python
      const sendEvent = (eventType, eventData) => {
        try {
          const currentEvents = model.get("_js_events") || [];
          const newEvents = [...currentEvents, { type: eventType, ...eventData }];
          model.set("_js_events", newEvents);
          model.save_changes();
        } catch (error) {
          console.warn('Error sending event:', eventType, error);
        }
      };

      // Throttle view state updates to reduce serialization overhead
      let viewStateUpdateTimeout = null;
      const throttledViewStateUpdate = (viewState) => {
        if (viewStateUpdateTimeout) {
          clearTimeout(viewStateUpdateTimeout);
        }

        viewStateUpdateTimeout = setTimeout(() => {
          // Update model with new view state
          model.set("center", [viewState.latitude, viewState.longitude]);
          model.set("zoom", viewState.zoom);
          model.set("bearing", viewState.bearing);
          model.set("pitch", viewState.pitch);
          model.save_changes();
        }, 100); // Update every 100ms at most
      };

      // Clear loading message and initialize DeckGL
      container.innerHTML = '';

      // Initialize DeckGL
      const deckgl = new deck.DeckGL({
        container: container,
        mapStyle: model.get("style"),
        initialViewState: initialViewState,
        controller: controllerOptions,
        layers: parseDeckGLLayers(model.get("deckgl_layers") || []),
        onViewStateChange: ({ viewState }) => {
          // Use throttled update to prevent too many serialization calls
          throttledViewStateUpdate(viewState);
        },
        onClick: (info) => {
          // Send only serializable click data
          const clickData = {
            coordinate: info.coordinate || null,
            layerId: info.layer ? info.layer.id : null
          };

          // Add serializable object properties if available
          if (info.object && typeof info.object === 'object') {
            try {
              // Only include serializable properties
              const serializableObject = {};
              for (const [key, value] of Object.entries(info.object)) {
                if (typeof value !== 'function' && typeof value !== 'undefined') {
                  serializableObject[key] = value;
                }
              }
              clickData.object = serializableObject;
            } catch (e) {
              console.warn('Could not serialize click object:', e);
            }
          }

          sendEvent('click', clickData);
        }
      });

      // Store DeckGL instance for cleanup
      el._deckgl = deckgl;
      el._widgetId = widgetId;

      // Setup resize observer to handle container size changes
      let resizeObserver;
      if (window.ResizeObserver) {
        resizeObserver = new ResizeObserver(() => {
          setTimeout(() => {
            if (deckgl) {
              deckgl.setProps({ width: container.offsetWidth, height: container.offsetHeight });
            }
          }, 100);
        });
        resizeObserver.observe(el);
        resizeObserver.observe(container);
      }

      // Listen for trait changes from Python
      model.on("change:center", () => {
        const center = model.get("center");
        const viewState = {
          latitude: center[0],
          longitude: center[1],
          zoom: model.get("zoom"),
          bearing: model.get("bearing"),
          pitch: model.get("pitch")
        };
        deckgl.setProps({ initialViewState: viewState });
      });

      model.on("change:zoom", () => {
        const center = model.get("center");
        const viewState = {
          latitude: center[0],
          longitude: center[1],
          zoom: model.get("zoom"),
          bearing: model.get("bearing"),
          pitch: model.get("pitch")
        };
        deckgl.setProps({ initialViewState: viewState });
      });

      model.on("change:style", () => {
        deckgl.setProps({ mapStyle: model.get("style") });
      });

      model.on("change:bearing", () => {
        const center = model.get("center");
        const viewState = {
          latitude: center[0],
          longitude: center[1],
          zoom: model.get("zoom"),
          bearing: model.get("bearing"),
          pitch: model.get("pitch")
        };
        deckgl.setProps({ initialViewState: viewState });
      });

      model.on("change:pitch", () => {
        const center = model.get("center");
        const viewState = {
          latitude: center[0],
          longitude: center[1],
          zoom: model.get("zoom"),
          bearing: model.get("bearing"),
          pitch: model.get("pitch")
        };
        deckgl.setProps({ initialViewState: viewState });
      });

      model.on("change:deckgl_layers", () => {
        const layers = parseDeckGLLayers(model.get("deckgl_layers") || []);
        deckgl.setProps({ layers });
      });

      model.on("change:controller_options", () => {
        const controllerOptions = Object.assign({
          doubleClickZoom: false
        }, model.get("controller_options") || {});
        deckgl.setProps({ controller: controllerOptions });
      });

      // Handle JavaScript method calls from Python
      model.on("change:_js_calls", () => {
        const calls = model.get("_js_calls") || [];
        calls.forEach(call => {
          executeMapMethod(deckgl, call, el);
        });
        // Clear the calls after processing
        model.set("_js_calls", []);
        model.save_changes();
      });

      // Method execution function
      function executeMapMethod(deckgl, call, el) {
        const { method, args, kwargs } = call;

        try {
          switch (method) {
            case 'flyTo':
              const flyToOptions = args[0] || {};
              const viewState = {
                latitude: flyToOptions.center ? flyToOptions.center[0] : deckgl.viewState.latitude,
                longitude: flyToOptions.center ? flyToOptions.center[1] : deckgl.viewState.longitude,
                zoom: flyToOptions.zoom !== undefined ? flyToOptions.zoom : deckgl.viewState.zoom,
                bearing: flyToOptions.bearing !== undefined ? flyToOptions.bearing : deckgl.viewState.bearing,
                pitch: flyToOptions.pitch !== undefined ? flyToOptions.pitch : deckgl.viewState.pitch,
                transitionDuration: flyToOptions.duration || 1000
              };
              deckgl.setProps({ initialViewState: viewState });
              break;

            default:
              console.warn(`Unknown DeckGL method: ${method}`);
          }
        } catch (error) {
          console.error(`Error executing DeckGL method ${method}:`, error);
          sendEvent('error', { method, error: error.message });
        }
      }

      // Cleanup function
      return () => {
        if (resizeObserver) {
          resizeObserver.disconnect();
        }
        if (el._deckgl) {
          el._deckgl.finalize();
          el._deckgl = null;
        }
      };

    } catch (error) {
      console.error('Failed to initialize DeckGL:', error);
      // Clear any existing content and show error
      container.innerHTML = `<div style="
        padding: 20px;
        color: red;
        font-family: Arial, sans-serif;
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.95);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 1000;
      ">
        <h3 style="margin: 0 0 10px 0;">DeckGL Loading Error</h3>
        <p style="margin: 5px 0;">${error.message}</p>
        <p style="margin: 5px 0; font-size: 12px;">Please check your internet connection and try again.</p>
      </div>`;
    }
  }

  // Parse DeckGL layers from Python configuration
  function parseDeckGLLayers(layerConfigs) {
    if (typeof deck === 'undefined') {
      console.warn('DeckGL not available for layer parsing');
      return [];
    }

    // Helper function to convert accessor expressions to functions
    function parseAccessor(accessor) {
      if (typeof accessor === 'string' && accessor.startsWith('@@=')) {
        const expression = accessor.substring(3); // Remove '@@=' prefix

        try {
          // Handle arrow function expressions directly
          if (expression.includes('=>')) {
            // This is already an arrow function, just evaluate it
            return eval(`(${expression})`);
          }
          // Create a function from the expression
          // Handle different variable contexts (d = data item, f = feature, etc.)
          else if (expression.includes('f.geometry.coordinates')) {
            return new Function('f', `return ${expression}`);
          } else if (expression.includes('f.properties')) {
            return new Function('f', `return ${expression}`);
          } else if (expression.includes('d.features')) {
            // For dataTransform functions
            return new Function('d', `return ${expression}`);
          } else if (expression.includes('d.')) {
            return new Function('d', `return ${expression}`);
          } else {
            // Default context
            return new Function('d', `return ${expression}`);
          }
        } catch (error) {
          console.warn('Failed to parse accessor expression:', accessor, error);
          return accessor; // Return original if parsing fails
        }
      }
      return accessor;
    }

    // Helper function to process layer properties and convert accessors
    function processLayerProps(props) {
      const processed = { ...props };

      // List of properties that should be treated as accessors
      const accessorProps = [
        'getSourcePosition', 'getTargetPosition', 'getPosition',
        'getRadius', 'getFillColor', 'getLineColor', 'getWidth',
        'getPointRadius', 'dataTransform'
      ];

      accessorProps.forEach(prop => {
        if (prop in processed) {
          processed[prop] = parseAccessor(processed[prop]);
        }
      });

      return processed;
    }

    return layerConfigs.map(config => {
      const layerType = config["@@type"];
      const layerProps = processLayerProps({ ...config });
      delete layerProps["@@type"];

      try {
        switch (layerType) {
          case "GeoJsonLayer":
            return new deck.GeoJsonLayer(layerProps);
          case "ArcLayer":
            return new deck.ArcLayer(layerProps);
          case "ScatterplotLayer":
            return new deck.ScatterplotLayer(layerProps);
          default:
            console.warn(`Unknown DeckGL layer type: ${layerType}`);
            return null;
        }
      } catch (error) {
        console.error(`Error creating ${layerType}:`, error, layerProps);
        return null;
      }
    }).filter(layer => layer !== null);
  }

  // Show loading message
  container.innerHTML = `<div class="deckgl-loading-message" style="
    padding: 20px;
    text-align: center;
    font-family: Arial, sans-serif;
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.9);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    z-index: 1000;
  ">
    <div style="font-size: 16px; margin-bottom: 10px;">Loading DeckGL...</div>
    <div style="font-size: 12px; color: #666;">Please wait while we load the map components.</div>
  </div>`;

  // Initialize DeckGL
  initializeDeckGL();

  // Return cleanup function
  return () => {
    if (el._deckgl) {
      el._deckgl.finalize();
      el._deckgl = null;
    }
  };
}

export default { render };