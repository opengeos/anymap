// Load Cesium library from CDN
function loadCesium() {
  return new Promise((resolve, reject) => {
    // Check if Cesium is already loaded
    if (window.Cesium) {
      resolve();
      return;
    }

    // Check if script is already being loaded
    const existingScript = document.head.querySelector('script[src*="Cesium.js"]');
    if (existingScript) {
      existingScript.addEventListener('load', resolve);
      existingScript.addEventListener('error', reject);
      return;
    }

    // Create and load the script
    const script = document.createElement('script');
    script.src = 'https://cesium.com/downloads/cesiumjs/releases/1.131/Build/Cesium/Cesium.js';
    script.async = false;
    script.addEventListener('load', resolve);
    script.addEventListener('error', reject);
    document.head.appendChild(script);
  });
}

function render({ model, el }) {
  // Create unique ID for this widget instance
  const widgetId = `anymap-cesium-${Math.random().toString(36).substr(2, 9)}`;

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
  if (el._viewer) {
    el._viewer.destroy();
    el._viewer = null;
  }
  if (el._entities) {
    el._entities = [];
  }

  el.innerHTML = "";
  el.appendChild(container);

  // Show loading indicator
  const loadingDiv = document.createElement("div");
  loadingDiv.className = "anymap-cesium-loading";
  loadingDiv.textContent = "Loading Cesium...";
  container.appendChild(loadingDiv);

  // Load Cesium and initialize when ready
  loadCesium().then(() => {
    initializeCesium();
  }).catch((error) => {
    console.error("Failed to load Cesium:", error);
    loadingDiv.textContent = "Failed to load Cesium library";
    loadingDiv.style.color = "red";
  });

  // Function to initialize Cesium when library is ready
  function initializeCesium() {
    if (!window.Cesium) {
      console.error("Cesium library not loaded");
      return;
    }

    // Remove loading indicator
    if (loadingDiv.parentNode) {
      loadingDiv.parentNode.removeChild(loadingDiv);
    }

    // Set Cesium ion access token
    const accessToken = model.get("access_token");
    if (accessToken) {
      window.Cesium.Ion.defaultAccessToken = accessToken;
    }

    // Get configuration options
    const viewerOptions = {
      baseLayerPicker: model.get("base_layer_picker") !== false,
      fullscreenButton: model.get("fullscreen_button") !== false,
      vrButton: model.get("vr_button") !== false,
      geocoder: model.get("geocoder") !== false,
      homeButton: model.get("home_button") !== false,
      infoBox: model.get("info_box") !== false,
      sceneModePicker: model.get("scene_mode_picker") !== false,
      selectionIndicator: model.get("selection_indicator") !== false,
      timeline: model.get("timeline") !== false,
      navigationHelpButton: false, // Disable navigation help to prevent arrows
      navigationInstructionsInitiallyVisible: false,
      animation: model.get("animation") !== false,
      shouldAnimate: model.get("should_animate") !== false,
      clockViewModel: undefined,
      selectedImageryProviderViewModel: undefined,
      imageryProviderViewModels: window.Cesium.createDefaultImageryProviderViewModels(),
      selectedTerrainProviderViewModel: undefined,
      terrainProviderViewModels: window.Cesium.createDefaultTerrainProviderViewModels(),
      skyBox: undefined,
      skyAtmosphere: undefined,
      fullscreenElement: document.body,
      useDefaultRenderLoop: true,
      targetFrameRate: undefined,
      showRenderLoopErrors: true,
      useBrowserRecommendedResolution: true,
      automaticallyTrackDataSourceClocks: true,
      contextOptions: undefined,
      sceneMode: window.Cesium.SceneMode.SCENE3D,
      mapProjection: new window.Cesium.WebMercatorProjection(),
      dataSources: new window.Cesium.DataSourceCollection()
    };

    // Initialize Cesium viewer
    const viewer = new window.Cesium.Viewer(container, viewerOptions);

    // Disable navigation help overlay completely
    if (viewer.cesiumWidget.scene && viewer.cesiumWidget.scene.screenSpaceCameraController) {
      viewer.cesiumWidget.scene.screenSpaceCameraController.enableRotate = true;
      viewer.cesiumWidget.scene.screenSpaceCameraController.enableTranslate = true;
      viewer.cesiumWidget.scene.screenSpaceCameraController.enableZoom = true;
      viewer.cesiumWidget.scene.screenSpaceCameraController.enableTilt = true;
      viewer.cesiumWidget.scene.screenSpaceCameraController.enableLook = true;
    }

    // Aggressively hide all navigation help elements
    const hideNavigationHelp = () => {
      // Hide all possible navigation help selectors
      const selectors = [
        '.cesium-navigation-help',
        '.cesium-navigation-help-pan',
        '.cesium-navigation-help-zoom',
        '.cesium-navigation-help-rotate',
        '.cesium-navigation-help-tilt',
        '.cesium-navigation-help-instructions',
        '.cesium-viewer-navigationHelpButton-wrapper',
        '.cesium-navigation-help-button',
        '.cesium-click-navigation-help',
        '.cesium-touch-navigation-help',
        '[class*="navigation-help"]',
        '[class*="cesium-navigation"]'
      ];

      selectors.forEach(selector => {
        const elements = container.querySelectorAll(selector);
        elements.forEach(el => {
          el.style.display = 'none';
          el.style.visibility = 'hidden';
          el.style.opacity = '0';
          el.style.pointerEvents = 'none';
          el.style.zIndex = '-1000';
          el.remove();
        });
      });

      // Also check document body for any navigation help overlays
      document.querySelectorAll('[class*="cesium-navigation"]').forEach(el => {
        if (el.style) {
          el.style.display = 'none';
          el.style.visibility = 'hidden';
        }
      });

      // Ensure canvas gets focus for mouse events
      const canvas = container.querySelector('canvas');
      if (canvas) {
        canvas.style.outline = 'none';
        canvas.setAttribute('tabindex', '0');
        canvas.style.pointerEvents = 'auto';
        canvas.style.touchAction = 'none';
      }
    };

    // Run immediately and then with timeouts to catch delayed elements
    hideNavigationHelp();
    setTimeout(hideNavigationHelp, 100);
    setTimeout(hideNavigationHelp, 500);
    setTimeout(hideNavigationHelp, 1000);

    // Set up mutation observer to catch dynamically added navigation help elements
    if (window.MutationObserver) {
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // Element node
              const className = node.className || '';
              if (typeof className === 'string' && className.includes('navigation-help')) {
                hideNavigationHelp();
              }
            }
          });
        });
      });

      observer.observe(container, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
      });

      // Store observer for cleanup
      el._navigationObserver = observer;
    }

    // Store viewer instance for cleanup
    el._viewer = viewer;
    el._entities = [];
    el._widgetId = widgetId;

    // Set initial camera position
    const center = model.get("center");
    const zoom = model.get("zoom");
    const height = model.get("camera_height") || 10000000; // Default 10M meters

    if (center && center.length >= 2) {
      viewer.camera.setView({
        destination: window.Cesium.Cartesian3.fromDegrees(center[1], center[0], height),
        orientation: {
          heading: window.Cesium.Math.toRadians(model.get("heading") || 0),
          pitch: window.Cesium.Math.toRadians(model.get("pitch") || -90),
          roll: window.Cesium.Math.toRadians(model.get("roll") || 0)
        }
      });
    }

    // Handle map events and send to Python
    const sendEvent = (eventType, eventData) => {
      const currentEvents = model.get("_js_events") || [];
      const newEvents = [...currentEvents, { type: eventType, ...eventData }];
      model.set("_js_events", newEvents);
      model.save_changes();
    };

    // Map event handlers
    viewer.cesiumWidget.screenSpaceEventHandler.setInputAction((event) => {
      const pickedObject = viewer.scene.pick(event.position);
      const cartesian = viewer.camera.pickEllipsoid(event.position, viewer.scene.globe.ellipsoid);

      if (cartesian) {
        const cartographic = window.Cesium.Cartographic.fromCartesian(cartesian);
        const longitude = window.Cesium.Math.toDegrees(cartographic.longitude);
        const latitude = window.Cesium.Math.toDegrees(cartographic.latitude);

        sendEvent('click', {
          longitude: longitude,
          latitude: latitude,
          height: cartographic.height,
          pickedObject: pickedObject ? pickedObject.id : null
        });
      }
    }, window.Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Camera move event
    viewer.camera.moveEnd.addEventListener(() => {
      const center = viewer.camera.positionCartographic;
      sendEvent('moveend', {
        longitude: window.Cesium.Math.toDegrees(center.longitude),
        latitude: window.Cesium.Math.toDegrees(center.latitude),
        height: center.height,
        heading: window.Cesium.Math.toDegrees(viewer.camera.heading),
        pitch: window.Cesium.Math.toDegrees(viewer.camera.pitch),
        roll: window.Cesium.Math.toDegrees(viewer.camera.roll)
      });
    });

    // Listen for trait changes from Python
    model.on("change:center", () => {
      const newCenter = model.get("center");
      if (newCenter && newCenter.length >= 2) {
        viewer.camera.setView({
          destination: window.Cesium.Cartesian3.fromDegrees(newCenter[1], newCenter[0], height)
        });
      }
    });

    model.on("change:access_token", () => {
      const newToken = model.get("access_token");
      if (newToken) {
        window.Cesium.Ion.defaultAccessToken = newToken;
      }
    });

    // Handle JavaScript method calls from Python
    model.on("change:_js_calls", () => {
      const calls = model.get("_js_calls") || [];
      calls.forEach(call => {
        executeCesiumMethod(viewer, call, el, sendEvent);
      });
      // Clear the calls after processing
      model.set("_js_calls", []);
      model.save_changes();
    });
  }

  // Method execution function
  function executeCesiumMethod(viewer, call, el, sendEvent) {
    const { method, args, kwargs } = call;

    try {
      switch (method) {
        case 'flyTo':
          const flyToOptions = args[0] || {};
          if (flyToOptions.longitude !== undefined && flyToOptions.latitude !== undefined) {
            const destination = window.Cesium.Cartesian3.fromDegrees(
              flyToOptions.longitude,
              flyToOptions.latitude,
              flyToOptions.height || 10000000
            );

            const flyToConfig = {
              destination: destination,
              duration: flyToOptions.duration || 3.0
            };

            if (flyToOptions.heading !== undefined || flyToOptions.pitch !== undefined || flyToOptions.roll !== undefined) {
              flyToConfig.orientation = {
                heading: window.Cesium.Math.toRadians(flyToOptions.heading || 0),
                pitch: window.Cesium.Math.toRadians(flyToOptions.pitch || -90),
                roll: window.Cesium.Math.toRadians(flyToOptions.roll || 0)
              };
            }

            viewer.camera.flyTo(flyToConfig);
          }
          break;

        case 'addEntity':
          const entityConfig = args[0];

          // Convert point color from string or array to Cesium.Color
          if (entityConfig.point) {
              if (typeof entityConfig.point.color === 'string') {
                  entityConfig.point.color = Cesium.Color.fromCssColorString(entityConfig.point.color);
              } else if (Array.isArray(entityConfig.point.color)) {
                  entityConfig.point.color = new Cesium.Color(...entityConfig.point.color);
              }

              if (typeof entityConfig.point.outlineColor === 'string') {
                  entityConfig.point.outlineColor = Cesium.Color.fromCssColorString(entityConfig.point.outlineColor);
              } else if (Array.isArray(entityConfig.point.outlineColor)) {
                  entityConfig.point.outlineColor = new Cesium.Color(...entityConfig.point.outlineColor);
              }
          }

          const entity = viewer.entities.add(entityConfig);
          el._entities.push(entity);
          break;


        case 'removeEntity':
          const entityId = args[0];
          const entityToRemove = viewer.entities.getById(entityId);
          if (entityToRemove) {
            viewer.entities.remove(entityToRemove);
            const index = el._entities.indexOf(entityToRemove);
            if (index > -1) {
              el._entities.splice(index, 1);
            }
          }
          break;

        case 'home':
          viewer.camera.setView({
            destination: window.Cesium.Cartesian3.fromDegrees(0, 0, 10000000)
          });
          break;

        default:
          console.warn(`Unknown Cesium method: ${method}`);
      }
    } catch (error) {
      console.error(`Error executing Cesium method ${method}:`, error);
      if (sendEvent) {
        sendEvent('error', { method, error: error.message });
      }
    }
  }

  // Cleanup function
  return () => {
    if (el._navigationObserver) {
      el._navigationObserver.disconnect();
      el._navigationObserver = null;
    }
    if (el._entities) {
      el._entities = [];
    }
    if (el._viewer) {
      el._viewer.destroy();
      el._viewer = null;
    }
  };
}

export default { render };