// Helper function to process DeckGL properties
function processDeckGLProps(props) {
  const processed = {};

  for (const [key, value] of Object.entries(props)) {
    if (typeof value === 'string') {
      // Handle coordinate system constants
      if (key === 'coordinateSystem' && value.startsWith('COORDINATE_SYSTEM.')) {
        try {
          // Convert string like "COORDINATE_SYSTEM.METER_OFFSETS" to actual constant
          const constantName = value.replace('COORDINATE_SYSTEM.', '');
          if (window.deck && window.deck.COORDINATE_SYSTEM && window.deck.COORDINATE_SYSTEM[constantName] !== undefined) {
            processed[key] = window.deck.COORDINATE_SYSTEM[constantName];
            console.log(`Converted coordinate system: ${value} -> ${window.deck.COORDINATE_SYSTEM[constantName]}`);
          } else {
            console.warn(`Unknown coordinate system: ${value}, using as-is`);
            processed[key] = value;
          }
        } catch (e) {
          console.warn(`Failed to parse coordinate system: ${value}`, e);
          processed[key] = value;
        }
      }
      // Handle different string accessor patterns
      else if (key.startsWith('get') && !value.startsWith('@@=')) {
        // Convert simple property names to accessor functions
        // Special cases for common property names
        if (value === 'position') {
          processed[key] = d => d.position;
        } else if (value === 'color') {
          processed[key] = d => d.color;
        } else if (value === 'normal') {
          processed[key] = d => d.normal;
        } else {
          processed[key] = d => d[value];
        }
      } else if (value.startsWith('@@=')) {
        // Handle JavaScript expressions (from DeckGL backend pattern)
        try {
          const expression = value.substring(3); // Remove '@@='
          processed[key] = new Function('d', `return ${expression}`);
        } catch (e) {
          console.warn(`Failed to parse expression: ${value}`, e);
          processed[key] = value;
        }
      } else {
        processed[key] = value;
      }
    } else {
      processed[key] = value;
    }
  }

  return processed;
}

// Layer Control class
class LayerControl {
  constructor(options, map, model) {
    this.options = options;
    this.map = map;
    this.model = model;
    this.collapsed = options.collapsed !== false;
    this.layerStates = options.layerStates || {};
    this.targetLayers = options.layers || Object.keys(this.layerStates);
    this.userInteractingWithSlider = false;

    // Create control container
    this.container = document.createElement('div');
    this.container.className = 'maplibregl-ctrl maplibregl-ctrl-group maplibregl-ctrl-layer-control';

    // Create toggle button
    this.button = document.createElement('button');
    this.button.type = 'button';
    this.button.title = 'Layer Control';
    this.button.setAttribute('aria-label', 'Layer Control');

    // Create icon
    const icon = document.createElement('span');
    icon.className = 'layer-control-icon';
    this.button.appendChild(icon);

    // Create panel
    this.panel = document.createElement('div');
    this.panel.className = 'layer-control-panel';
    if (!this.collapsed) {
      this.panel.classList.add('expanded');
    }

    // Add header
    const header = document.createElement('div');
    header.className = 'layer-control-panel-header';
    header.textContent = 'Layers';
    this.panel.appendChild(header);

    // Build layer items
    this.buildLayerItems();

    // Add event listeners
    this.button.addEventListener('click', () => this.toggle());

    // Assemble control
    this.container.appendChild(this.button);
    this.container.appendChild(this.panel);

    // Click outside to close
    document.addEventListener('click', (e) => {
      if (!this.container.contains(e.target)) {
        this.collapse();
      }
    });

    // Listen for external layer changes
    this.setupLayerChangeListeners();

    // Listen for model changes to detect new layers
    this.setupModelChangeListeners();
  }


  buildLayerItems() {
    // Clear existing items first (in case of rebuild)
    const existingItems = this.panel.querySelectorAll('.layer-control-item');
    existingItems.forEach(item => item.remove());

    // Add items for all layers in our state
    Object.entries(this.layerStates).forEach(([layerId, state]) => {
      if (this.targetLayers.includes(layerId)) {
        this.addLayerItem(layerId, state);
      }
    });
  }

  toggle() {
    if (this.collapsed) {
      this.expand();
    } else {
      this.collapse();
    }
  }

  expand() {
    this.collapsed = false;
    this.panel.classList.add('expanded');
  }

  collapse() {
    this.collapsed = true;
    this.panel.classList.remove('expanded');
  }

  toggleLayerVisibility(layerId, visible) {
    // Update local state
    if (this.layerStates[layerId]) {
      this.layerStates[layerId].visible = visible;
    }

    // Call map's visibility method
    this.map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');

    // Sync back to Python
    this.model.set('_js_events', [...this.model.get('_js_events'), {
      type: 'layer_visibility_changed',
      layerId: layerId,
      visible: visible
    }]);
    this.model.save_changes();
  }

  changeLayerOpacity(layerId, opacity) {
    // Update local state
    if (this.layerStates[layerId]) {
      this.layerStates[layerId].opacity = opacity;
    }

    // Apply opacity to map layer
    const layer = this.map.getLayer(layerId);
    if (layer) {
      const layerType = layer.type;
      let opacityProperty;

      switch (layerType) {
        case 'fill':
          opacityProperty = 'fill-opacity';
          break;
        case 'line':
          opacityProperty = 'line-opacity';
          break;
        case 'circle':
          opacityProperty = 'circle-opacity';
          break;
        case 'symbol':
          this.map.setPaintProperty(layerId, 'icon-opacity', opacity);
          this.map.setPaintProperty(layerId, 'text-opacity', opacity);
          return;
        case 'raster':
          opacityProperty = 'raster-opacity';
          break;
        case 'background':
          opacityProperty = 'background-opacity';
          break;
        default:
          opacityProperty = `${layerType}-opacity`;
      }

      this.map.setPaintProperty(layerId, opacityProperty, opacity);
    }

    // Sync back to Python
    this.model.set('_js_events', [...this.model.get('_js_events'), {
      type: 'layer_opacity_changed',
      layerId: layerId,
      opacity: opacity
    }]);
    this.model.save_changes();
  }

  onAdd(map) {
    return this.container;
  }

  setupLayerChangeListeners() {
    // Listen for map layer property changes to sync UI
    this.map.on('styledata', () => {
      // Update UI when map style changes (with a small delay to ensure changes are applied)
      setTimeout(() => {
        this.updateLayerStatesFromMap();
        this.checkForNewLayers();
      }, 100);
    });

    // Also listen for data changes which can trigger updates
    this.map.on('data', (e) => {
      if (e.sourceDataType === 'content') {
        setTimeout(() => {
          this.updateLayerStatesFromMap();
          this.checkForNewLayers();
        }, 100);
      }
    });

    // Listen for source add events (indicates new layers may be added)
    this.map.on('sourcedata', (e) => {
      if (e.sourceDataType === 'metadata') {
        setTimeout(() => {
          this.checkForNewLayers();
        }, 150);
      }
    });
  }

  setupModelChangeListeners() {
    // Listen for changes to the layer_dict in the Python model
    this.model.on('change:_layer_dict', () => {
      setTimeout(() => {
        this.checkForNewLayers();
      }, 100);
    });

    // Listen for layer additions/removals
    this.model.on('change:_layers', () => {
      setTimeout(() => {
        this.checkForNewLayers();
      }, 100);
    });
  }

  updateLayerStatesFromMap() {
    // Update local state and UI based on current map layer states
    Object.keys(this.layerStates).forEach(layerId => {
      const layer = this.map.getLayer(layerId);
      if (layer) {
        // Check visibility
        const visibility = this.map.getLayoutProperty(layerId, 'visibility');
        const isVisible = visibility !== 'none';

        // Check opacity
        const layerType = layer.type;
        let opacity = 1.0;

        switch (layerType) {
          case 'fill':
            opacity = this.map.getPaintProperty(layerId, 'fill-opacity') || 1.0;
            break;
          case 'line':
            opacity = this.map.getPaintProperty(layerId, 'line-opacity') || 1.0;
            break;
          case 'circle':
            opacity = this.map.getPaintProperty(layerId, 'circle-opacity') || 1.0;
            break;
          case 'symbol':
            opacity = this.map.getPaintProperty(layerId, 'icon-opacity') || 1.0;
            break;
          case 'raster':
            opacity = this.map.getPaintProperty(layerId, 'raster-opacity') || 1.0;
            break;
          case 'background':
            opacity = this.map.getPaintProperty(layerId, 'background-opacity') || 1.0;
            break;
        }

        // Update local state
        if (this.layerStates[layerId]) {
          this.layerStates[layerId].visible = isVisible;
          this.layerStates[layerId].opacity = opacity;
        }

        // Update UI elements
        this.updateUIForLayer(layerId, isVisible, opacity);
      }
    });
  }

  updateUIForLayer(layerId, visible, opacity) {
    // Skip UI updates if user is currently interacting with a slider
    if (this.userInteractingWithSlider) {
      return;
    }

    // Find the UI elements for this layer using data attribute
    const layerItems = this.panel.querySelectorAll('.layer-control-item');

    layerItems.forEach(item => {
      // Use data attribute for exact matching instead of text content
      if (item.dataset.layerId === layerId) {
        const checkbox = item.querySelector('.layer-control-checkbox');
        const opacitySlider = item.querySelector('.layer-control-opacity');

        // Update checkbox
        if (checkbox) {
          checkbox.checked = visible;
        }

        // Update opacity slider
        if (opacitySlider) {
          opacitySlider.value = opacity;
          opacitySlider.title = `Opacity: ${Math.round(opacity * 100)}%`;
        }
      }
    });
  }

  checkForNewLayers() {
    // Check for new user-added layers by monitoring the model's layer_dict
    const currentLayers = this.model.get('_layers') || {};
    const currentLayerDict = this.model.get('_layer_dict') || {};

    // Check for new layers in the layer_dict that aren't in our layerStates
    Object.keys(currentLayerDict).forEach(layerId => {
      // Skip if we already have this layer in our control
      if (this.layerStates[layerId]) {
        return;
      }

      // Skip if this layer is filtered out
      if (this.options.layers && !this.options.layers.includes(layerId)) {
        return;
      }

      // Get layer info from layer_dict
      const layerInfo = currentLayerDict[layerId];
      if (layerInfo) {
        // Add to our layer states
        this.layerStates[layerId] = {
          visible: layerInfo.visible !== false,
          opacity: layerInfo.opacity || 1.0,
          name: layerId
        };

        // Add to target layers if not filtering
        if (!this.options.layers) {
          this.targetLayers.push(layerId);
        }

        // Add UI element for this layer
        this.addLayerItem(layerId, this.layerStates[layerId]);
      }
    });
  }

  addNewLayer(layerId, layerConfig) {
    // Get current layer properties
    const visibility = this.map.getLayoutProperty(layerId, 'visibility');
    const isVisible = visibility !== 'none';

    // Get opacity based on layer type
    const layerType = layerConfig.type;
    let opacity = 1.0;

    switch (layerType) {
      case 'fill':
        opacity = this.map.getPaintProperty(layerId, 'fill-opacity') || 1.0;
        break;
      case 'line':
        opacity = this.map.getPaintProperty(layerId, 'line-opacity') || 1.0;
        break;
      case 'circle':
        opacity = this.map.getPaintProperty(layerId, 'circle-opacity') || 1.0;
        break;
      case 'symbol':
        opacity = this.map.getPaintProperty(layerId, 'icon-opacity') || 1.0;
        break;
      case 'raster':
        opacity = this.map.getPaintProperty(layerId, 'raster-opacity') || 1.0;
        break;
      case 'background':
        opacity = this.map.getPaintProperty(layerId, 'background-opacity') || 1.0;
        break;
    }

    // Add to our layer states
    this.layerStates[layerId] = {
      visible: isVisible,
      opacity: opacity,
      name: layerId
    };

    // Update target layers if not filtering
    if (!this.options.layers) {
      this.targetLayers.push(layerId);
    }

    // Create and add the UI element for this layer
    this.addLayerItem(layerId, this.layerStates[layerId]);
  }

  isUserAddedLayer(layerId) {
    // Check if this layer is in our layerStates (meaning it was added by user via Python)
    // Background style layers are NOT in layerStates except for the special "Background" entry
    return this.layerStates[layerId] && layerId !== 'Background';
  }

  addLayerItem(layerId, state) {
    const item = document.createElement('div');
    item.className = 'layer-control-item';
    item.setAttribute('data-layer-id', layerId);

    // Checkbox for visibility
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'layer-control-checkbox';
    checkbox.checked = state.visible;
    checkbox.addEventListener('change', () => {
      if (layerId === 'Background') {
        this.toggleBackgroundVisibility(checkbox.checked);
      } else {
        this.toggleLayerVisibility(layerId, checkbox.checked);
      }
    });

    // Layer name - use friendly name for Background
    const name = document.createElement('span');
    name.className = 'layer-control-name';
    name.textContent = layerId === 'Background' ? 'Background' : (state.name || layerId);
    name.title = layerId === 'Background' ? 'Background' : (state.name || layerId);

    // Opacity slider
    const opacity = document.createElement('input');
    opacity.type = 'range';
    opacity.className = 'layer-control-opacity';
    opacity.min = '0';
    opacity.max = '1';
    opacity.step = '0.01';
    opacity.value = state.opacity;
    opacity.title = `Opacity: ${Math.round(state.opacity * 100)}%`;

    // Track when user starts interacting with slider
    const startSliderInteraction = () => {
      this.userInteractingWithSlider = true;

      // Define handlers to end interaction
      const endInteraction = () => {
        this.userInteractingWithSlider = false;
        document.removeEventListener('mouseup', endInteraction);
        document.removeEventListener('touchend', endInteraction);
        document.removeEventListener('mouseleave', endInteraction);
        document.removeEventListener('touchcancel', endInteraction);
      };

      document.addEventListener('mouseup', endInteraction);
      document.addEventListener('touchend', endInteraction);
      document.addEventListener('mouseleave', endInteraction);
      document.addEventListener('touchcancel', endInteraction);
    };

    opacity.addEventListener('mousedown', startSliderInteraction);
    opacity.addEventListener('touchstart', startSliderInteraction);

    // Track when user stops interacting with slider (in case pointer stays on slider)
    opacity.addEventListener('mouseup', () => {
      this.userInteractingWithSlider = false;
    });
    opacity.addEventListener('touchend', () => {
      this.userInteractingWithSlider = false;
    });
    opacity.addEventListener('mouseleave', () => {
      this.userInteractingWithSlider = false;
    });
    opacity.addEventListener('touchcancel', () => {
      this.userInteractingWithSlider = false;
    });

    opacity.addEventListener('input', () => {
      if (layerId === 'Background') {
        this.changeBackgroundOpacity(parseFloat(opacity.value));
      } else {
        this.changeLayerOpacity(layerId, parseFloat(opacity.value));
      }
      opacity.title = `Opacity: ${Math.round(opacity.value * 100)}%`;
    });

    item.appendChild(checkbox);
    item.appendChild(name);
    item.appendChild(opacity);

    this.panel.appendChild(item);
  }

  toggleBackgroundVisibility(visible) {
    // Update local state
    if (this.layerStates['Background']) {
      this.layerStates['Background'].visible = visible;
    }

    // Apply to all style layers (Background layers)
    const styleLayers = this.map.getStyle().layers || [];
    styleLayers.forEach(layer => {
      // Skip user-added layers (they have different sources)
      if (!this.isUserAddedLayer(layer.id)) {
        this.map.setLayoutProperty(layer.id, 'visibility', visible ? 'visible' : 'none');
      }
    });

    // Sync back to Python
    this.model.set('_js_events', [...this.model.get('_js_events'), {
      type: 'layer_visibility_changed',
      layerId: 'Background',
      visible: visible
    }]);
    this.model.save_changes();
  }

  changeBackgroundOpacity(opacity) {
    // Update local state
    if (this.layerStates['Background']) {
      this.layerStates['Background'].opacity = opacity;
    }

    // Apply to all style layers (Background layers)
    const styleLayers = this.map.getStyle().layers || [];
    styleLayers.forEach(styleLayer => {
      // Skip user-added layers
      if (!this.isUserAddedLayer(styleLayer.id)) {
        const layer = this.map.getLayer(styleLayer.id);
        if (layer) {
          const layerType = layer.type;
          let opacityProperty;

          switch (layerType) {
            case 'fill':
              opacityProperty = 'fill-opacity';
              break;
            case 'line':
              opacityProperty = 'line-opacity';
              break;
            case 'circle':
              opacityProperty = 'circle-opacity';
              break;
            case 'symbol':
              this.map.setPaintProperty(styleLayer.id, 'icon-opacity', opacity);
              this.map.setPaintProperty(styleLayer.id, 'text-opacity', opacity);
              return;
            case 'raster':
              opacityProperty = 'raster-opacity';
              break;
            case 'background':
              opacityProperty = 'background-opacity';
              break;
            default:
              opacityProperty = `${layerType}-opacity`;
          }

          // Apply opacity if the property exists for this layer type
          if (opacityProperty) {
            this.map.setPaintProperty(styleLayer.id, opacityProperty, opacity);
          }
        }
      }
    });

    // Sync back to Python
    this.model.set('_js_events', [...this.model.get('_js_events'), {
      type: 'layer_opacity_changed',
      layerId: 'Background',
      opacity: opacity
    }]);
    this.model.save_changes();
  }

  onRemove() {
    this.container.parentNode.removeChild(this.container);
  }
}

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
      // Load MapLibre GL JS first
      if (!window.maplibregl) {
        const maplibreScript = document.createElement('script');
        maplibreScript.src = 'https://unpkg.com/maplibre-gl@latest/dist/maplibre-gl.js';

        await new Promise((resolve, reject) => {
          maplibreScript.onload = resolve;
          maplibreScript.onerror = reject;
          document.head.appendChild(maplibreScript);
        });

        console.log("MapLibre GL JS loaded successfully");
      }

      // Load MapLibre GL CSS
      if (!document.querySelector('link[href*="maplibre-gl.css"]')) {
        const maplibreCSS = document.createElement('link');
        maplibreCSS.rel = 'stylesheet';
        maplibreCSS.href = 'https://unpkg.com/maplibre-gl@latest/dist/maplibre-gl.css';
        document.head.appendChild(maplibreCSS);
      }

      // Load COG protocol
      if (!window.MaplibreCOGProtocol) {
        const cogScript = document.createElement('script');
        cogScript.src = 'https://unpkg.com/@geomatico/maplibre-cog-protocol@0.8.0/dist/index.js';

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

      // Load MapboxDraw
      if (!window.MapboxDraw) {
        const drawScript = document.createElement('script');
        drawScript.src = 'https://www.unpkg.com/@mapbox/mapbox-gl-draw@1.5.0/dist/mapbox-gl-draw.js';

        await new Promise((resolve, reject) => {
          drawScript.onload = resolve;
          drawScript.onerror = reject;
          document.head.appendChild(drawScript);
        });

        // Load CSS for MapboxDraw
        if (!document.querySelector('link[href*="mapbox-gl-draw.css"]')) {
          const drawCSS = document.createElement('link');
          drawCSS.rel = 'stylesheet';
          drawCSS.href = 'https://www.unpkg.com/@mapbox/mapbox-gl-draw@1.5.0/dist/mapbox-gl-draw.css';
          document.head.appendChild(drawCSS);
        }
      }

      // Load Terra Draw
      if (!window.MaplibreTerradrawControl) {
        const terraDrawScript = document.createElement('script');
        terraDrawScript.src = 'https://cdn.jsdelivr.net/npm/@watergis/maplibre-gl-terradraw@1.0.1/dist/maplibre-gl-terradraw.umd.js';

        await new Promise((resolve, reject) => {
          terraDrawScript.onload = resolve;
          terraDrawScript.onerror = reject;
          document.head.appendChild(terraDrawScript);
        });

        // Load CSS for Terra Draw
        if (!document.querySelector('link[href*="maplibre-gl-terradraw.css"]')) {
          const terraDrawCSS = document.createElement('link');
          terraDrawCSS.rel = 'stylesheet';
          terraDrawCSS.href = 'https://cdn.jsdelivr.net/npm/@watergis/maplibre-gl-terradraw@1.0.1/dist/maplibre-gl-terradraw.css';
          document.head.appendChild(terraDrawCSS);
        }
      }

      // Load MapLibre GL Geocoder
      if (!window.MaplibreGeocoder) {
        const geocoderScript = document.createElement('script');
        geocoderScript.src = 'https://unpkg.com/@maplibre/maplibre-gl-geocoder@1.5.0/dist/maplibre-gl-geocoder.min.js';

        await new Promise((resolve, reject) => {
          geocoderScript.onload = resolve;
          geocoderScript.onerror = reject;
          document.head.appendChild(geocoderScript);
        });

        // Load CSS for MapLibre GL Geocoder
        if (!document.querySelector('link[href*="maplibre-gl-geocoder.css"]')) {
          const geocoderCSS = document.createElement('link');
          geocoderCSS.rel = 'stylesheet';
          geocoderCSS.href = 'https://unpkg.com/@maplibre/maplibre-gl-geocoder@1.5.0/dist/maplibre-gl-geocoder.css';
          document.head.appendChild(geocoderCSS);
        }
      }

      // Load Google Street View Plugin
      if (!window.MaplibreGoogleStreetView) {
        const streetViewScript = document.createElement('script');
        streetViewScript.src = 'https://cdn.jsdelivr.net/npm/@rezw4n/maplibre-google-streetview@latest/dist/maplibre-google-streetview.js';

        await new Promise((resolve, reject) => {
          streetViewScript.onload = resolve;
          streetViewScript.onerror = reject;
          document.head.appendChild(streetViewScript);
        });

        // Load CSS for Google Street View Plugin
        if (!document.querySelector('link[href*="maplibre-google-streetview.css"]')) {
          const streetViewCSS = document.createElement('link');
          streetViewCSS.rel = 'stylesheet';
          streetViewCSS.href = 'https://cdn.jsdelivr.net/npm/@rezw4n/maplibre-google-streetview@latest/dist/maplibre-google-streetview.css';
          document.head.appendChild(streetViewCSS);
        }
      }

      // Load MapLibre GL Basemaps Control
      if (!window.MaplibreGLBasemapsControl) {
        const basemapsScript = document.createElement('script');
        basemapsScript.src = 'https://unpkg.com/maplibre-gl-basemaps@0.1.3/lib/index.js';

        await new Promise((resolve, reject) => {
          basemapsScript.onload = resolve;
          basemapsScript.onerror = reject;
          document.head.appendChild(basemapsScript);
        });

        // Load CSS for MapLibre GL Basemaps Control
        if (!document.querySelector('link[href*="basemaps.css"]')) {
          const basemapsCSS = document.createElement('link');
          basemapsCSS.rel = 'stylesheet';
          basemapsCSS.href = 'https://unpkg.com/maplibre-gl-basemaps@0.1.3/lib/basemaps.css';
          document.head.appendChild(basemapsCSS);
        }
      }

      // Load DeckGL for overlay layers
      if (!window.deck) {
        const deckScript = document.createElement('script');
        deckScript.src = 'https://unpkg.com/deck.gl@9.0.0/dist.min.js';

        await new Promise((resolve, reject) => {
          deckScript.onload = resolve;
          deckScript.onerror = reject;
          document.head.appendChild(deckScript);
        });

        console.log("DeckGL loaded successfully");
      }

      // Load loaders.gl LASLoader using ESM CDN
      if (!window._loadersGLLASLoader) {
        try {
          // Try using esm.sh which properly handles ES modules
          const lasModule = await import('https://esm.sh/@loaders.gl/las@latest');
          if (lasModule.LASLoader) {
            window._loadersGLLASLoader = lasModule.LASLoader;
            console.log('✓ Loaded LASLoader via esm.sh:', window._loadersGLLASLoader);
          } else {
            console.warn('LASLoader not found in esm.sh module, trying cdn.skypack.dev');
            // Try skypack as fallback
            const lasModule2 = await import('https://cdn.skypack.dev/@loaders.gl/las@latest');
            window._loadersGLLASLoader = lasModule2.LASLoader;
            console.log('✓ Loaded LASLoader via skypack:', window._loadersGLLASLoader);
          }
        } catch (error) {
          console.error('Failed to load LASLoader via ESM CDNs:', error);
          console.warn('LAZ files will not be supported without LASLoader');
        }
      }

      // Register the COG protocol
      if (window.MaplibreCOGProtocol && window.MaplibreCOGProtocol.cogProtocol) {
        // Check if protocol is already registered to avoid duplicates
        if (!window._cogProtocolRegistered) {
          maplibregl.addProtocol("cog", window.MaplibreCOGProtocol.cogProtocol);
          window._cogProtocolRegistered = true;
          console.log("COG protocol registered successfully");
        } else {
          console.log("COG protocol already registered");
        }
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

      // Configure MapboxDraw for MapLibre compatibility
      if (window.MapboxDraw) {
        window.MapboxDraw.constants.classes.CANVAS = 'maplibregl-canvas';
        window.MapboxDraw.constants.classes.CONTROL_BASE = 'maplibregl-ctrl';
        window.MapboxDraw.constants.classes.CONTROL_PREFIX = 'maplibregl-ctrl-';
        window.MapboxDraw.constants.classes.CONTROL_GROUP = 'maplibregl-ctrl-group';
        window.MapboxDraw.constants.classes.ATTRIBUTION = 'maplibregl-ctrl-attrib';

        // Create custom styles for MapLibre compatibility
        window.MapLibreDrawStyles = [
          // Point styles
          {
            "id": "gl-draw-point-point-stroke-inactive",
            "type": "circle",
            "filter": ["all", ["==", "active", "false"], ["==", "$type", "Point"], ["==", "meta", "feature"], ["!=", "mode", "static"]],
            "paint": {
              "circle-radius": 5,
              "circle-opacity": 1,
              "circle-color": "#000"
            }
          },
          {
            "id": "gl-draw-point-inactive",
            "type": "circle",
            "filter": ["all", ["==", "active", "false"], ["==", "$type", "Point"], ["==", "meta", "feature"], ["!=", "mode", "static"]],
            "paint": {
              "circle-radius": 3,
              "circle-color": "#3bb2d0"
            }
          },
          {
            "id": "gl-draw-point-stroke-active",
            "type": "circle",
            "filter": ["all", ["==", "active", "true"], ["!=", "meta", "midpoint"], ["==", "$type", "Point"]],
            "paint": {
              "circle-radius": 7,
              "circle-color": "#000"
            }
          },
          {
            "id": "gl-draw-point-active",
            "type": "circle",
            "filter": ["all", ["==", "active", "true"], ["!=", "meta", "midpoint"], ["==", "$type", "Point"]],
            "paint": {
              "circle-radius": 5,
              "circle-color": "#fbb03b"
            }
          },
          // Line styles - fixed for MapLibre
          {
            "id": "gl-draw-line-inactive",
            "type": "line",
            "filter": ["all", ["==", "active", "false"], ["==", "$type", "LineString"], ["!=", "mode", "static"]],
            "layout": {
              "line-cap": "round",
              "line-join": "round"
            },
            "paint": {
              "line-color": "#3bb2d0",
              "line-width": 2
            }
          },
          {
            "id": "gl-draw-line-active",
            "type": "line",
            "filter": ["all", ["==", "active", "true"], ["==", "$type", "LineString"]],
            "layout": {
              "line-cap": "round",
              "line-join": "round"
            },
            "paint": {
              "line-color": "#fbb03b",
              "line-width": 2,
              "line-dasharray": ["literal", [0.2, 2]]
            }
          },
          // Polygon fill
          {
            "id": "gl-draw-polygon-fill-inactive",
            "type": "fill",
            "filter": ["all", ["==", "active", "false"], ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
            "paint": {
              "fill-color": "#3bb2d0",
              "fill-outline-color": "#3bb2d0",
              "fill-opacity": 0.1
            }
          },
          {
            "id": "gl-draw-polygon-fill-active",
            "type": "fill",
            "filter": ["all", ["==", "active", "true"], ["==", "$type", "Polygon"]],
            "paint": {
              "fill-color": "#fbb03b",
              "fill-outline-color": "#fbb03b",
              "fill-opacity": 0.1
            }
          },
          // Polygon stroke
          {
            "id": "gl-draw-polygon-stroke-inactive",
            "type": "line",
            "filter": ["all", ["==", "active", "false"], ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
            "layout": {
              "line-cap": "round",
              "line-join": "round"
            },
            "paint": {
              "line-color": "#3bb2d0",
              "line-width": 2
            }
          },
          {
            "id": "gl-draw-polygon-stroke-active",
            "type": "line",
            "filter": ["all", ["==", "active", "true"], ["==", "$type", "Polygon"]],
            "layout": {
              "line-cap": "round",
              "line-join": "round"
            },
            "paint": {
              "line-color": "#fbb03b",
              "line-width": 2,
              "line-dasharray": ["literal", [0.2, 2]]
            }
          },
          // Vertices (corner points) for editing
          {
            "id": "gl-draw-polygon-and-line-vertex-stroke-inactive",
            "type": "circle",
            "filter": ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
            "paint": {
              "circle-radius": 5,
              "circle-color": "#fff"
            }
          },
          {
            "id": "gl-draw-polygon-and-line-vertex-inactive",
            "type": "circle",
            "filter": ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
            "paint": {
              "circle-radius": 3,
              "circle-color": "#fbb03b"
            }
          },
          // Midpoint
          {
            "id": "gl-draw-polygon-midpoint",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "midpoint"]],
            "paint": {
              "circle-radius": 3,
              "circle-color": "#fbb03b"
            }
          },
          // Active line vertex styles
          {
            "id": "gl-draw-line-vertex-stroke-active",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
            "paint": {
              "circle-radius": 7,
              "circle-color": "#fff"
            }
          },
          {
            "id": "gl-draw-line-vertex-active",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
            "paint": {
              "circle-radius": 5,
              "circle-color": "#fbb03b"
            }
          },
          // Polygon vertex styles for direct select mode
          {
            "id": "gl-draw-polygon-vertex-stroke-active",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
            "paint": {
              "circle-radius": 7,
              "circle-color": "#fff"
            }
          },
          {
            "id": "gl-draw-polygon-vertex-active",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
            "paint": {
              "circle-radius": 5,
              "circle-color": "#fbb03b"
            }
          }
        ];

        console.log("MapboxDraw configured for MapLibre compatibility with custom styles");
      } else {
        console.warn("MapboxDraw not available");
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
      center: model.get("center"), // [lng, lat] format
      zoom: model.get("zoom"),
      bearing: model.get("bearing"),
      pitch: model.get("pitch"),
      antialias: model.get("antialias")
    });

    // Force default cursor for all map interactions
    map.on('load', () => {
      const canvas = map.getCanvas();
      canvas.style.cursor = 'default';
    });

    // Store map instance for cleanup
    el._map = map;
    el._markers = [];
    el._controls = new Map(); // Track added controls by type and position
    el._drawControl = null; // Track draw control instance
    el._terraDrawControl = null; // Track Terra Draw control instance
    el._streetViewPlugins = new Map(); // Track Street View plugin instances
    el._streetViewObservers = new Map(); // Track Street View mutation observers
    el._streetViewHandlers = new Map(); // Track Street View event handlers
    el._widgetId = widgetId;
    el._mapReady = false; // Track if map is fully loaded
    el._pendingCalls = []; // Queue for calls before map is ready

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
            // Check if this is a COG source and if protocol is ready
            const isCogSource = sourceConfig.url && sourceConfig.url.startsWith('cog://');
            if (isCogSource && !window._cogProtocolRegistered) {
              console.warn(`COG protocol not ready for source ${sourceId}, will retry`);
              // Retry after a short delay
              setTimeout(() => {
                if (!map.getSource(sourceId) && window._cogProtocolRegistered) {
                  try {
                    map.addSource(sourceId, sourceConfig);
                    console.log(`COG source ${sourceId} added successfully on retry`);
                  } catch (retryError) {
                    console.warn(`Failed to add COG source ${sourceId} on retry:`, retryError);
                  }
                }
              }, 500);
            } else {
              map.addSource(sourceId, sourceConfig);
            }
          } catch (error) {
            console.warn(`Failed to restore source ${sourceId}:`, error);
          }
        }
      });

      // Then add layers (with delay for COG-dependent layers)
      Object.entries(layers).forEach(([layerId, layerConfig]) => {
        if (!map.getLayer(layerId)) {
          try {
            // Check if this layer uses a COG source
            const sourceId = layerConfig.source;
            const sourceConfig = sources[sourceId];
            const isCogLayer = sourceConfig && sourceConfig.url && sourceConfig.url.startsWith('cog://');

            if (isCogLayer && !window._cogProtocolRegistered) {
              // Retry adding COG-dependent layers after source is ready
              setTimeout(() => {
                if (!map.getLayer(layerId) && map.getSource(sourceId)) {
                  try {
                    map.addLayer(layerConfig);
                    console.log(`COG layer ${layerId} added successfully on retry`);
                  } catch (retryError) {
                    console.warn(`Failed to add COG layer ${layerId} on retry:`, retryError);
                  }
                }
              }, 600);
            } else {
              map.addLayer(layerConfig);
            }
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
              case 'draw':
                // Handle draw control restoration
                if (window.MapboxDraw && !el._drawControl) {
                  // Use custom styles if provided, otherwise use MapLibre compatibility styles
                  const customStyles = controlOptions.customStyles;
                  const drawOptions = {
                    ...controlOptions,
                    styles: customStyles || window.MapLibreDrawStyles || undefined
                  };
                  el._drawControl = new window.MapboxDraw(drawOptions);
                  map.addControl(el._drawControl, position);

                  // Track selection state for preserving selection during updates
                  let lastSelectedFeatureIds = [];
                  let preserveSelectionOnNextChange = false;
                  const preserveSelectionOnEdit = controlOptions.preserveSelectionOnEdit !== false;

                  // Set up draw event handlers with data sync
                  map.on('draw.create', (e) => {
                    const allData = el._drawControl.getAll();
                    model.set('_draw_data', allData);
                    model.save_changes();
                    sendEvent('draw.create', { features: e.features, allData: allData });
                  });

                  map.on('draw.update', (e) => {
                    // Store selected feature IDs before update to preserve selection
                    if (preserveSelectionOnEdit) {
                      const selectedFeatures = el._drawControl.getSelected().features;
                      if (selectedFeatures.length > 0) {
                        lastSelectedFeatureIds = selectedFeatures.map(f => f.id);
                        preserveSelectionOnNextChange = true;

                        // Re-select the features after a short delay to ensure the update completes
                        setTimeout(() => {
                          if (preserveSelectionOnNextChange && lastSelectedFeatureIds.length > 0) {
                            try {
                              // Check if features still exist before re-selecting
                              const allFeatures = el._drawControl.getAll().features;
                              const validIds = lastSelectedFeatureIds.filter(id =>
                                allFeatures.some(f => f.id === id)
                              );

                              if (validIds.length > 0) {
                                el._drawControl.changeMode('simple_select', { featureIds: validIds });
                              }
                            } catch (err) {
                              console.warn('Failed to restore selection after update:', err);
                            }
                            preserveSelectionOnNextChange = false;
                          }
                        }, 10);
                      }
                    }

                    const allData = el._drawControl.getAll();
                    model.set('_draw_data', allData);
                    model.save_changes();
                    sendEvent('draw.update', { features: e.features, allData: allData });
                  });

                  map.on('draw.delete', (e) => {
                    const allData = el._drawControl.getAll();
                    model.set('_draw_data', allData);
                    model.save_changes();
                    sendEvent('draw.delete', { features: e.features, allData: allData });
                  });

                  map.on('draw.selectionchange', (e) => {
                    // Don't update tracking if we're in the middle of preserving selection
                    if (!preserveSelectionOnNextChange) {
                      lastSelectedFeatureIds = e.features.map(f => f.id);
                    }
                    sendEvent('draw.selectionchange', { features: e.features });
                  });

                  console.log('Draw control restored successfully with custom styles');
                } else {
                  console.warn('MapboxDraw not available or already added during restore');
                }
                return;
              case 'layer_control':
                // Handle layer control restoration
                control = new LayerControl(controlOptions || {}, map, model);
                break;
              case 'geocoder':
                // Handle geocoder control restoration
                if (window.MaplibreGeocoder) {
                  const apiConfig = controlOptions.api_config || {};

                  // Create geocoder API implementation
                  const geocoderApi = {
                    forwardGeocode: async (config) => {
                      const features = [];
                      try {
                        const request = `${apiConfig.api_url || 'https://nominatim.openstreetmap.org/search'}?q=${config.query}&format=geojson&polygon_geojson=1&addressdetails=1&limit=${apiConfig.limit || 5}`;
                        const response = await fetch(request);
                        const geojson = await response.json();

                        for (const feature of geojson.features) {
                          const center = [
                            feature.bbox[0] + (feature.bbox[2] - feature.bbox[0]) / 2,
                            feature.bbox[1] + (feature.bbox[3] - feature.bbox[1]) / 2,
                          ];
                          const point = {
                            type: "Feature",
                            geometry: {
                              type: "Point",
                              coordinates: center,
                            },
                            place_name: feature.properties.display_name,
                            properties: feature.properties,
                            text: feature.properties.display_name,
                            place_type: ["place"],
                            center,
                          };
                          features.push(point);
                        }
                      } catch (e) {
                        console.error(`Failed to forwardGeocode with error: ${e}`);
                      }

                      return { features };
                    },
                  };

                  // Create geocoder control
                  const geocoderOptions = {
                    maplibregl: maplibregl,
                    placeholder: apiConfig.placeholder || 'Search for places...',
                    collapsed: controlOptions.collapsed !== false,
                    ...controlOptions
                  };
                  delete geocoderOptions.api_config; // Remove from options passed to geocoder
                  delete geocoderOptions.position; // Remove position from geocoder options

                  control = new window.MaplibreGeocoder(geocoderApi, geocoderOptions);
                  console.log('Geocoder control restored successfully');
                } else {
                  console.warn('MaplibreGeocoder not available during restore');
                  return;
                }
                break;
              case 'terra_draw':
                // Handle Terra Draw control restoration
                if (window.MaplibreTerradrawControl && !el._terraDrawControl) {
                  const terraDrawOptions = {
                    ...controlOptions
                  };
                  el._terraDrawControl = new window.MaplibreTerradrawControl.MaplibreTerradrawControl(terraDrawOptions);
                  map.addControl(el._terraDrawControl, position);

                  console.log('Terra Draw control restored successfully');

                  // Load saved Terra Draw data if it exists
                  const savedTerraDrawData = model.get("_terra_draw_data");
                  if (savedTerraDrawData && savedTerraDrawData.features && savedTerraDrawData.features.length > 0) {
                    try {
                      // Terra Draw data loading would need to be implemented based on the library's API
                      console.log('Saved Terra Draw data found:', savedTerraDrawData);
                    } catch (error) {
                      console.error('Failed to load saved Terra Draw data:', error);
                    }
                  }
                } else {
                  console.warn('MaplibreTerradrawControl not available or already added during restore');
                }
                return;
              case 'google_streetview':
                // Handle Google Street View plugin restoration
                if (window.MaplibreGoogleStreetView) {
                  const apiKey = controlOptions.api_key;
                  if (apiKey) {
                    try {
                      const streetViewOptions = {
                        map: map,
                        apiKey: apiKey,
                        iframeOptions: {
                          allow: 'accelerometer; gyroscope; geolocation'
                        }
                      };

                      // Create the Street View plugin instance (not a control)
                      const streetViewPlugin = new window.MaplibreGoogleStreetView(streetViewOptions);

                      // Store the plugin instance for later management
                      if (!el._streetViewPlugins) {
                        el._streetViewPlugins = new Map();
                      }
                      el._streetViewPlugins.set(controlKey, streetViewPlugin);

                      // Force plugin elements to be contained within the map
                      const repositionStreetViewElements = () => {
                        try {
                          const mapContainer = map.getContainer();

                          // Find Street View elements using comprehensive selectors
                          const streetViewElements = document.querySelectorAll(
                            '[class*="streetview"], [class*="street-view"], [class*="pegman"], [class*="peg-man"], [class*="google-streetview"], [id*="streetview"], [id*="street-view"], [id*="pegman"]'
                          );

                          // Also check for any floating control-like elements
                          const allElements = Array.from(document.querySelectorAll('*'));
                          const floatingElements = allElements.filter(el => {
                            if (mapContainer.contains(el)) return false;
                            const style = window.getComputedStyle(el);
                            return (
                              (style.position === 'fixed' || style.position === 'absolute') &&
                              parseInt(style.zIndex) > 999 &&
                              el.offsetWidth > 0 && el.offsetHeight > 0 &&
                              el.offsetWidth < 100 && el.offsetHeight < 100
                            );
                          });

                          const allStreetViewElements = [...streetViewElements, ...floatingElements];

                          allStreetViewElements.forEach(element => {
                            if (!mapContainer.contains(element)) {
                              console.log('Moving Street View element into map container:', element);
                              element.style.position = 'absolute';
                              element.style.zIndex = '1000';
                              mapContainer.appendChild(element);

                              const pos = controlOptions.position || 'top-left';
                              if (pos.includes('top')) {
                                element.style.top = '10px';
                                element.style.bottom = 'auto';
                              } else {
                                element.style.bottom = '10px';
                                element.style.top = 'auto';
                              }
                              if (pos.includes('left')) {
                                element.style.left = '10px';
                                element.style.right = 'auto';
                              } else {
                                element.style.right = '10px';
                                element.style.left = 'auto';
                              }
                            }
                          });
                        } catch (error) {
                          console.warn('Failed to reposition Street View elements:', error);
                        }
                      };

                      setTimeout(repositionStreetViewElements, 100);
                      setTimeout(repositionStreetViewElements, 500);
                      setTimeout(repositionStreetViewElements, 1000);

                      // Add iframe permission fix event listener
                      const permissionHandler = function(event) {
                        if (event.target && event.target.tagName === 'IFRAME' &&
                            (event.target.id === 'street-view-iframe' ||
                             (event.target.parentNode && event.target.parentNode.id === 'street-view'))) {
                          event.target.setAttribute('allow', 'accelerometer; gyroscope; geolocation');
                        }
                      };

                      // Store the handler so we can clean it up later
                      if (!el._streetViewHandlers) {
                        el._streetViewHandlers = new Map();
                      }
                      el._streetViewHandlers.set(controlKey, permissionHandler);

                      // Use modern event listener instead of deprecated DOMNodeInserted
                      const observer = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                          mutation.addedNodes.forEach(function(node) {
                            if (node.nodeType === 1) { // Element node
                              // Handle iframe permissions
                              if (node.tagName === 'IFRAME' &&
                                  (node.id === 'street-view-iframe' ||
                                   (node.parentNode && node.parentNode.id === 'street-view'))) {
                                node.setAttribute('allow', 'accelerometer; gyroscope; geolocation');
                              }

                              // Handle Street View control positioning - check multiple patterns
                              const isStreetViewElement = (
                                (node.className && (
                                  node.className.includes('streetview') ||
                                  node.className.includes('street-view') ||
                                  node.className.includes('google-streetview') ||
                                  node.className.includes('pegman') ||
                                  node.className.includes('peg-man')
                                )) ||
                                (node.id && (
                                  node.id.includes('streetview') ||
                                  node.id.includes('street-view') ||
                                  node.id.includes('pegman')
                                )) ||
                                // Check if it's a floating control-like element
                                (() => {
                                  try {
                                    const style = window.getComputedStyle(node);
                                    return (
                                      (style.position === 'fixed' || style.position === 'absolute') &&
                                      parseInt(style.zIndex) > 999 &&
                                      node.offsetWidth > 0 && node.offsetHeight > 0 &&
                                      node.offsetWidth < 100 && node.offsetHeight < 100
                                    );
                                  } catch (e) {
                                    return false;
                                  }
                                })()
                              );

                              if (isStreetViewElement) {
                                const mapContainer = map.getContainer();
                                if (!mapContainer.contains(node)) {
                                  console.log('Auto-moving newly created Street View element:', node);
                                  node.style.position = 'absolute';
                                  node.style.zIndex = '1000';
                                  mapContainer.appendChild(node);

                                  // Position based on the requested position
                                  const pos = controlOptions.position || 'top-left';
                                  if (pos.includes('top')) {
                                    node.style.top = '10px';
                                    node.style.bottom = 'auto';
                                  } else {
                                    node.style.bottom = '10px';
                                    node.style.top = 'auto';
                                  }
                                  if (pos.includes('left')) {
                                    node.style.left = '10px';
                                    node.style.right = 'auto';
                                  } else {
                                    node.style.right = '10px';
                                    node.style.left = 'auto';
                                  }
                                }
                              }
                            }
                          });
                        });
                      });

                      observer.observe(document.body, {
                        childList: true,
                        subtree: true
                      });

                      // Store observer for cleanup
                      if (!el._streetViewObservers) {
                        el._streetViewObservers = new Map();
                      }
                      el._streetViewObservers.set(controlKey, observer);

                      console.log('Google Street View plugin restored successfully');
                    } catch (error) {
                      console.error('Failed to initialize Google Street View plugin:', error);
                      return;
                    }
                  } else {
                    console.warn('Google Street View plugin requires API key');
                    return;
                  }
                } else {
                  console.warn('MaplibreGoogleStreetView not available during restore');
                  return;
                }
                // Skip adding as regular control since it's a plugin
                return;
              case 'basemap_control':
                // Handle basemap control restoration
                if (window.MaplibreGLBasemapsControl) {
                  const basemapsOptions = {
                    basemaps: controlOptions.basemaps || [],
                    initialBasemap: controlOptions.initialBasemap,
                    expandDirection: controlOptions.expandDirection || 'down',
                    ...controlOptions
                  };
                  delete basemapsOptions.position; // Remove position from options passed to control

                  control = new window.MaplibreGLBasemapsControl(basemapsOptions);
                  console.log('Basemap control restored successfully');
                } else {
                  console.warn('MaplibreGLBasemapsControl not available during restore');
                  return;
                }
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

      // Set terrain if it exists
      const terrain = model.get("_terrain") || {};
      if (Object.keys(terrain).length > 0) {
        try {
          map.setTerrain(terrain);
          console.log('Terrain restored successfully:', terrain);
        } catch (error) {
          console.warn('Failed to restore terrain:', error);
        }
      }

      // Load existing draw data if present
      const drawData = model.get("_draw_data");
      if (el._drawControl && drawData && drawData.features && drawData.features.length > 0) {
        try {
          el._drawControl.set(drawData);
          console.log('Initial draw data loaded on widget initialization:', drawData);
        } catch (error) {
          console.error('Failed to load initial draw data:', error);
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

        // Mark map as ready
        el._mapReady = true;
        console.log('[DeckGL Debug] Map is now ready!');

        // Check if there are already calls in _js_calls that haven't been processed
        const existingCalls = model.get("_js_calls") || [];
        if (existingCalls.length > 0) {
          console.log(`[DeckGL Debug] Found ${existingCalls.length} existing calls in _js_calls, processing now`);
          existingCalls.forEach(call => {
            console.log(`[DeckGL Debug] Processing existing call: ${call.method}`);
            executeMapMethod(map, call, el);
          });
          // Clear them
          model.set("_js_calls", []);
          model.save_changes();
        }

        // Process any pending calls that came in before map was ready
        if (el._pendingCalls && el._pendingCalls.length > 0) {
          console.log(`[DeckGL Debug] Processing ${el._pendingCalls.length} pending calls after map load`);
          el._pendingCalls.forEach(call => {
            console.log(`[DeckGL Debug] Processing pending call: ${call.method}`);
            executeMapMethod(map, call, el);
          });
          el._pendingCalls = [];
        } else {
          console.log('[DeckGL Debug] No pending calls to process');
        }
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
      const clickData = {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat
      };

      // Update the clicked trait
      model.set("clicked", clickData);
      model.save_changes();

      // Also send as event for backwards compatibility
      sendEvent('click', {
        lngLat: [e.lngLat.lng, e.lngLat.lat],
        point: [e.point.x, e.point.y]
      });
    });

    map.on('moveend', () => {
      const center = map.getCenter();
      const bounds = map.getBounds();
      sendEvent('moveend', {
        center: [center.lng, center.lat],
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch(),
        bounds: [[bounds.getWest(), bounds.getSouth()], [bounds.getEast(), bounds.getNorth()]]
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
      map.setCenter(center); // [lng, lat] format
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

    // Listen for draw data changes from Python
    model.on("change:_draw_data", () => {
      const drawData = model.get("_draw_data");
      if (el._drawControl && drawData) {
        try {
          // Clear existing data first
          el._drawControl.deleteAll();

          // Load new data if it has features
          if (drawData.features && drawData.features.length > 0) {
            el._drawControl.set(drawData);
            console.log('Draw data updated from Python:', drawData);
          } else {
            console.log('Draw data cleared from Python');
          }
        } catch (error) {
          console.error('Failed to update draw data from Python:', error);
        }
      }
    });

    // Listen for Terra Draw data changes from Python
    model.on("change:_terra_draw_data", () => {
      const terraDrawData = model.get("_terra_draw_data");
      if (el._terraDrawControl && terraDrawData) {
        try {
          // Terra Draw data handling would need to be implemented based on the library's API
          console.log('Terra Draw data updated from Python:', terraDrawData);
        } catch (error) {
          console.error('Failed to update Terra Draw data from Python:', error);
        }
      }
    });

    // Handle JavaScript method calls from Python
    model.on("change:_js_calls", () => {
      const calls = model.get("_js_calls") || [];
      console.log(`[DeckGL Debug] Received ${calls.length} calls from Python. Map ready: ${el._mapReady}`);

      if (el._mapReady) {
        // Map is ready, execute calls immediately
        console.log('[DeckGL Debug] Map is ready, executing calls immediately');
        calls.forEach(call => {
          console.log(`[DeckGL Debug] Executing call: ${call.method}`);
          executeMapMethod(map, call, el);
        });
      } else {
        // Map not ready yet, queue the calls
        console.log(`[DeckGL Debug] Map not ready, queuing ${calls.length} calls`);
        el._pendingCalls.push(...calls);
        console.log(`[DeckGL Debug] Total pending calls: ${el._pendingCalls.length}`);
      }

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
            flyToOptions.center = [flyToOptions.center[1], flyToOptions.center[0]]; // [lat,lng] to [lng,lat]
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
            // bounds are already in [[lng,lat], [lng,lat]] format
            map.fitBounds(bounds, options || {});
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
              case 'layer_control':
                control = new LayerControl(controlOptions || {}, map, model);
                break;
              case 'geocoder':
                if (window.MaplibreGeocoder) {
                  const apiConfig = controlOptions.api_config || {};

                  // Create geocoder API implementation
                  const geocoderApi = {
                    forwardGeocode: async (config) => {
                      const features = [];
                      try {
                        const request = `${apiConfig.api_url || 'https://nominatim.openstreetmap.org/search'}?q=${config.query}&format=geojson&polygon_geojson=1&addressdetails=1&limit=${apiConfig.limit || 5}`;
                        const response = await fetch(request);
                        const geojson = await response.json();

                        for (const feature of geojson.features) {
                          const center = [
                            feature.bbox[0] + (feature.bbox[2] - feature.bbox[0]) / 2,
                            feature.bbox[1] + (feature.bbox[3] - feature.bbox[1]) / 2,
                          ];
                          const point = {
                            type: "Feature",
                            geometry: {
                              type: "Point",
                              coordinates: center,
                            },
                            place_name: feature.properties.display_name,
                            properties: feature.properties,
                            text: feature.properties.display_name,
                            place_type: ["place"],
                            center,
                          };
                          features.push(point);
                        }
                      } catch (e) {
                        console.error(`Failed to forwardGeocode with error: ${e}`);
                      }

                      return { features };
                    },
                  };

                  // Create geocoder control
                  const geocoderOptions = {
                    maplibregl: maplibregl,
                    placeholder: apiConfig.placeholder || 'Search for places...',
                    collapsed: controlOptions.collapsed !== false,
                    ...controlOptions
                  };
                  delete geocoderOptions.api_config; // Remove from options passed to geocoder
                  delete geocoderOptions.position; // Remove position from geocoder options

                  control = new window.MaplibreGeocoder(geocoderApi, geocoderOptions);
                  console.log('Geocoder control added successfully');
                } else {
                  console.warn('MaplibreGeocoder not available');
                  return;
                }
                break;
              case 'google_streetview':
                if (window.MaplibreGoogleStreetView) {
                  const apiKey = controlOptions.api_key;
                  if (apiKey) {
                    try {
                      const streetViewOptions = {
                        map: map,
                        apiKey: apiKey,
                        iframeOptions: {
                          allow: 'accelerometer; gyroscope; geolocation'
                        }
                      };

                      // Create the Street View plugin instance (not a control)
                      const streetViewPlugin = new window.MaplibreGoogleStreetView(streetViewOptions);

                      // Store the plugin instance for later management
                      if (!el._streetViewPlugins) {
                        el._streetViewPlugins = new Map();
                      }
                      el._streetViewPlugins.set(controlKey, streetViewPlugin);

                      // Force plugin elements to be contained within the map
                      const repositionStreetViewElements = () => {
                        try {
                          const mapContainer = map.getContainer();

                          // Find Street View elements using comprehensive selectors
                          const streetViewElements = document.querySelectorAll(
                            '[class*="streetview"], [class*="street-view"], [class*="pegman"], [class*="peg-man"], [class*="google-streetview"], [id*="streetview"], [id*="street-view"], [id*="pegman"]'
                          );

                          // Also check for any floating control-like elements
                          const allElements = Array.from(document.querySelectorAll('*'));
                          const floatingElements = allElements.filter(el => {
                            if (mapContainer.contains(el)) return false;
                            const style = window.getComputedStyle(el);
                            return (
                              (style.position === 'fixed' || style.position === 'absolute') &&
                              parseInt(style.zIndex) > 999 &&
                              el.offsetWidth > 0 && el.offsetHeight > 0 &&
                              el.offsetWidth < 100 && el.offsetHeight < 100
                            );
                          });

                          const allStreetViewElements = [...streetViewElements, ...floatingElements];

                          allStreetViewElements.forEach(element => {
                            if (!mapContainer.contains(element)) {
                              console.log('Moving Street View element into map container:', element);
                              element.style.position = 'absolute';
                              element.style.zIndex = '1000';
                              mapContainer.appendChild(element);

                              const pos = controlOptions.position || 'top-left';
                              if (pos.includes('top')) {
                                element.style.top = '10px';
                                element.style.bottom = 'auto';
                              } else {
                                element.style.bottom = '10px';
                                element.style.top = 'auto';
                              }
                              if (pos.includes('left')) {
                                element.style.left = '10px';
                                element.style.right = 'auto';
                              } else {
                                element.style.right = '10px';
                                element.style.left = 'auto';
                              }
                            }
                          });
                        } catch (error) {
                          console.warn('Failed to reposition Street View elements:', error);
                        }
                      };

                      setTimeout(repositionStreetViewElements, 100);
                      setTimeout(repositionStreetViewElements, 500);
                      setTimeout(repositionStreetViewElements, 1000);

                      // Add iframe permission fix using modern MutationObserver
                      const observer = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                          mutation.addedNodes.forEach(function(node) {
                            if (node.nodeType === 1) { // Element node
                              // Handle iframe permissions
                              if (node.tagName === 'IFRAME' &&
                                  (node.id === 'street-view-iframe' ||
                                   (node.parentNode && node.parentNode.id === 'street-view'))) {
                                node.setAttribute('allow', 'accelerometer; gyroscope; geolocation');
                              }

                              // Handle Street View control positioning - check multiple patterns
                              const isStreetViewElement = (
                                (node.className && (
                                  node.className.includes('streetview') ||
                                  node.className.includes('street-view') ||
                                  node.className.includes('google-streetview') ||
                                  node.className.includes('pegman') ||
                                  node.className.includes('peg-man')
                                )) ||
                                (node.id && (
                                  node.id.includes('streetview') ||
                                  node.id.includes('street-view') ||
                                  node.id.includes('pegman')
                                )) ||
                                // Check if it's a floating control-like element
                                (() => {
                                  try {
                                    const style = window.getComputedStyle(node);
                                    return (
                                      (style.position === 'fixed' || style.position === 'absolute') &&
                                      parseInt(style.zIndex) > 999 &&
                                      node.offsetWidth > 0 && node.offsetHeight > 0 &&
                                      node.offsetWidth < 100 && node.offsetHeight < 100
                                    );
                                  } catch (e) {
                                    return false;
                                  }
                                })()
                              );

                              if (isStreetViewElement) {
                                const mapContainer = map.getContainer();
                                if (!mapContainer.contains(node)) {
                                  console.log('Auto-moving newly created Street View element:', node);
                                  node.style.position = 'absolute';
                                  node.style.zIndex = '1000';
                                  mapContainer.appendChild(node);

                                  // Position based on the requested position
                                  const pos = controlOptions.position || 'top-left';
                                  if (pos.includes('top')) {
                                    node.style.top = '10px';
                                    node.style.bottom = 'auto';
                                  } else {
                                    node.style.bottom = '10px';
                                    node.style.top = 'auto';
                                  }
                                  if (pos.includes('left')) {
                                    node.style.left = '10px';
                                    node.style.right = 'auto';
                                  } else {
                                    node.style.right = '10px';
                                    node.style.left = 'auto';
                                  }
                                }
                              }
                            }
                          });
                        });
                      });

                      observer.observe(document.body, {
                        childList: true,
                        subtree: true
                      });

                      // Store observer for cleanup
                      if (!el._streetViewObservers) {
                        el._streetViewObservers = new Map();
                      }
                      el._streetViewObservers.set(controlKey, observer);

                      console.log('Google Street View plugin added successfully');

                      // Skip the normal control addition process since this is a plugin
                      return;
                    } catch (error) {
                      console.error('Failed to initialize Google Street View plugin:', error);
                      return;
                    }
                  } else {
                    console.warn('Google Street View plugin requires API key');
                    return;
                  }
                } else {
                  console.warn('MaplibreGoogleStreetView not available');
                  return;
                }
                break;
              case 'basemap_control':
                if (window.MaplibreGLBasemapsControl) {
                  const basemapsOptions = {
                    basemaps: controlOptions.basemaps || [],
                    initialBasemap: controlOptions.initialBasemap,
                    expandDirection: controlOptions.expandDirection || 'down',
                    ...controlOptions
                  };
                  delete basemapsOptions.position; // Remove position from options passed to control

                  control = new window.MaplibreGLBasemapsControl(basemapsOptions);
                  console.log('Basemap control added successfully');
                } else {
                  console.warn('MaplibreGLBasemapsControl not available');
                  return;
                }
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

            // Handle Street View plugin removal
            if (removeControlType === 'google_streetview') {
              if (el._streetViewPlugins && el._streetViewPlugins.has(removeControlKey)) {
                // Clean up the plugin
                el._streetViewPlugins.delete(removeControlKey);

                // Clean up observers
                if (el._streetViewObservers && el._streetViewObservers.has(removeControlKey)) {
                  const observer = el._streetViewObservers.get(removeControlKey);
                  observer.disconnect();
                  el._streetViewObservers.delete(removeControlKey);
                }

                // Clean up handlers
                if (el._streetViewHandlers && el._streetViewHandlers.has(removeControlKey)) {
                  el._streetViewHandlers.delete(removeControlKey);
                }

                console.log(`Google Street View plugin ${removeControlKey} removed`);
              } else {
                console.warn(`Google Street View plugin ${removeControlKey} not found`);
              }
            } else {
              // Handle regular controls
              if (el._controls.has(removeControlKey)) {
                const controlToRemove = el._controls.get(removeControlKey);
                map.removeControl(controlToRemove);
                el._controls.delete(removeControlKey);
              } else {
                console.warn(`Control ${removeControlType} at position ${removePosition} not found`);
              }
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

          case 'setTerrain':
            const [terrainConfig] = args;
            try {
              map.setTerrain(terrainConfig);
              console.log('Terrain set successfully:', terrainConfig);
            } catch (error) {
              console.warn('Failed to set terrain:', error);
            }
            break;

          case 'addDrawControl':
            const [drawOptions] = args;
            try {
              if (window.MapboxDraw && !el._drawControl) {
                // Use custom styles if provided, otherwise use MapLibre compatibility styles
                const customStyles = drawOptions.customStyles;
                const finalDrawOptions = {
                  ...drawOptions,
                  styles: customStyles || window.MapLibreDrawStyles || undefined
                };
                el._drawControl = new window.MapboxDraw(finalDrawOptions);
                map.addControl(el._drawControl, drawOptions.position || 'top-left');

                // Track selection state for preserving selection during updates
                let lastSelectedFeatureIds = [];
                let preserveSelectionOnNextChange = false;
                const preserveSelectionOnEdit = drawOptions.preserveSelectionOnEdit !== false;

                // Set up draw event handlers with data sync
                map.on('draw.create', (e) => {
                  const allData = el._drawControl.getAll();
                  model.set('_draw_data', allData);
                  model.save_changes();
                  sendEvent('draw.create', { features: e.features, allData: allData });
                });

                map.on('draw.update', (e) => {
                  // Store selected feature IDs before update to preserve selection
                  if (preserveSelectionOnEdit) {
                    const selectedFeatures = el._drawControl.getSelected().features;
                    if (selectedFeatures.length > 0) {
                      lastSelectedFeatureIds = selectedFeatures.map(f => f.id);
                      preserveSelectionOnNextChange = true;

                      // Re-select the features after a short delay to ensure the update completes
                      setTimeout(() => {
                        if (preserveSelectionOnNextChange && lastSelectedFeatureIds.length > 0) {
                          try {
                            // Check if features still exist before re-selecting
                            const allFeatures = el._drawControl.getAll().features;
                            const validIds = lastSelectedFeatureIds.filter(id =>
                              allFeatures.some(f => f.id === id)
                            );

                            if (validIds.length > 0) {
                              el._drawControl.changeMode('simple_select', { featureIds: validIds });
                            }
                          } catch (err) {
                            console.warn('Failed to restore selection after update:', err);
                          }
                          preserveSelectionOnNextChange = false;
                        }
                      }, 10);
                    }
                  }

                  const allData = el._drawControl.getAll();
                  model.set('_draw_data', allData);
                  model.save_changes();
                  sendEvent('draw.update', { features: e.features, allData: allData });
                });

                map.on('draw.delete', (e) => {
                  const allData = el._drawControl.getAll();
                  model.set('_draw_data', allData);
                  model.save_changes();
                  sendEvent('draw.delete', { features: e.features, allData: allData });
                });

                map.on('draw.selectionchange', (e) => {
                  // Don't update tracking if we're in the middle of preserving selection
                  if (!preserveSelectionOnNextChange) {
                    lastSelectedFeatureIds = e.features.map(f => f.id);
                  }
                  sendEvent('draw.selectionchange', { features: e.features });
                });

                console.log('Draw control added successfully with custom styles');
              } else {
                console.warn('MapboxDraw not available or already added');
              }
            } catch (error) {
              console.error('Failed to add draw control:', error);
            }
            break;

          case 'loadDrawData':
            const [geojsonData] = args;
            try {
              if (el._drawControl) {
                // Clear existing data first
                el._drawControl.deleteAll();
                // Add new data
                el._drawControl.set(geojsonData);

                // Immediately sync the loaded data back to Python
                const loadedData = el._drawControl.getAll();
                model.set('_draw_data', loadedData);
                model.save_changes();

                console.log('Draw data loaded and synced successfully', loadedData);

                // Send event to notify successful loading
                sendEvent('draw_data_loaded', { data: loadedData });
              } else {
                console.warn('Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to load draw data:', error);
            }
            break;

          case 'addDrawData':
            const [geojsonDataToAdd] = args;
            try {
              if (el._drawControl) {
                // Add features without clearing existing ones
                if (geojsonDataToAdd && geojsonDataToAdd.type === 'FeatureCollection' && geojsonDataToAdd.features) {
                  geojsonDataToAdd.features.forEach(feature => {
                    el._drawControl.add(feature);
                  });
                } else if (geojsonDataToAdd && geojsonDataToAdd.type === 'Feature') {
                  el._drawControl.add(geojsonDataToAdd);
                }

                // Immediately sync the updated data back to Python
                const updatedData = el._drawControl.getAll();
                model.set('_draw_data', updatedData);
                model.save_changes();

                console.log('Draw data added and synced successfully', updatedData);

                // Send event to notify successful addition
                sendEvent('draw_data_added', { data: updatedData });
              } else {
                console.warn('Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to add draw data:', error);
            }
            break;

          case 'getDrawData':
            try {
              if (el._drawControl) {
                const drawData = el._drawControl.getAll();
                model.set('_draw_data', drawData);
                model.save_changes();
                console.log('Draw data retrieved successfully', drawData);
                // Also send as event for immediate response
                sendEvent('draw_data_retrieved', { data: drawData });
              } else {
                console.warn('Draw control not initialized');
                // Send empty data if control not initialized
                model.set('_draw_data', { type: 'FeatureCollection', features: [] });
                model.save_changes();
              }
            } catch (error) {
              console.error('Failed to get draw data:', error);
              // Send empty data on error
              model.set('_draw_data', { type: 'FeatureCollection', features: [] });
              model.save_changes();
            }
            break;

          case 'clearDrawData':
            try {
              if (el._drawControl) {
                el._drawControl.deleteAll();

                // Sync the cleared state back to Python
                const emptyData = { type: 'FeatureCollection', features: [] };
                model.set('_draw_data', emptyData);
                model.save_changes();

                console.log('Draw data cleared successfully');
                sendEvent('draw_data_cleared', { data: emptyData });
              } else {
                console.warn('Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to clear draw data:', error);
            }
            break;

          case 'deleteDrawFeatures':
            const [featureIds] = args;
            try {
              if (el._drawControl) {
                el._drawControl.delete(featureIds);
                console.log('Draw features deleted successfully');
              } else {
                console.warn('Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to delete draw features:', error);
            }
            break;

          case 'setDrawMode':
            const [mode] = args;
            try {
              if (el._drawControl) {
                el._drawControl.changeMode(mode);
                console.log(`Draw mode changed to: ${mode}`);
              } else {
                console.warn('Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to set draw mode:', error);
            }
            break;

          case 'addTerraDrawControl':
            const [terraDrawOptions] = args;
            try {
              if (window.MaplibreTerradrawControl && !el._terraDrawControl) {
                el._terraDrawControl = new window.MaplibreTerradrawControl.MaplibreTerradrawControl(terraDrawOptions);
                map.addControl(el._terraDrawControl, terraDrawOptions.position || 'top-left');

                // Set up Terra Draw event handlers to sync data changes
                const terraDrawInstance = el._terraDrawControl.getTerraDrawInstance();
                if (terraDrawInstance) {
                  // Listen for Terra Draw events and sync data
                  terraDrawInstance.on('finish', () => {
                    try {
                      const currentData = terraDrawInstance.getSnapshot();
                      model.set('_terra_draw_data', currentData);
                      model.save_changes();
                      console.log('Terra Draw data auto-synced after finish event');
                    } catch (error) {
                      console.error('Failed to sync Terra Draw data after finish event:', error);
                    }
                  });

                  terraDrawInstance.on('change', () => {
                    try {
                      const currentData = terraDrawInstance.getSnapshot();
                      model.set('_terra_draw_data', currentData);
                      model.save_changes();
                      console.log('Terra Draw data auto-synced after change event');
                    } catch (error) {
                      console.error('Failed to sync Terra Draw data after change event:', error);
                    }
                  });
                }

                console.log('Terra Draw control added successfully');
              } else {
                console.warn('MaplibreTerradrawControl not available or already added');
              }
            } catch (error) {
              console.error('Failed to add Terra Draw control:', error);
            }
            break;

          case 'loadTerraDrawData':
            const [terraGeojsonData] = args;
            try {
              if (el._terraDrawControl) {
                // Get the Terra Draw instance from the control
                const terraDrawInstance = el._terraDrawControl.getTerraDrawInstance();
                if (terraDrawInstance) {
                  // Try different possible method names for loading data
                  let loaded = false;

                  // Try addFeatures() first (most common)
                  if (typeof terraDrawInstance.addFeatures === 'function' && terraGeojsonData.features) {
                    terraDrawInstance.addFeatures(terraGeojsonData.features);
                    loaded = true;
                    console.log('Terra Draw data loaded via addFeatures():', terraGeojsonData);
                  }
                  // Try setFeatures() as alternative
                  else if (typeof terraDrawInstance.setFeatures === 'function' && terraGeojsonData.features) {
                    terraDrawInstance.setFeatures(terraGeojsonData.features);
                    loaded = true;
                    console.log('Terra Draw data loaded via setFeatures():', terraGeojsonData);
                  }
                  // Try loadFeatures() as alternative
                  else if (typeof terraDrawInstance.loadFeatures === 'function' && terraGeojsonData.features) {
                    terraDrawInstance.loadFeatures(terraGeojsonData.features);
                    loaded = true;
                    console.log('Terra Draw data loaded via loadFeatures():', terraGeojsonData);
                  }
                  // Try setGeoJSON() as alternative
                  else if (typeof terraDrawInstance.setGeoJSON === 'function') {
                    terraDrawInstance.setGeoJSON(terraGeojsonData);
                    loaded = true;
                    console.log('Terra Draw data loaded via setGeoJSON():', terraGeojsonData);
                  }
                  // Try to access store/data property directly
                  else if (terraDrawInstance.store && typeof terraDrawInstance.store.addFeatures === 'function' && terraGeojsonData.features) {
                    terraDrawInstance.store.addFeatures(terraGeojsonData.features);
                    loaded = true;
                    console.log('Terra Draw data loaded via store.addFeatures():', terraGeojsonData);
                  }

                  if (loaded) {
                    // Sync the loaded data back to Python
                    model.set('_terra_draw_data', terraGeojsonData);
                    model.save_changes();
                    sendEvent('terra_draw_data_loaded', { data: terraGeojsonData });
                  } else {
                    console.warn('No load method found on Terra Draw instance');
                  }
                } else {
                  console.warn('Could not get Terra Draw instance');
                }
              } else {
                console.warn('Terra Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to load Terra Draw data:', error);
            }
            break;

          case 'getTerraDrawData':
            try {
              if (el._terraDrawControl) {
                // Get the Terra Draw instance from the control
                const terraDrawInstance = el._terraDrawControl.getTerraDrawInstance();
                if (terraDrawInstance) {
                  // Try different possible method names for getting data
                  let terraDrawData = { type: 'FeatureCollection', features: [] };

                  // Try getSnapshot() first
                  if (typeof terraDrawInstance.getSnapshot === 'function') {
                    terraDrawData = terraDrawInstance.getSnapshot();
                    console.log('Terra Draw data retrieved via getSnapshot():', terraDrawData);
                  }
                  // Try getFeatures() as alternative
                  else if (typeof terraDrawInstance.getFeatures === 'function') {
                    const features = terraDrawInstance.getFeatures();
                    terraDrawData = { type: 'FeatureCollection', features: features };
                    console.log('Terra Draw data retrieved via getFeatures():', terraDrawData);
                  }
                  // Try getAllFeatures() as alternative
                  else if (typeof terraDrawInstance.getAllFeatures === 'function') {
                    const features = terraDrawInstance.getAllFeatures();
                    terraDrawData = { type: 'FeatureCollection', features: features };
                    console.log('Terra Draw data retrieved via getAllFeatures():', terraDrawData);
                  }
                  // Try getGeoJSON() as alternative
                  else if (typeof terraDrawInstance.getGeoJSON === 'function') {
                    terraDrawData = terraDrawInstance.getGeoJSON();
                    console.log('Terra Draw data retrieved via getGeoJSON():', terraDrawData);
                  }
                  // Try to access store/data property directly
                  else if (terraDrawInstance.store && typeof terraDrawInstance.store.getFeatures === 'function') {
                    const features = terraDrawInstance.store.getFeatures();
                    terraDrawData = { type: 'FeatureCollection', features: features };
                    console.log('Terra Draw data retrieved via store.getFeatures():', terraDrawData);
                  }
                  // Debug: log available methods
                  else {
                    console.log('Available Terra Draw instance methods:', Object.getOwnPropertyNames(terraDrawInstance));
                    console.log('Terra Draw instance proto:', Object.getOwnPropertyNames(Object.getPrototypeOf(terraDrawInstance)));
                  }

                  model.set('_terra_draw_data', terraDrawData);
                  model.save_changes();
                  sendEvent('terra_draw_data_retrieved', { data: terraDrawData });
                } else {
                  console.warn('Could not get Terra Draw instance');
                  model.set('_terra_draw_data', { type: 'FeatureCollection', features: [] });
                  model.save_changes();
                }
              } else {
                console.warn('Terra Draw control not initialized');
                model.set('_terra_draw_data', { type: 'FeatureCollection', features: [] });
                model.save_changes();
              }
            } catch (error) {
              console.error('Failed to get Terra Draw data:', error);
              model.set('_terra_draw_data', { type: 'FeatureCollection', features: [] });
              model.save_changes();
            }
            break;

          case 'clearTerraDrawData':
            try {
              if (el._terraDrawControl) {
                // Get the Terra Draw instance from the control
                const terraDrawInstance = el._terraDrawControl.getTerraDrawInstance();
                if (terraDrawInstance) {
                  // Try different possible method names for clearing data
                  let cleared = false;

                  // Try clear() first
                  if (typeof terraDrawInstance.clear === 'function') {
                    terraDrawInstance.clear();
                    cleared = true;
                    console.log('Terra Draw data cleared via clear()');
                  }
                  // Try clearAll() as alternative
                  else if (typeof terraDrawInstance.clearAll === 'function') {
                    terraDrawInstance.clearAll();
                    cleared = true;
                    console.log('Terra Draw data cleared via clearAll()');
                  }
                  // Try deleteAll() as alternative
                  else if (typeof terraDrawInstance.deleteAll === 'function') {
                    terraDrawInstance.deleteAll();
                    cleared = true;
                    console.log('Terra Draw data cleared via deleteAll()');
                  }
                  // Try removeAll() as alternative
                  else if (typeof terraDrawInstance.removeAll === 'function') {
                    terraDrawInstance.removeAll();
                    cleared = true;
                    console.log('Terra Draw data cleared via removeAll()');
                  }
                  // Try to access store/data property directly
                  else if (terraDrawInstance.store && typeof terraDrawInstance.store.clear === 'function') {
                    terraDrawInstance.store.clear();
                    cleared = true;
                    console.log('Terra Draw data cleared via store.clear()');
                  }

                  if (cleared) {
                    const emptyData = { type: 'FeatureCollection', features: [] };
                    model.set('_terra_draw_data', emptyData);
                    model.save_changes();
                    sendEvent('terra_draw_data_cleared', { data: emptyData });
                  } else {
                    console.warn('No clear method found on Terra Draw instance');
                  }
                } else {
                  console.warn('Could not get Terra Draw instance');
                }
              } else {
                console.warn('Terra Draw control not initialized');
              }
            } catch (error) {
              console.error('Failed to clear Terra Draw data:', error);
            }
            break;

          case 'addDeckGLLayer':
            const deckLayerConfig = args[0];
            try {
              // Check if DeckGL is available
              if (typeof window.deck === 'undefined') {
                console.error('DeckGL not loaded yet. Waiting for loadProtocols to complete...');
                // Retry after a short delay
                setTimeout(() => {
                  executeMapMethod(map, call, el);
                }, 100);
                break;
              }

              // Initialize DeckGL overlay if not exists
              if (!el._deckglOverlay) {
                el._deckglOverlay = new window.deck.MapboxOverlay({
                  layers: []
                });
                map.addControl(el._deckglOverlay);
                el._deckglLayers = new Map();
              }

              // Create DeckGL layer
              const LayerClass = window.deck[deckLayerConfig.type];
              if (!LayerClass) {
                console.error(`Unknown DeckGL layer type: ${deckLayerConfig.type}`);
                break;
              }

              // Process props to convert string accessors to functions
              const processedProps = processDeckGLProps(deckLayerConfig.props);

              // Add LASLoader for PointCloudLayer if loaders.gl is available
              const layerOptions = {
                id: deckLayerConfig.id,
                data: deckLayerConfig.data,
                visible: deckLayerConfig.visible !== false,
                ...processedProps
              };

              // If this is a PointCloudLayer, add LASLoader if available
              if (deckLayerConfig.type === 'PointCloudLayer') {
                if (window._loadersGLLASLoader) {
                  layerOptions.loaders = [window._loadersGLLASLoader];
                  // Add fp64 support for LAZ files to fix floating point precision issues
                  // This is critical for proper 3D elevation rendering with LNGLAT coordinates
                  if (!layerOptions.loadOptions) {
                    layerOptions.loadOptions = {};
                  }
                  if (!layerOptions.loadOptions.las) {
                    layerOptions.loadOptions.las = {};
                  }
                  layerOptions.loadOptions.las.fp64 = true;
                  console.log('✓ Added LASLoader to PointCloudLayer with fp64 precision (from ESM)');
                } else {
                  console.warn('⚠ LASLoader not available, LAZ files may not load');
                }
              }

              const deckLayer = new LayerClass(layerOptions);

              // Store layer reference
              el._deckglLayers.set(deckLayerConfig.id, deckLayer);

              // Update overlay with new layers
              const allLayers = Array.from(el._deckglLayers.values());
              el._deckglOverlay.setProps({ layers: allLayers });

              console.log(`Added DeckGL layer: ${deckLayerConfig.id}`);
            } catch (error) {
              console.error('Failed to add DeckGL layer:', error);
            }
            break;

          case 'removeDeckGLLayer':
            const deckRemoveLayerId = args[0];
            try {
              if (el._deckglLayers && el._deckglLayers.has(deckRemoveLayerId)) {
                el._deckglLayers.delete(deckRemoveLayerId);

                // Update overlay with remaining layers
                if (el._deckglOverlay) {
                  const allLayers = Array.from(el._deckglLayers.values());
                  el._deckglOverlay.setProps({ layers: allLayers });
                }

                console.log(`Removed DeckGL layer: ${deckRemoveLayerId}`);
              }
            } catch (error) {
              console.error('Failed to remove DeckGL layer:', error);
            }
            break;

          case 'updateDeckGLLayer':
            const updateLayerConfig = args[0];
            try {
              if (el._deckglLayers && el._deckglLayers.has(updateLayerConfig.id)) {
                // Create updated layer
                const LayerClass = window.deck[updateLayerConfig.type];
                if (!LayerClass) {
                  console.error(`Unknown DeckGL layer type: ${updateLayerConfig.type}`);
                  break;
                }

                // Process props to convert string accessors to functions
                const processedProps = processDeckGLProps(updateLayerConfig.props);

                // Add LASLoader for PointCloudLayer if loaders.gl is available
                const layerOptions = {
                  id: updateLayerConfig.id,
                  data: updateLayerConfig.data,
                  visible: updateLayerConfig.visible !== false,
                  ...processedProps
                };

                // If this is a PointCloudLayer, add LASLoader if available
                if (updateLayerConfig.type === 'PointCloudLayer') {
                  if (window._loadersGLLASLoader) {
                    layerOptions.loaders = [window._loadersGLLASLoader];
                    // Add fp64 support for LAZ files to fix floating point precision issues
                    // This is critical for proper 3D elevation rendering with LNGLAT coordinates
                    if (!layerOptions.loadOptions) {
                      layerOptions.loadOptions = {};
                    }
                    if (!layerOptions.loadOptions.las) {
                      layerOptions.loadOptions.las = {};
                    }
                    layerOptions.loadOptions.las.fp64 = true;
                    console.log('✓ Added LASLoader to PointCloudLayer with fp64 precision (update, from ESM)');
                  }
                }

                const updatedLayer = new LayerClass(layerOptions);

                // Replace layer
                el._deckglLayers.set(updateLayerConfig.id, updatedLayer);

                // Update overlay
                if (el._deckglOverlay) {
                  const allLayers = Array.from(el._deckglLayers.values());
                  el._deckglOverlay.setProps({ layers: allLayers });
                }

                console.log(`Updated DeckGL layer: ${updateLayerConfig.id}`);
              }
            } catch (error) {
              console.error('Failed to update DeckGL layer:', error);
            }
            break;

          case 'setDeckGLLayerVisibility':
            const [visLayerId, visible] = args;
            try {
              if (el._deckglLayers && el._deckglLayers.has(visLayerId)) {
                const layer = el._deckglLayers.get(visLayerId);
                const updatedLayer = layer.clone({ visible });
                el._deckglLayers.set(visLayerId, updatedLayer);

                // Update overlay
                if (el._deckglOverlay) {
                  const allLayers = Array.from(el._deckglLayers.values());
                  el._deckglOverlay.setProps({ layers: allLayers });
                }

                console.log(`Set DeckGL layer ${visLayerId} visibility: ${visible}`);
              }
            } catch (error) {
              console.error('Failed to set DeckGL layer visibility:', error);
            }
            break;

          case 'clearDeckGLLayers':
            try {
              if (el._deckglLayers) {
                el._deckglLayers.clear();

                // Update overlay with empty layers
                if (el._deckglOverlay) {
                  el._deckglOverlay.setProps({ layers: [] });
                }

                console.log('Cleared all DeckGL layers');
              }
            } catch (error) {
              console.error('Failed to clear DeckGL layers:', error);
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
      if (el._drawControl) {
        el._drawControl = null;
      }
      if (el._terraDrawControl) {
        el._terraDrawControl = null;
      }
      if (el._deckglOverlay) {
        try {
          map.removeControl(el._deckglOverlay);
        } catch (e) {
          console.warn('Failed to remove DeckGL overlay:', e);
        }
        el._deckglOverlay = null;
      }
      if (el._deckglLayers) {
        el._deckglLayers.clear();
        el._deckglLayers = null;
      }
      if (el._streetViewPlugins) {
        el._streetViewPlugins.clear();
      }
      if (el._streetViewObservers) {
        el._streetViewObservers.forEach(observer => observer.disconnect());
        el._streetViewObservers.clear();
      }
      if (el._streetViewHandlers) {
        el._streetViewHandlers.clear();
      }
      if (el._map) {
        el._map.remove();
        el._map = null;
      }
    };

  }); // End of loadProtocols().then()
}

export default { render };