function loadStyle(href) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

async function render({ model, el }) {

  let POTREE_BASE = model.get('POTREE_LIBS_DIR')
  if (!POTREE_BASE) {
    console.log("NO POTREE_LIBS_DIR FOUND!")
        let div = document.createElement("div");
        div.className = "potree-warning";
        const msg = document.createTextNode("Error creating widget (no POTREE_LIBS_DIR found)");
        div.appendChild(msg);
        el.appendChild(div);
        return
  }

  // Load styles
  loadStyle(`${POTREE_BASE}/build/potree/potree.css`);
  loadStyle(`${POTREE_BASE}/libs/jquery-ui/jquery-ui.min.css`);
  loadStyle(`${POTREE_BASE}/libs/openlayers3/ol.css`);
  loadStyle(`${POTREE_BASE}/libs/spectrum/spectrum.css`);
  loadStyle(`${POTREE_BASE}/libs/jstree/themes/mixed/style.css`);

  // Load libs
  await loadScript(`${POTREE_BASE}/libs/jquery/jquery-3.1.1.min.js`);
  await loadScript(`${POTREE_BASE}/libs/spectrum/spectrum.js`);
  await loadScript(`${POTREE_BASE}/libs/jquery-ui/jquery-ui.min.js`);
  await loadScript(`${POTREE_BASE}/libs/three.js/build/three.js`);
  await loadScript(`${POTREE_BASE}/libs/other/BinaryHeap.js`);
  await loadScript(`${POTREE_BASE}/libs/tween/tween.min.js`);
  await loadScript(`${POTREE_BASE}/libs/d3/d3.js`);
  await loadScript(`${POTREE_BASE}/libs/proj4/proj4.js`);
  await loadScript(`${POTREE_BASE}/libs/openlayers3/ol.js`);
  await loadScript(`${POTREE_BASE}/libs/i18next/i18next.js`);
  await loadScript(`${POTREE_BASE}/libs/jstree/jstree.js`);
  await loadScript(`${POTREE_BASE}/libs/plasio/js/laslaz.js`);
  await loadScript(`${POTREE_BASE}/libs/copc/index.js`);
  await loadScript(`${POTREE_BASE}/build/potree/potree.js`);

  // Create container for the sidebar
  const sideBar = document.createElement("div");
  sideBar.id = "potree_sidebar_container"; // hard-coded in potree

  // Create Potree viewer inside the widget container
  const container = document.createElement("div");
  container.style.width = model.get("width");
  container.style.height = model.get("height");
  container.id = "potree_render_area"; // hard-coded in potree

  //container.style.backgroundColor = model.get("background_color") || "#000000";

  // Ensure parent element has proper styling
  el.style.width = "100%";
  el.style.display = "block";
  el.style.height = model.get("height");
  el.style.background = "#111";

  el.innerHTML="";
  el.appendChild(container);
  el.appendChild(sideBar);

  //
  const viewer = new Potree.Viewer(container);
  viewer.setEDLEnabled(true);
  viewer.setFOV(60);
  viewer.setPointBudget(1_000_000);
  viewer.setDescription(model.get("description"));
  viewer.loadSettingsFromURL();

  viewer.loadGUI(() => {
  viewer.setLanguage('en');
  const $menuAppearance = $("#menu_appearance");
    if ($menuAppearance.length > 0) {
      $menuAppearance.next().show();
    }
  });

  if (model.get('point_cloud_url')){
    Potree.loadPointCloud(
     model.get('point_cloud_url'),
      "example",
      function(e) {
        viewer.scene.addPointCloud(e.pointcloud);
        let material = e.pointcloud.material;
        material.size = 1;
        material.pointSizeType = Potree.PointSizeType.ADAPTIVE;
        viewer.fitToScreen();
      }
     );
  }

  // Handle model changes from Python
  model.on("change:description", () => {
    const newDesc = model.get("description") || "";
    viewer.setDescription(newDesc);
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
            case 'loadPointCloud':
                const pcConfig = args[0];
                if (pcConfig){
                  console.log("TODO");
                  console.log(pcConfig)
                }

              break;
      }
    } catch(error){
      console.error(`Error executing map method ${method}:`, error);
      sendEvent('error', { method, error: error.message });
    }
   }

   // Cleanup function
  return () => {
    if (el._map) {
      el._map.remove();
      el._map = null;
    }
  };

}

export default { render };