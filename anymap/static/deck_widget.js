// Global flag to track if deck.gl is loaded
let deckGLLoaded = false;
let deckGLLoadPromise = null;

// Load deck.gl library synchronously if not already loaded
function loadDeckGLSync() {
  if (typeof window.deck !== 'undefined') {
    console.log('deck.gl already loaded');
    deckGLLoaded = true;
    return Promise.resolve();
  }

  if (deckGLLoadPromise) {
    return deckGLLoadPromise;
  }

  deckGLLoadPromise = new Promise((resolve, reject) => {
    console.log('Loading deck.gl library...');
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/deck.gl@9.0.31/dist.min.js';
    script.onload = () => {
      console.log('deck.gl library loaded successfully');
      if (typeof window.deck !== 'undefined') {
        deckGLLoaded = true;
        resolve();
      } else {
        reject(new Error('deck.gl library loaded but window.deck is undefined'));
      }
    };
    script.onerror = (error) => {
      console.error('Failed to load deck.gl library:', error);
      reject(error);
    };
    document.head.appendChild(script);
  });

  return deckGLLoadPromise;
}

function render({ model, el }) {
  console.log('🎯 DeckGL widget render called');

  // Create simple container
  const widgetId = `deck-${Math.random().toString(36).substr(2, 9)}`;

  el.innerHTML = `
    <div id="${widgetId}" style="width: ${model.get('width')}; height: ${model.get('height')}; position: relative; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
      <div id="${widgetId}-loading" style="display: flex; align-items: center; justify-content: center; height: 100%; color: #6c757d;">
        <div style="text-align: center;">
          <div style="font-size: 18px; margin-bottom: 8px;">🔄</div>
          <div>Loading DeckGL...</div>
        </div>
      </div>
      <div id="${widgetId}-map" style="width: 100%; height: 100%; display: none;"></div>
    </div>
  `;

  const container = el.querySelector(`#${widgetId}`);
  const loadingDiv = el.querySelector(`#${widgetId}-loading`);
  const mapDiv = el.querySelector(`#${widgetId}-map`);

  // Load deck.gl if not already loaded
  if (typeof window.deck === 'undefined') {
    console.log('Loading deck.gl library...');
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/deck.gl@9.0.31/dist.min.js';
    script.onload = () => initDeckGL();
    script.onerror = () => showError('Failed to load deck.gl library');
    document.head.appendChild(script);
  } else {
    initDeckGL();
  }

  function showError(message) {
    container.innerHTML = `
      <div style="padding: 20px; color: red; border: 2px solid red; border-radius: 4px;">
        <strong>Error:</strong> ${message}
      </div>
    `;
  }

  function initDeckGL() {
    try {
      if (typeof window.deck === 'undefined') {
        throw new Error('deck.gl not available');
      }

      console.log('✅ deck.gl ready, creating map...');

      // Hide loading, show map
      loadingDiv.style.display = 'none';
      mapDiv.style.display = 'block';

      const initialViewState = {
        longitude: model.get("center")[1],
        latitude: model.get("center")[0],
        zoom: model.get("zoom"),
        bearing: model.get("bearing") || 0,
        pitch: model.get("pitch") || 0
      };

      const deck = new window.deck.DeckGL({
        container: mapDiv,
        initialViewState: initialViewState,
        controller: model.get("controller"),
        layers: []
      });

      // Store deck instance for cleanup
      el._deck = deck;
      el._layers = new Map();

      console.log('🎉 DeckGL map created successfully!');

      // Layer management
      function addLayer(layerId, layerConfig) {
        try {
          const { type, data, ...props } = layerConfig;
          const LayerClass = window.deck[type];

          if (!LayerClass) {
            console.warn(`Unknown layer type: ${type}`);
            return;
          }

          const layer = new LayerClass({
            id: layerId,
            data,
            ...props
          });

          el._layers.set(layerId, layer);
          updateLayers();
          console.log(`✅ Added layer: ${layerId}`);

        } catch (error) {
          console.error(`Error adding layer ${layerId}:`, error);
        }
      }

      function updateLayers() {
        const layers = Array.from(el._layers.values());
        deck.setProps({ layers });
      }

      function removeLayer(layerId) {
        if (el._layers.has(layerId)) {
          el._layers.delete(layerId);
          updateLayers();
          console.log(`✅ Removed layer: ${layerId}`);
        }
      }

      // Handle method calls from Python
      model.on("change:_js_calls", () => {
        const calls = model.get("_js_calls") || [];
        calls.forEach(call => {
          if (!call || typeof call !== 'object') return;

          const { method, args } = call;
          console.log(`Executing: ${method}`);

          switch (method) {
            case "addLayer":
              const [layerConfig, layerId] = args;
              addLayer(layerId, layerConfig);
              break;

            case "removeLayer":
              removeLayer(args[0]);
              break;

            case "setViewState":
              deck.setProps({
                initialViewState: { ...deck.viewState, ...args[0] }
              });
              break;

            default:
              console.warn(`Unknown method: ${method}`);
          }
        });
      });

      // Restore existing layers
      const existingLayers = model.get("_layers") || {};
      Object.entries(existingLayers).forEach(([layerId, layerConfig]) => {
        addLayer(layerId, layerConfig);
      });

      console.log('✅ DeckGL widget ready!');

    } catch (error) {
      console.error('DeckGL initialization error:', error);
      showError(`DeckGL initialization failed: ${error.message}`);
    }
  }
}

export default { render };