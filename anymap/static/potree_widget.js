// Load Three.js and OrbitControls from CDN using traditional script tags
function loadThreeJS() {
  return new Promise((resolve, reject) => {
    // Check if Three.js is already loaded
    if (window.THREE) {
      resolve();
      return;
    }

    // Check if script is already being loaded
    const existingScript = document.head.querySelector('script[src*="three.min.js"]');
    if (existingScript) {
      existingScript.addEventListener('load', resolve);
      existingScript.addEventListener('error', reject);
      return;
    }

    // Load Three.js first
    const threeScript = document.createElement('script');
    threeScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r156/three.min.js';
    threeScript.async = false;

    threeScript.addEventListener('load', () => {
      // Load OrbitControls after Three.js
      const controlsScript = document.createElement('script');
      controlsScript.src = 'https://cdn.jsdelivr.net/npm/three@0.156.1/examples/js/controls/OrbitControls.js';
      controlsScript.async = false;

      controlsScript.addEventListener('load', () => {
        // Make OrbitControls available
        if (window.THREE && window.THREE.OrbitControls) {
          resolve();
        } else {
          // Fallback: create a basic OrbitControls placeholder
          window.THREE = window.THREE || {};
          window.THREE.OrbitControls = function(camera, domElement) {
            this.camera = camera;
            this.domElement = domElement;
            this.target = new THREE.Vector3();
            this.update = function() {};
            this.dispose = function() {};
          };
          resolve();
        }
      });

      controlsScript.addEventListener('error', () => {
        // If OrbitControls fails to load, continue without it
        console.warn('OrbitControls failed to load, continuing without camera controls');
        resolve();
      });

      document.head.appendChild(controlsScript);
    });

    threeScript.addEventListener('error', reject);
    document.head.appendChild(threeScript);

    // Fallback timeout
    setTimeout(() => {
      if (!window.THREE) {
        reject(new Error('Three.js failed to load'));
      }
    }, 15000);
  });
}

function render({ model, el }) {
  // Create unique ID for this widget instance
  const widgetId = `anymap-potree-${Math.random().toString(36).substr(2, 9)}`;

  // Create container for the viewer
  const container = document.createElement("div");
  container.id = widgetId;
  container.style.width = model.get("width");
  container.style.height = model.get("height");
  container.style.position = "relative";
  container.style.overflow = "hidden";
  container.style.backgroundColor = model.get("background_color") || "#000000";

  // Ensure parent element has proper styling
  el.style.width = "100%";
  el.style.display = "block";

  // Clear any existing content and cleanup
  if (el._scene) {
    el._scene = null;
  }
  if (el._camera) {
    el._camera = null;
  }
  if (el._renderer) {
    el._renderer.dispose();
    el._renderer = null;
  }
  if (el._controls) {
    el._controls.dispose();
    el._controls = null;
  }
  if (el._potree) {
    el._potree = null;
  }
  if (el._pointClouds) {
    el._pointClouds = [];
  }

  el.innerHTML = "";
  el.appendChild(container);

  // Show loading indicator
  const loadingDiv = document.createElement("div");
  loadingDiv.className = "anymap-potree-loading";
  loadingDiv.style.position = "absolute";
  loadingDiv.style.top = "50%";
  loadingDiv.style.left = "50%";
  loadingDiv.style.transform = "translate(-50%, -50%)";
  loadingDiv.style.color = "#ffffff";
  loadingDiv.style.fontSize = "16px";
  loadingDiv.style.fontFamily = "Arial, sans-serif";
  loadingDiv.textContent = "Loading Three.js...";
  container.appendChild(loadingDiv);

  // Load Three.js and initialize when ready
  loadThreeJS().then(() => {
    initializeViewer();
  }).catch((error) => {
    console.error("Failed to load Three.js:", error);
    console.log("Falling back to basic canvas renderer");
    initializeFallbackViewer();
  });

  // Function to initialize viewer when library is ready
  function initializeViewer() {
    if (!window.THREE) {
      console.error("Three.js library not loaded");
      return;
    }

    // Remove loading indicator
    if (loadingDiv.parentNode) {
      loadingDiv.parentNode.removeChild(loadingDiv);
    }

    // Initialize Three.js scene
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      model.get("fov") || 60,
      container.clientWidth / container.clientHeight,
      model.get("near_clip") || 0.1,
      model.get("far_clip") || 1000
    );

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setClearColor(new THREE.Color(model.get("background_color") || "#000000"));
    container.appendChild(renderer.domElement);

    // Set up camera position
    const cameraPos = model.get("camera_position") || [0, 0, 10];
    const cameraTarget = model.get("camera_target") || [0, 0, 0];
    camera.position.set(cameraPos[0], cameraPos[1], cameraPos[2]);
    camera.lookAt(new THREE.Vector3(cameraTarget[0], cameraTarget[1], cameraTarget[2]));

    // Set up orbit controls
    let controls;
    if (window.THREE.OrbitControls) {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.target.set(cameraTarget[0], cameraTarget[1], cameraTarget[2]);
      controls.update();
    }

    // Store references
    el._scene = scene;
    el._camera = camera;
    el._renderer = renderer;
    el._controls = controls;
    el._pointClouds = [];
    el._widgetId = widgetId;

    // Add coordinate grid if enabled
    if (model.get("show_grid")) {
      const gridSize = model.get("grid_size") || 10;
      const gridColor = new THREE.Color(model.get("grid_color") || "#aaaaaa");
      const grid = new THREE.GridHelper(gridSize, 10, gridColor, gridColor);
      scene.add(grid);
    }

    // Setup resize observer
    let resizeObserver;
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        setTimeout(() => {
          if (camera && renderer && container) {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
          }
        }, 100);
      });
      resizeObserver.observe(el);
      resizeObserver.observe(container);
    }

    // Animation loop
    function animate() {
      requestAnimationFrame(animate);

      if (controls) {
        controls.update();
      }

      // Render the scene
      renderer.render(scene, camera);
    }
    animate();

    // Load initial point cloud if provided
    const initialPointCloudUrl = model.get("point_cloud_url");
    if (initialPointCloudUrl) {
      loadPointCloudFromUrl(initialPointCloudUrl);
    }

    // Restore state from model
    restoreViewerState();
  }

  // Function to load point cloud from URL (placeholder)
  function loadPointCloudFromUrl(url, name = "Point Cloud") {
    console.log("Point cloud loading requested:", url, name);
    console.warn("Point cloud loading not yet implemented - requires Potree library integration");

    // For now, just add a simple placeholder object
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshBasicMaterial({ color: 0x00ff00, wireframe: true });
    const placeholder = new THREE.Mesh(geometry, material);
    placeholder.name = name || "Placeholder";

    el._scene.add(placeholder);
    el._pointClouds.push(placeholder);

    fitToScreen();
  }

  // Function to fit point clouds to screen
  function fitToScreen() {
    if (!el._pointClouds.length || !el._camera || !el._controls) {
      return;
    }

    // Calculate bounding box of all objects
    const box = new THREE.Box3();
    el._pointClouds.forEach(obj => {
      const objBox = new THREE.Box3().setFromObject(obj);
      box.union(objBox);
    });

    if (!box.isEmpty()) {
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxSize = Math.max(size.x, size.y, size.z);

      // Position camera
      const distance = maxSize * 3;
      el._camera.position.copy(center);
      el._camera.position.z += distance;

      if (el._controls) {
        el._controls.target.copy(center);
        el._controls.update();
      }
    }
  }

  // Function to restore viewer state from model
  function restoreViewerState() {
    // This would restore any persistent state if needed
  }

  // Fallback viewer without Three.js dependencies
  function initializeFallbackViewer() {
    // Remove loading indicator
    if (loadingDiv.parentNode) {
      loadingDiv.parentNode.removeChild(loadingDiv);
    }

    // Create a simple canvas fallback
    const canvas = document.createElement('canvas');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';
    container.appendChild(canvas);

    const ctx = canvas.getContext('2d');

    // Draw a simple visualization
    function drawFallback() {
      ctx.fillStyle = model.get("background_color") || "#000000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw grid if enabled
      if (model.get("show_grid")) {
        ctx.strokeStyle = model.get("grid_color") || "#444444";
        ctx.lineWidth = 1;
        const gridSize = 50; // Fixed grid size for fallback

        for (let x = 0; x <= canvas.width; x += gridSize) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, canvas.height);
          ctx.stroke();
        }

        for (let y = 0; y <= canvas.height; y += gridSize) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(canvas.width, y);
          ctx.stroke();
        }
      }

      // Draw center message
      ctx.fillStyle = "#ffffff";
      ctx.font = "16px Arial";
      ctx.textAlign = "center";
      ctx.fillText("Potree Viewer", canvas.width / 2, canvas.height / 2 - 20);
      ctx.fillText("(Three.js library not available)", canvas.width / 2, canvas.height / 2 + 20);
    }

    drawFallback();

    // Store minimal references
    el._canvas = canvas;
    el._ctx = ctx;
    el._widgetId = widgetId;

    // Handle resize
    window.addEventListener('resize', () => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      drawFallback();
    });

    // Redraw when background color changes
    model.on("change:background_color", drawFallback);
    model.on("change:show_grid", drawFallback);
    model.on("change:grid_color", drawFallback);
  }

  // Handle JavaScript method calls from Python
  function handleJSMethodCall(call) {
    const { method, args, kwargs } = call;

    try {
      switch (method) {
        case "loadPointCloud":
          if (args && args.length > 0) {
            const options = args[0];
            loadPointCloudFromUrl(options.url, options.name);
          }
          break;

        case "fitToScreen":
          fitToScreen();
          break;

        case "clearPointClouds":
          el._pointClouds.forEach(pc => {
            el._scene.remove(pc);
          });
          el._pointClouds = [];
          break;

        case "takeScreenshot":
          // Render current frame to get screenshot
          el._renderer.render(el._scene, el._camera);
          const dataURL = el._renderer.domElement.toDataURL();
          // Could emit event back to Python with screenshot data
          break;

        case "loadMultiplePointClouds":
          if (args && args.length > 0) {
            const pointClouds = args[0];
            pointClouds.forEach(pc => {
              loadPointCloudFromUrl(pc.url, pc.name);
            });
          }
          break;

        case "setQuality":
          if (args && args.length > 0) {
            const quality = args[0];
            // Adjust rendering quality based on setting
            if (quality === "low") {
              el._renderer.setPixelRatio(0.5);
            } else if (quality === "medium") {
              el._renderer.setPixelRatio(0.75);
            } else if (quality === "high") {
              el._renderer.setPixelRatio(1.0);
            }
          }
          break;

        case "addMeasurement":
          // Implementation would depend on Potree measurement tools
          console.log("Measurement tools not yet implemented");
          break;

        case "clearMeasurements":
          // Clear measurement objects
          console.log("Clear measurements not yet implemented");
          break;

        case "clearFilters":
          // Reset any applied filters
          el._pointClouds.forEach(pc => {
            if (pc.material) {
              // Reset material properties to defaults
            }
          });
          break;

        default:
          console.warn(`Unknown method: ${method}`);
      }
    } catch (error) {
      console.error(`Error executing method ${method}:`, error);
    }
  }

  // Listen for JavaScript method calls
  model.on("change:_js_calls", () => {
    const calls = model.get("_js_calls") || [];
    const lastCall = calls[calls.length - 1];
    if (lastCall) {
      handleJSMethodCall(lastCall);
    }
  });

  // Listen for trait changes
  model.on("change:point_size", () => {
    const size = model.get("point_size");
    console.log("Point size changed to:", size);
    // Point size changes will be implemented when actual point cloud loading is added
  });

  model.on("change:point_size_type", () => {
    const sizeType = model.get("point_size_type");
    console.log("Point size type changed to:", sizeType);
    // Point size type changes will be implemented when actual point cloud loading is added
  });

  model.on("change:point_shape", () => {
    const shape = model.get("point_shape");
    console.log("Point shape changed to:", shape);
    // Point shape changes will be implemented when actual point cloud loading is added
  });

  model.on("change:background_color", () => {
    const color = model.get("background_color");
    if (el._renderer) {
      el._renderer.setClearColor(new THREE.Color(color));
    }
    container.style.backgroundColor = color;
  });

  model.on("change:camera_position", () => {
    const position = model.get("camera_position");
    if (el._camera && position && position.length >= 3) {
      el._camera.position.set(position[0], position[1], position[2]);
    }
  });

  model.on("change:camera_target", () => {
    const target = model.get("camera_target");
    if (el._controls && target && target.length >= 3) {
      el._controls.target.set(target[0], target[1], target[2]);
      el._controls.update();
    }
  });

  model.on("change:fov", () => {
    const fov = model.get("fov");
    if (el._camera) {
      el._camera.fov = fov;
      el._camera.updateProjectionMatrix();
    }
  });

  model.on("change:show_grid", () => {
    const showGrid = model.get("show_grid");
    // Find existing grid and toggle visibility
    el._scene.children.forEach(child => {
      if (child instanceof THREE.GridHelper) {
        child.visible = showGrid;
      }
    });

    // Add grid if it doesn't exist and should be shown
    if (showGrid) {
      const existingGrid = el._scene.children.find(child => child instanceof THREE.GridHelper);
      if (!existingGrid) {
        const gridSize = model.get("grid_size") || 10;
        const gridColor = new THREE.Color(model.get("grid_color") || "#aaaaaa");
        const grid = new THREE.GridHelper(gridSize, 10, gridColor, gridColor);
        el._scene.add(grid);
      }
    }
  });

  // Cleanup function
  el._cleanup = () => {
    if (el._renderer) {
      el._renderer.dispose();
    }
    if (el._controls && el._controls.dispose) {
      el._controls.dispose();
    }
    if (typeof resizeObserver !== 'undefined' && resizeObserver) {
      resizeObserver.disconnect();
    }
    // Clear any canvas contexts
    if (el._canvas) {
      el._canvas = null;
    }
    if (el._ctx) {
      el._ctx = null;
    }
  };
}

// Cleanup function for proper widget disposal
function cleanup(el) {
  if (el._cleanup) {
    el._cleanup();
  }
}

// Export default object with render and cleanup functions
export default { render, cleanup };