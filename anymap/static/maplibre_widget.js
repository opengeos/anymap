// Helper function to process DeckGL properties
const THREE_VERSION = '0.178.0';

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

function resolveLegendControlClass() {
  const candidates = [
    () => window.MapboxLegendControl,
    () => window.LegendControl,
    () => window.mapboxgl && window.mapboxgl.LegendControl,
    () => window.maplibregl && window.maplibregl.LegendControl,
  ];

  for (const get of candidates) {
    try {
      const value = get();
      if (!value) continue;
      if (typeof value === 'function') return value;
      if (typeof value === 'object') {
        if (typeof value.LegendControl === 'function') return value.LegendControl;
        if (typeof value.default === 'function') return value.default;
        // Some UMDs nest under .default.LegendControl
        if (value.default && typeof value.default.LegendControl === 'function') {
          return value.default.LegendControl;
        }
      }
    } catch (_) {}
  }
  return null;
}

function scheduleLegendInitialization(controlKey, { position, options }, map, el) {
  const attempt = () => {
    try {
      const LegendCtor = resolveLegendControlClass();
      if (!LegendCtor) {
        setTimeout(attempt, 200);
        return;
      }
      const legendConfig = { ...(options || {}) };
      const labelOverridesRaw = legendConfig.labelOverrides || legendConfig.label_overrides;
      delete legendConfig.labelOverrides;
      delete legendConfig.label_overrides;

      const normalizeHeight = (value) => {
        if (value == null) return null;
        if (typeof value === 'number') return `${value}px`;
        const str = String(value).trim();
        if (!str) return null;
        if (/^\d+(\.\d+)?$/.test(str)) {
          return `${str}px`;
        }
        return str;
      };

      const maxHeightRaw = legendConfig.maxHeight || legendConfig.max_height;
      delete legendConfig.maxHeight;
      delete legendConfig.max_height;

      const computeAutoMaxHeight = () => {
        try {
          if (map && typeof map.getContainer === 'function') {
            const container = map.getContainer();
            if (container && container.clientHeight) {
              const height = Math.max(container.clientHeight - 100, 160);
              return `${height}px`;
            }
          }
        } catch (error) {
          console.warn('Failed to compute map-based legend height:', error);
        }

        if (el && el.clientHeight) {
          const fallback = Math.max(el.clientHeight - 100, 160);
          return `${fallback}px`;
        }

        if (typeof window !== 'undefined' && window.innerHeight) {
          const viewportHeight = Math.max(window.innerHeight - 100, 160);
          return `${viewportHeight}px`;
        }

        return 'calc(100vh - 100px)';
      };

      let maxHeight = normalizeHeight(maxHeightRaw);
      const autoMaxHeight = maxHeight == null;
      if (autoMaxHeight) {
        maxHeight = computeAutoMaxHeight();
      }

      const toggleIconRaw = legendConfig.toggleIcon || legendConfig.toggle_icon;
      delete legendConfig.toggleIcon;
      delete legendConfig.toggle_icon;

      let targetsArg = legendConfig.targets;
      if (targetsArg && typeof targetsArg === 'object') {
        targetsArg = { ...targetsArg };
      }
      delete legendConfig.targets;

      const base = new LegendCtor(targetsArg, legendConfig);
      const controlState = {
        targets: targetsArg,
        options: legendConfig,
        labelOverrides: labelOverridesRaw && typeof labelOverridesRaw === 'object'
          ? { ...labelOverridesRaw }
          : {},
        maxHeight,
        autoMaxHeight,
        container: null,
        methodsPatched: false,
        toggleIcon: toggleIconRaw != null ? String(toggleIconRaw) : null,
        resizeHandler: null,
        mapResizeHandler: null,
        base,
      };

      const originalGetLayerLegend = typeof base.getLayerLegend === 'function'
        ? base.getLayerLegend
        : null;

      const applyLabelOverrides = () => {
        if (!originalGetLayerLegend) {
          return;
        }

        if (!controlState.labelOverrides || Object.keys(controlState.labelOverrides).length === 0) {
          base.getLayerLegend = originalGetLayerLegend;
          return;
        }

        base.getLayerLegend = function patchedGetLayerLegend(...args) {
          const existingTargets = this.targets;
          let mergedTargets = existingTargets;

          if (existingTargets === undefined) {
            mergedTargets = { ...controlState.labelOverrides };
          } else {
            mergedTargets = { ...existingTargets, ...controlState.labelOverrides };
          }

          this.targets = mergedTargets;
          try {
            return originalGetLayerLegend.apply(this, args);
          } finally {
            this.targets = existingTargets;
          }
        };
      };

      const ensureAutoHeightListeners = () => {
        if (!controlState.autoMaxHeight || controlState.resizeHandler) {
          return;
        }
        const handler = () => {
          const nextValue = computeAutoMaxHeight();
          if (nextValue && nextValue !== controlState.maxHeight) {
            controlState.maxHeight = nextValue;
            applyMaxHeight();
          }
        };
        controlState.resizeHandler = handler;
        if (typeof window !== 'undefined') {
          window.addEventListener('resize', handler);
        }
        if (map && typeof map.on === 'function') {
          map.on('resize', handler);
          controlState.mapResizeHandler = handler;
        }
      };

      const teardownAutoHeightListeners = () => {
        if (controlState.resizeHandler && typeof window !== 'undefined') {
          window.removeEventListener('resize', controlState.resizeHandler);
        }
        if (controlState.mapResizeHandler && map && typeof map.off === 'function') {
          map.off('resize', controlState.mapResizeHandler);
        }
        controlState.resizeHandler = null;
        controlState.mapResizeHandler = null;
      };

      const applyMaxHeight = () => {
        const container = controlState.container;
        if (!container) {
          return;
        }
        const targetEl =
          container.querySelector('.mapboxgl-legend-list') ||
          container.querySelector('.mapboxgl-legend') ||
          container;
        if (!targetEl) return;

        if (controlState.maxHeight) {
          targetEl.style.maxHeight = controlState.maxHeight;
          if (!targetEl.style.overflowY) {
            targetEl.style.overflowY = 'auto';
          }
          if (!targetEl.style.overflowX) {
            targetEl.style.overflowX = 'hidden';
          }
        }
      };

      const updateMaxHeight = (value) => {
        const normalized = normalizeHeight(value);
        if (normalized) {
          controlState.autoMaxHeight = false;
          teardownAutoHeightListeners();
          controlState.maxHeight = normalized;
        } else if (value !== undefined) {
          controlState.autoMaxHeight = true;
          controlState.maxHeight = computeAutoMaxHeight();
          ensureAutoHeightListeners();
        }
        applyMaxHeight();
      };

      if (controlState.autoMaxHeight) {
        ensureAutoHeightListeners();
      }

      const applyLegendStyling = () => {
        const container = controlState.container;
        if (!container) {
          return;
        }

        const resolveToggleButton = () =>
          container.querySelector('.mapboxgl-legend-switcher') ||
          container.querySelector('.mapboxgl-legend-button');

        const applyToggleIcon = () => {
          const button = resolveToggleButton();
          if (!button) {
            return;
          }
          const iconContent =
            controlState.toggleIcon && controlState.toggleIcon.length > 0
              ? controlState.toggleIcon
              : '<span style="font-size:16px;line-height:1;">☷</span>';

          if (button.innerHTML !== iconContent) {
            button.innerHTML = iconContent;
          }
          if (!button.getAttribute('aria-label')) {
            button.setAttribute('aria-label', 'Show legend');
          }
          button.style.display = 'inline-flex';
          button.style.alignItems = 'center';
          button.style.justifyContent = 'center';
          button.style.width = '30px';
          button.style.height = '30px';
          button.style.borderRadius = '4px';
          button.style.background = 'rgba(255,255,255,0.92)';
          button.style.border = '1px solid rgba(0,0,0,0.2)';
          button.style.boxShadow = '0 1px 2px rgba(0,0,0,0.25)';
          button.style.cursor = 'pointer';
          button.style.padding = '0';
          if (!button.style.margin) {
            button.style.margin = '0 0 6px 0';
          }
        };

        const title = container.querySelector('.mapboxgl-legend-title-label');
        const closeBtn = container.querySelector('.mapboxgl-legend-close-button');

        if (title) {
          title.style.fontWeight = '600';
          title.style.fontSize = '13px';
          title.style.color = '#1f1f1f';
          title.style.margin = '0';
        }

        if (title && closeBtn) {
          let header = container.querySelector('.anymap-legend-header');
          if (!header) {
            header = document.createElement('div');
            header.className = 'anymap-legend-header';
            const parent = title.parentNode || container;
            parent.insertBefore(header, title);
          }
          if (!header.contains(title)) {
            header.appendChild(title);
          }
          if (!header.contains(closeBtn)) {
            header.appendChild(closeBtn);
          }
          header.style.display = 'flex';
          header.style.alignItems = 'center';
          header.style.justifyContent = 'space-between';
          header.style.gap = '8px';
          header.style.marginBottom = '4px';

          closeBtn.style.margin = '0';
          closeBtn.style.background = 'transparent';
          closeBtn.style.border = 'none';
          closeBtn.style.cursor = 'pointer';
          closeBtn.style.fontSize = '14px';
          closeBtn.style.lineHeight = '1';
          closeBtn.style.padding = '2px 4px';

          let nextNode = header.nextSibling;
          while (nextNode && nextNode.nodeType === Node.TEXT_NODE && !nextNode.textContent.trim()) {
            nextNode = nextNode.nextSibling;
          }
          if (nextNode && nextNode.nodeType === Node.ELEMENT_NODE && nextNode.tagName === 'BR') {
            nextNode.parentNode.removeChild(nextNode);
          }
        }

        const rows = container.querySelectorAll('.legend-table tr');
        rows.forEach((row) => {
          row.style.height = '26px';
          row.style.lineHeight = '26px';
          row.style.display = 'table-row';
          row.style.borderBottom = '1px solid rgba(0,0,0,0.05)';

          const cells = row.querySelectorAll('td');
          if (cells.length === 0) {
            return;
          }

          const hasCheckbox = cells.length === 3;
          const symbolCell = hasCheckbox ? cells[1] : cells[0];
          const labelCell = hasCheckbox ? cells[2] : cells[1];

          if (symbolCell) {
            symbolCell.style.width = '28px';
            symbolCell.style.minWidth = '28px';
            symbolCell.style.maxWidth = '32px';
            symbolCell.style.padding = '2px 6px';
            symbolCell.style.display = '';
            symbolCell.style.alignItems = '';
            symbolCell.style.justifyContent = '';
            symbolCell.style.borderRadius = '4px';
            symbolCell.style.boxSizing = 'border-box';
            symbolCell.style.margin = '2px 0';
            const hasInlineBackground =
              symbolCell.style.backgroundColor && symbolCell.style.backgroundColor !== 'transparent';
            if (!hasInlineBackground) {
              symbolCell.style.backgroundColor = 'transparent';
            }
            symbolCell.style.backgroundImage = symbolCell.style.backgroundImage || '';
            symbolCell.style.backgroundPosition = symbolCell.style.backgroundPosition || 'center';
            symbolCell.style.backgroundRepeat = symbolCell.style.backgroundRepeat || 'no-repeat';
            symbolCell.style.backgroundSize = symbolCell.style.backgroundSize || 'contain';

            const img = symbolCell.querySelector('img');
            if (img) {
              img.style.maxHeight = '18px';
              img.style.maxWidth = '22px';
            }
            const svg = symbolCell.querySelector('svg');
            if (svg) {
              svg.style.maxHeight = '18px';
              svg.style.maxWidth = '22px';
              svg.style.display = 'block';
              svg.style.margin = '0 auto';
            }

            const swatch = symbolCell.querySelector('div');
            if (swatch) {
              swatch.style.margin = '0 auto';
              swatch.style.width = '100%';
              swatch.style.height = '100%';
              swatch.style.borderRadius = '3px';
            }
          }

          if (labelCell) {
            labelCell.style.paddingLeft = '6px';
            labelCell.style.fontSize = '12px';
            labelCell.style.color = '#1f1f1f';
            labelCell.style.whiteSpace = 'nowrap';
          }
        });

        applyToggleIcon();
      };

      const patchLegendMethods = () => {
        if (controlState.methodsPatched) {
          return;
        }
        if (typeof base.updateLegendControl === 'function') {
          const originalUpdate = base.updateLegendControl.bind(base);
          base.updateLegendControl = (...args) => {
            const result = originalUpdate(...args);
            applyLegendStyling();
            return result;
          };
        }
        if (typeof base.redraw === 'function') {
          const originalRedraw = base.redraw.bind(base);
          base.redraw = (...args) => {
            const result = originalRedraw(...args);
            applyLegendStyling();
            return result;
          };
        }
        controlState.methodsPatched = true;
      };

      patchLegendMethods();
      applyLabelOverrides();

      const refreshLegend = (force = false) => {
        try {
          if (!controlState.base) {
            return;
          }
          if (force && typeof controlState.base.updateLegendControl === 'function') {
            controlState.base.updateLegendControl();
            return;
          }
          if (typeof controlState.base.redraw === 'function') {
            controlState.base.redraw();
          } else if (typeof controlState.base.updateLegendControl === 'function') {
            controlState.base.updateLegendControl();
          }
        } catch (error) {
          console.debug('Legend refresh failed:', error);
        }
      };

      const control = {
        onAdd(m) {
          const elc = base.onAdd(m);
          try {
            if (elc && elc.classList) {
              elc.classList.add('maplibregl-ctrl');
              elc.classList.add('maplibregl-ctrl-group');
              if (!elc.style.margin) elc.style.margin = '10px';
            }
          } catch (_) {}
          controlState.container = elc;
          applyMaxHeight();
          applyLegendStyling();
          refreshLegend(true);
          if (controlState.autoMaxHeight) {
            ensureAutoHeightListeners();
          }
          return elc;
        },
        onRemove(m) {
          try {
            teardownAutoHeightListeners();
            controlState.container = null;
          } catch (_) {}
          if (typeof base.onRemove === 'function') {
            base.onRemove(m);
          }
        },
        updateOptions: (opts) => {
          if (!opts || typeof opts !== 'object') {
            return;
          }
          const nextConfig = { ...opts };
          const nextTargets = nextConfig.targets && typeof nextConfig.targets === 'object'
            ? { ...nextConfig.targets }
            : undefined;
          delete nextConfig.targets;

          const nextLabelOverrides = nextConfig.labelOverrides || nextConfig.label_overrides;
          delete nextConfig.labelOverrides;
          delete nextConfig.label_overrides;

          const nextMaxHeight = nextConfig.maxHeight || nextConfig.max_height;
          delete nextConfig.maxHeight;
          delete nextConfig.max_height;

          const nextToggleIcon =
            nextConfig.toggleIcon !== undefined
              ? nextConfig.toggleIcon
              : nextConfig.toggle_icon;
          delete nextConfig.toggleIcon;
          delete nextConfig.toggle_icon;

          if (nextTargets) {
            controlState.targets = nextTargets;
            base.targets = { ...nextTargets };
          }

          if (nextLabelOverrides && typeof nextLabelOverrides === 'object') {
            controlState.labelOverrides = {
              ...(controlState.labelOverrides || {}),
              ...nextLabelOverrides,
            };
            applyLabelOverrides();
          }

          if (nextMaxHeight !== undefined) {
            updateMaxHeight(nextMaxHeight);
          }

          if (nextToggleIcon !== undefined) {
            const iconString = nextToggleIcon != null ? String(nextToggleIcon) : '';
            controlState.toggleIcon = iconString.length > 0 ? iconString : null;
          }

          if (Object.keys(nextConfig).length > 0) {
            controlState.options = { ...controlState.options, ...nextConfig };
            base.options = { ...(base.options || {}), ...controlState.options };
          }

          refreshLegend();
          applyLegendStyling();
        },
        refreshLegend: () => refreshLegend(true),
      };
      controlState.cleanup = () => {
        teardownAutoHeightListeners();
        controlState.container = null;
      };
      control._anymapLegendState = controlState;
      map.addControl(control, position || 'bottom-left');
      el._controls.set(controlKey, control);
      console.log('Legend control initialized successfully');
    } catch (error) {
      console.error('Failed to initialize Legend control:', error);
    }
  };
  attempt();
}

function resolveExportControlClass() {
  if (!window.MaplibreExportControl) {
    return null;
  }

  if (typeof window.MaplibreExportControl === 'function') {
    return window.MaplibreExportControl;
  }

  if (typeof window.MaplibreExportControl === 'object' && window.MaplibreExportControl !== null) {
    if (typeof window.MaplibreExportControl.MaplibreExportControl === 'function') {
      return window.MaplibreExportControl.MaplibreExportControl;
    }
    if (typeof window.MaplibreExportControl.default === 'function') {
      return window.MaplibreExportControl.default;
    }
  }

  return null;
}

function normalizeExportControlOptions(rawOptions = {}) {
  const exportOptions = { ...rawOptions };
  const shouldStartCollapsed = exportOptions.collapsed !== false;

  delete exportOptions.position;
  delete exportOptions.collapsed;

  if (Array.isArray(exportOptions.PageSize)) {
    const numericSize = exportOptions.PageSize
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));
    if (numericSize.length === 2) {
      exportOptions.PageSize = numericSize;
    } else {
      delete exportOptions.PageSize;
    }
  }

  if (typeof exportOptions.PageOrientation === 'string') {
    exportOptions.PageOrientation = exportOptions.PageOrientation.toLowerCase();
  }

  if (typeof exportOptions.Format === 'string') {
    exportOptions.Format = exportOptions.Format.toLowerCase();
  }

  if (Array.isArray(exportOptions.AllowedSizes)) {
    exportOptions.AllowedSizes = exportOptions.AllowedSizes.map((value) =>
      String(value).toUpperCase(),
    );
  }

  if (exportOptions.DPI !== undefined) {
    const dpiNumber = Number(exportOptions.DPI);
    if (Number.isFinite(dpiNumber)) {
      exportOptions.DPI = dpiNumber;
    } else {
      delete exportOptions.DPI;
    }
  }

  if (exportOptions.Crosshair !== undefined) {
    exportOptions.Crosshair = Boolean(exportOptions.Crosshair);
  }

  if (exportOptions.PrintableArea !== undefined) {
    exportOptions.PrintableArea = Boolean(exportOptions.PrintableArea);
  }

  if (exportOptions.Locale !== undefined) {
    exportOptions.Locale = String(exportOptions.Locale || '').toLowerCase() || 'en';
  }

  if (typeof exportOptions.Filename === 'string') {
    exportOptions.Filename = exportOptions.Filename.trim() || 'map';
  }

  return {
    options: exportOptions,
    startCollapsed: shouldStartCollapsed,
  };
}

function applyExportControlCollapsedState(control, shouldCollapse) {
  if (!control || typeof control !== 'object') {
    return;
  }
  const container = control.exportContainer;
  const button = control.exportButton;

  if (!container || !button) {
    return;
  }

  if (shouldCollapse) {
    button.style.display = 'block';
    container.style.display = 'none';
    if (typeof control.toggleCrosshair === 'function') {
      control.toggleCrosshair(false);
    }
    if (typeof control.togglePrintableArea === 'function') {
      control.togglePrintableArea(false);
    }
  } else {
    button.style.display = 'none';
    container.style.display = 'block';
    if (typeof control.toggleCrosshair === 'function') {
      control.toggleCrosshair(true);
    }
    if (typeof control.togglePrintableArea === 'function') {
      control.togglePrintableArea(true);
    }
  }
}

function resolveGeomanNamespace() {
  if (!window.Geoman || typeof window.Geoman !== 'object') {
    return null;
  }
  return window.Geoman;
}

function resolveGeoGridClass() {
  if (!window.GeoGrid) {
    return null;
  }

  // Handle different module export formats
  if (typeof window.GeoGrid === 'function') {
    return window.GeoGrid;
  }

  if (typeof window.GeoGrid === 'object' && window.GeoGrid !== null) {
    if (typeof window.GeoGrid.GeoGrid === 'function') {
      return window.GeoGrid.GeoGrid;
    }
    if (typeof window.GeoGrid.default === 'function') {
      return window.GeoGrid.default;
    }
  }

  return null;
}

// Map MapLibre paint properties to GeoGrid style properties
function mapToGeoGridStyle(styleOptions) {
  if (!styleOptions) return styleOptions;

  const mapped = {};

  // Map line properties (gridStyle)
  if (styleOptions['line-color']) mapped.color = styleOptions['line-color'];
  if (styleOptions['line-width']) mapped.width = styleOptions['line-width'];
  if (styleOptions['line-dasharray']) mapped.dasharray = styleOptions['line-dasharray'];
  if (styleOptions['line-opacity']) mapped.opacity = styleOptions['line-opacity'];

  // If using GeoGrid native properties, preserve them
  if (styleOptions.color) mapped.color = styleOptions.color;
  if (styleOptions.width) mapped.width = styleOptions.width;
  if (styleOptions.dasharray) mapped.dasharray = styleOptions.dasharray;
  if (styleOptions.opacity) mapped.opacity = styleOptions.opacity;

  // Label style properties (already in correct format)
  if (styleOptions.fontSize) mapped.fontSize = styleOptions.fontSize;
  if (styleOptions.textShadow) mapped.textShadow = styleOptions.textShadow;

  return mapped;
}

function buildGeomanOptions(position, geomanOptions = {}, collapsed) {
  const options = { ...(geomanOptions || {}) };
  const settings = { ...(options.settings || {}) };

  if (position && !settings.controlsPosition) {
    settings.controlsPosition = position;
  }

  if (typeof settings.controlsCollapsible !== 'boolean') {
    settings.controlsCollapsible = true;
  }

  options.settings = settings;
  return options;
}

function normalizeGeomanGeoJson(data) {
  if (!data || typeof data !== 'object') {
    return { type: 'FeatureCollection', features: [] };
  }

  if (data.type === 'FeatureCollection') {
    const features = Array.isArray(data.features) ? data.features.filter(Boolean) : [];
    return { type: 'FeatureCollection', features };
  }

  if (data.type && data.geometry) {
    return { type: 'FeatureCollection', features: [data] };
  }

  if (Array.isArray(data)) {
    return { type: 'FeatureCollection', features: data.filter(Boolean) };
  }

  return { type: 'FeatureCollection', features: [] };
}

function ensureThreeImportMap() {
  if (document.querySelector('script[data-source="anymap-three-importmap"]')) {
    return;
  }

  const importMap = {
    imports: {
      three: `https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/build/three.module.min.js`,
      'three/': `https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/`,
    },
  };

  const script = document.createElement('script');
  script.type = 'importmap';
  script.dataset.source = 'anymap-three-importmap';
  script.textContent = JSON.stringify(importMap);
  document.head.appendChild(script);
}

let _tilesSupportPromise = null;

async function ensureThreeTilesSupport(mapScene) {
  if (!_tilesSupportPromise) {
    _tilesSupportPromise = (async () => {
      ensureThreeImportMap();

      const [rendererModule, pluginModule, dracoModule, ktxModule] = await Promise.all([
        import('https://cdn.jsdelivr.net/npm/3d-tiles-renderer@0.4.17/build/index.three.js'),
        import('https://cdn.jsdelivr.net/npm/3d-tiles-renderer@0.4.17/build/index.three-plugins.js'),
        import(`https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/examples/jsm/loaders/DRACOLoader.js`),
        import(`https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/examples/jsm/loaders/KTX2Loader.js`),
      ]);

      return {
        TilesRenderer: rendererModule.TilesRenderer,
        GLTFExtensionsPlugin: pluginModule.GLTFExtensionsPlugin,
        CesiumIonAuthPlugin: pluginModule.CesiumIonAuthPlugin,
        DebugTilesPlugin: pluginModule.DebugTilesPlugin,
        TilesFadePlugin: pluginModule.TilesFadePlugin,
        UnloadTilesPlugin: pluginModule.UnloadTilesPlugin,
        UpdateOnChangePlugin: pluginModule.UpdateOnChangePlugin,
        DRACOLoader: dracoModule.DRACOLoader,
        KTX2Loader: ktxModule.KTX2Loader,
      };
    })();
  }

  return _tilesSupportPromise;
}

function createUniqueId(prefix) {
  if (window.crypto && window.crypto.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

function georeferenceTileset(renderer, group) {
  const center = new window.THREE.Vector3();
  const size = new window.THREE.Vector3();
  const box = new window.THREE.Box3();
  const sphere = new window.THREE.Sphere();

  if (renderer.getBoundingBox(box)) {
    box.getCenter(center);
    box.getSize(size);
  } else if (renderer.getBoundingSphere(sphere)) {
    center.copy(sphere.center);
    size.set(sphere.radius, sphere.radius, sphere.radius);
  } else {
    return null;
  }

  const cartographic = { lon: 0, lat: 0, height: 0 };
  renderer.ellipsoid.getPositionToCartographic(center, cartographic);

  const lng = (cartographic.lon * 180) / Math.PI;
  const lat = (cartographic.lat * 180) / Math.PI;
  const height = cartographic.height;

  const positionVector = window.MaplibreThreePlugin.SceneTransform.lngLatToVector3(
    lng,
    lat,
    height,
  );

  group.position.copy(positionVector);

  const projectedUnits = window.MaplibreThreePlugin.SceneTransform.projectedUnitsPerMeter(lat);
  group.scale.set(projectedUnits, projectedUnits, projectedUnits);

  if (
    !renderer.rootTileSet.asset.gltfUpAxis ||
    renderer.rootTileSet.asset.gltfUpAxis === 'Z'
  ) {
    group.rotation.x = Math.PI;
  }
  group.rotation.y = Math.PI;
  group.updateMatrixWorld();

  const enuMatrix = renderer.ellipsoid.getEastNorthUpFrame(
    cartographic.lat,
    cartographic.lon,
    cartographic.height,
    new window.THREE.Matrix4(),
  );

  const modelMatrix = enuMatrix.clone().invert();
  renderer.group.applyMatrix4(modelMatrix);
  renderer.group.updateMatrixWorld();

  group.add(renderer.group);

  return {
    lng,
    lat,
    height,
    size,
  };
}

function applyTilesetHeight(entry, heightOffset) {
  if (!entry || !entry.positionDegrees) {
    return;
  }

  const [lng, lat, baseHeight] = entry.positionDegrees;
  const targetVector = window.MaplibreThreePlugin.SceneTransform.lngLatToVector3(
    lng,
    lat,
    baseHeight + heightOffset,
  );

  entry.group.position.copy(targetVector);
  entry.heightOffset = heightOffset;
}

function shouldSyncGeomanEvent(event) {
  if (!event || typeof event !== 'object') {
    return false;
  }

  if (event.name === 'loaded') {
    return true;
  }

  const payload = event.payload;
  if (!payload || typeof payload !== 'object') {
    return false;
  }

  return Boolean(
    payload.feature ||
      payload.features ||
      payload.originalFeature ||
      payload.originalFeatures ||
      payload.geoJson ||
      payload.featureId ||
      payload.sourceId
  );
}

// Track ongoing collapse/expand operations to prevent rapid successive clicks
let geomanCollapseInProgress = false;

function applyGeomanCollapsedState(instance, collapsed) {
  if (!instance || !instance.control || !instance.control.container) {
    return;
  }

  // Prevent concurrent collapse/expand operations
  if (geomanCollapseInProgress) {
    return;
  }

  const container = instance.control.container;
  const isCollapsed = !container.querySelector('.gm-reactive-controls');
  const toggleButton = container.querySelector('.group-settings .gm-control-button');

  if (!toggleButton) {
    return;
  }

  // Check if we need to change state
  if ((collapsed && !isCollapsed) || (!collapsed && isCollapsed)) {
    // Set flag to prevent concurrent operations
    geomanCollapseInProgress = true;

    // Click the toggle button
    toggleButton.click();

    // Wait for DOM to update before allowing next operation
    setTimeout(() => {
      geomanCollapseInProgress = false;
    }, 200); // 200ms should be enough for the DOM to update
  }
}

// Layer Control class
class LayerControl {
  constructor(options, map, model, widgetEl) {
    this.options = options;
    this.map = map;
    this.model = model;
    this.widgetEl = widgetEl;
    this.collapsed = options.collapsed !== false;
    this.layerStates = options.layerStates || {};
    this.targetLayers = options.layers || Object.keys(this.layerStates);
    this.userInteractingWithSlider = false;
    this.panelWidth = options.panelWidth || 320;
    this.minPanelWidth = options.panelMinWidth || 240;
    this.maxPanelWidth = options.panelMaxWidth || 420;
    this.styleEditors = new Map();
    this.originalLayerStyles = new Map();
    this.activeStyleEditor = null;
    this.widthFrame = null;
    this.widthDragRectWidth = null;
    this.widthDragStartX = null;
    this.widthDragStartWidth = null;
    const legendConfig = (options && typeof options.legend === 'object' && options.legend) || {};
    const legendOptionsRaw = {
      ...(options.legendOptions || {}),
      ...(options.legend_options || {}),
      ...(
        legendConfig && typeof legendConfig.options === 'object'
          ? legendConfig.options
          : {}
      ),
    };
    this.legendOptions = legendOptionsRaw;
    this.legendPosition =
      legendConfig.position ||
      options.legendPosition ||
      options.legend_position ||
      'bottom-left';
    this.legendControlKey = `legend_${this.legendPosition}`;
    this.legendButtonRef = null;

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
    // Stroke-based inline SVG “layers” glyph (robust against background/foreground colors)
    icon.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" ' +
      'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<polygon points="12 3 3 8.25 12 13.5 21 8.25 12 3"></polygon>' +
      '<polyline points="3 12.75 12 18 21 12.75"></polyline>' +
      '<polyline points="3 17.25 12 22 21 17.25"></polyline>' +
      '</svg>';
    this.button.appendChild(icon);

    // Create panel
    this.panel = document.createElement('div');
    this.panel.className = 'layer-control-panel';
    this.applyPanelWidth(this.panelWidth, true);
    if (!this.collapsed) {
      this.panel.classList.add('expanded');
    }

    // Add header
    const header = document.createElement('div');
    header.className = 'layer-control-panel-header';

    const title = document.createElement('span');
    title.className = 'layer-control-panel-title';
    title.textContent = 'Layers';
    header.appendChild(title);

    const widthControl = document.createElement('label');
    widthControl.className = 'layer-control-width-control';
    widthControl.title = 'Adjust layer panel width';

    const widthLabel = document.createElement('span');
    widthLabel.textContent = 'Width';
    widthControl.appendChild(widthLabel);

    this.isWidthSliderActive = false;

    const widthSlider = document.createElement('div');
    widthSlider.className = 'layer-control-width-slider';
    widthSlider.setAttribute('role', 'slider');
    widthSlider.setAttribute('aria-valuemin', String(this.minPanelWidth));
    widthSlider.setAttribute('aria-valuemax', String(this.maxPanelWidth));
    widthSlider.setAttribute('aria-valuenow', String(this.panelWidth));
    widthSlider.setAttribute('aria-valuestep', '10');
    widthSlider.setAttribute('aria-label', 'Layer panel width');
    widthSlider.tabIndex = 0;

    const widthTrack = document.createElement('div');
    widthTrack.className = 'layer-control-width-track';
    const widthThumb = document.createElement('div');
    widthThumb.className = 'layer-control-width-thumb';

    widthSlider.appendChild(widthTrack);
    widthSlider.appendChild(widthThumb);

    widthSlider.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      const rect = widthSlider.getBoundingClientRect();
      this.widthDragRectWidth = rect.width || 1;
      this.widthDragStartX = event.clientX;
      this.widthDragStartWidth = this.panelWidth;
      this.isWidthSliderActive = true;
      widthSlider.setPointerCapture(event.pointerId);
      this.updateWidthFromPointer(event, true);
    });

    widthSlider.addEventListener('pointermove', (event) => {
      if (!this.isWidthSliderActive) {
        return;
      }
      this.updateWidthFromPointer(event);
    });

    const endPointerDrag = (event) => {
      if (!this.isWidthSliderActive) {
        return;
      }
      if (event.pointerId !== undefined) {
        try {
          widthSlider.releasePointerCapture(event.pointerId);
        } catch (error) {
          // Ignore release errors if pointer capture was lost
        }
      }
      this.isWidthSliderActive = false;
      this.widthDragRectWidth = null;
      this.widthDragStartX = null;
      this.widthDragStartWidth = null;
      this.updateWidthDisplay();
    };

    widthSlider.addEventListener('pointerup', endPointerDrag);
    widthSlider.addEventListener('pointercancel', endPointerDrag);
    widthSlider.addEventListener('lostpointercapture', endPointerDrag);

    const widthValue = document.createElement('span');
    widthValue.className = 'layer-control-width-value';

    widthControl.appendChild(widthSlider);
    widthControl.appendChild(widthValue);
    header.appendChild(widthControl);

    this.panel.appendChild(header);
    this.widthSliderEl = widthSlider;
    this.widthThumbEl = widthThumb;
    this.widthValueEl = widthValue;
    this.updateWidthDisplay();

    widthSlider.addEventListener('keydown', (event) => {
      let handled = true;
      const step = event.shiftKey ? 20 : 10;
      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowDown':
          this.applyPanelWidth(this.panelWidth - step, true);
          break;
        case 'ArrowRight':
        case 'ArrowUp':
          this.applyPanelWidth(this.panelWidth + step, true);
          break;
        case 'Home':
          this.applyPanelWidth(this.minPanelWidth, true);
          break;
        case 'End':
          this.applyPanelWidth(this.maxPanelWidth, true);
          break;
        case 'PageUp':
          this.applyPanelWidth(this.panelWidth + 50, true);
          break;
        case 'PageDown':
          this.applyPanelWidth(this.panelWidth - 50, true);
          break;
        default:
          handled = false;
      }
      if (handled) {
        event.preventDefault();
        this.updateWidthDisplay();
      }
    });

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
    this.styleEditors.clear();

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

    // Check if this is a marker group
    if (this.widgetEl._markerGroups && this.widgetEl._markerGroups.has(layerId)) {
      const markerGroup = this.widgetEl._markerGroups.get(layerId);
      if (markerGroup) {
        markerGroup.forEach((marker) => {
          const markerEl = marker.getElement();
          markerEl.style.display = visible ? '' : 'none';
        });
      }
    } else {
      // Regular layer - call map's visibility method
      this.map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
    }

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

    // Check if this is a marker group
    if (this.widgetEl._markerGroups && this.widgetEl._markerGroups.has(layerId)) {
      const markerGroup = this.widgetEl._markerGroups.get(layerId);
      if (markerGroup) {
        markerGroup.forEach((marker) => {
          const markerEl = marker.getElement();
          markerEl.style.opacity = opacity;
        });
      }
    } else {
      // Regular layer - apply opacity to map layer
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

        this.ensureStyleControls(layerId);

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

        if (this.styleEditors.has(layerId)) {
          this.updateStyleEditorValues(layerId);
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
          name: layerInfo.name || layerId
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

    const row = document.createElement('div');
    row.className = 'layer-control-row';

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
    opacity.dataset.role = 'opacity-slider';

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
    opacity.addEventListener('change', () => {
      if (layerId !== 'Background') {
        const payload = { opacity: parseFloat(opacity.value) };
        this.notifyStyleChange(layerId, payload);
      }
    });

    row.appendChild(checkbox);
    row.appendChild(name);
    row.appendChild(opacity);

    const styleButton = this.createStyleButton(layerId, state);
    if (styleButton) {
      row.appendChild(styleButton);
    }

    item.appendChild(row);
    this.ensureStyleControls(layerId);

    if (styleButton && !styleButton.disabled) {
      const styleEditor = this.createStyleEditor(layerId, state);
      if (styleEditor) {
        item.appendChild(styleEditor);
        this.styleEditors.set(layerId, styleEditor);
        this.updateStyleEditorValues(layerId);
      }
    }

    this.panel.appendChild(item);
  }

  ensureStyleControls(layerId) {
    const state = this.layerStates[layerId];
    if (!state || !this.panel) {
      return;
    }

    const items = this.panel.querySelectorAll('.layer-control-item');
    const item = Array.from(items).find((el) => el.dataset.layerId === layerId);
    if (!item) {
      return;
    }

    const row = item.querySelector('.layer-control-row');
    if (!row) {
      return;
    }

    let button = row.querySelector('.layer-control-style-button');
    const hasOptions = this.hasStyleOptions(layerId);

    if (!button) {
      button = this.createStyleButton(layerId, state);
      if (button) {
        row.appendChild(button);
      }
    }

    if (!button) {
      return;
    }

    const isMarkerGroup = this.widgetEl._markerGroups && this.widgetEl._markerGroups.has(layerId);

    if (hasOptions) {
      button.disabled = false;
      button.title = `Style ${state.name || layerId}`;

      if (!this.styleEditors.has(layerId)) {
        const styleEditor = this.createStyleEditor(layerId, state);
        if (styleEditor) {
          item.appendChild(styleEditor);
          this.styleEditors.set(layerId, styleEditor);
          this.updateStyleEditorValues(layerId);
        }
      }
    } else if (layerId === 'Background') {
      button.disabled = false;
      button.title = 'Show legend';
      button.classList.add('layer-control-legend-button');
      button.setAttribute('aria-label', 'Show legend');
      this.legendButtonRef = button;
      this.setLegendButtonState(this.isLegendControlPresent());
    } else if (isMarkerGroup) {
      button.disabled = true;
      button.title = 'Styling not available for marker groups';
      button.setAttribute('aria-label', 'Styling not available for marker groups');
    } else {
      button.disabled = true;
      button.title = 'Styling not available for this layer';
    }
  }

  hasStyleOptions(layerId) {
    if (!this.map || layerId === 'Background') {
      return false;
    }
    // Marker groups don't have style options
    if (this.widgetEl._markerGroups && this.widgetEl._markerGroups.has(layerId)) {
      return false;
    }
    try {
      const layer = this.map.getLayer(layerId);
      if (!layer) {
        return false;
      }
      return ['fill', 'line', 'circle', 'symbol', 'raster'].includes(layer.type);
    } catch (error) {
      console.warn(`Could not read layer type for ${layerId}:`, error);
      return false;
    }
  }

  createStyleButton(layerId, state) {
    const hasOptions = this.hasStyleOptions(layerId);
    const isMarkerGroup = this.widgetEl._markerGroups && this.widgetEl._markerGroups.has(layerId);

    // Don't create button for non-marker-group layers without options (except Background)
    if (!hasOptions && layerId !== 'Background' && !isMarkerGroup) {
      return null;
    }

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'layer-control-style-button';
    button.title = `Style ${state.name || layerId}`;
    button.setAttribute('aria-label', `Style ${state.name || layerId}`);
    button.innerHTML = '&#9881;';

    if (!hasOptions) {
      if (layerId === 'Background') {
        button.disabled = false;
        button.title = 'Show legend';
        button.setAttribute('aria-label', 'Show legend');
        button.classList.add('layer-control-legend-button');
        button.addEventListener('click', (event) => {
          event.stopPropagation();
          this.showLegendControl();
        });
        this.legendButtonRef = button;
        this.setLegendButtonState(this.isLegendControlPresent());
      } else if (isMarkerGroup) {
        // Marker groups: show disabled button for consistency
        button.disabled = true;
        button.title = 'Styling not available for marker groups';
        button.setAttribute('aria-label', 'Styling not available for marker groups');
      } else {
        button.disabled = true;
        button.title = 'Styling not available for this layer';
      }
    } else {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        this.toggleStyleEditor(layerId);
      });
    }
    return button;
  }

  createStyleEditor(layerId, state) {
    if (!this.hasStyleOptions(layerId)) {
      return null;
    }

    const mapLayer = this.map.getLayer(layerId);
    if (!mapLayer) {
      return null;
    }

    this.cacheOriginalLayerStyle(layerId, mapLayer);

    const editor = document.createElement('div');
    editor.className = 'layer-control-style-editor';
    editor.dataset.layerId = layerId;

    const header = document.createElement('div');
    header.className = 'layer-control-style-header';

    const title = document.createElement('span');
    title.textContent = `Style ${state.name || layerId}`;
    header.appendChild(title);

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'layer-control-style-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.title = 'Close style editor';
    closeBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      this.toggleStyleEditor(layerId, false);
    });
    header.appendChild(closeBtn);

    editor.appendChild(header);

    const controlsContainer = document.createElement('div');
    controlsContainer.className = 'layer-control-style-controls';

    const paint = mapLayer.paint || {};
    const type = mapLayer.type;

    const appendControl = (control) => {
      if (control) {
        controlsContainer.appendChild(control);
      }
    };

    switch (type) {
      case 'fill':
        appendControl(this.createColorControl('Fill Color', layerId, 'fill-color', paint['fill-color'] || '#3388ff'));
        appendControl(this.createSliderControl('Fill Opacity', layerId, 'fill-opacity', paint['fill-opacity'] ?? 0.5, 0, 1, 0.05));
        appendControl(this.createColorControl('Outline Color', layerId, 'fill-outline-color', paint['fill-outline-color'] || '#3388ff'));
        break;
      case 'line':
        appendControl(this.createColorControl('Line Color', layerId, 'line-color', paint['line-color'] || '#3388ff'));
        appendControl(this.createSliderControl('Line Width', layerId, 'line-width', paint['line-width'] ?? 2, 0, 20, 0.5));
        appendControl(this.createSliderControl('Line Opacity', layerId, 'line-opacity', paint['line-opacity'] ?? 1, 0, 1, 0.05));
        appendControl(this.createSliderControl('Line Blur', layerId, 'line-blur', paint['line-blur'] ?? 0, 0, 5, 0.1));
        break;
      case 'circle':
        appendControl(this.createColorControl('Fill Color', layerId, 'circle-color', paint['circle-color'] || '#3388ff'));
        appendControl(this.createSliderControl('Radius', layerId, 'circle-radius', paint['circle-radius'] ?? 5, 0, 40, 0.5));
        appendControl(this.createSliderControl('Opacity', layerId, 'circle-opacity', paint['circle-opacity'] ?? 1, 0, 1, 0.05));
        appendControl(this.createSliderControl('Blur', layerId, 'circle-blur', paint['circle-blur'] ?? 0, 0, 5, 0.1));
        appendControl(this.createColorControl('Stroke Color', layerId, 'circle-stroke-color', paint['circle-stroke-color'] || '#ffffff'));
        appendControl(this.createSliderControl('Stroke Width', layerId, 'circle-stroke-width', paint['circle-stroke-width'] ?? 1, 0, 10, 0.1));
        appendControl(this.createSliderControl('Stroke Opacity', layerId, 'circle-stroke-opacity', paint['circle-stroke-opacity'] ?? 1, 0, 1, 0.05));
        break;
      case 'symbol':
        appendControl(this.createColorControl('Text Color', layerId, 'text-color', paint['text-color'] || '#333333'));
        appendControl(this.createColorControl('Text Halo', layerId, 'text-halo-color', paint['text-halo-color'] || '#ffffff'));
        appendControl(this.createSliderControl('Halo Width', layerId, 'text-halo-width', paint['text-halo-width'] ?? 1, 0, 10, 0.25));
        appendControl(this.createSliderControl('Text Opacity', layerId, 'text-opacity', paint['text-opacity'] ?? 1, 0, 1, 0.05));
        appendControl(this.createSliderControl('Icon Opacity', layerId, 'icon-opacity', paint['icon-opacity'] ?? 1, 0, 1, 0.05));
        break;
      case 'raster':
        appendControl(this.createSliderControl('Opacity', layerId, 'raster-opacity', paint['raster-opacity'] ?? 1, 0, 1, 0.05));
        appendControl(this.createSliderControl('Brightness Min', layerId, 'raster-brightness-min', paint['raster-brightness-min'] ?? 0, -1, 1, 0.05));
        appendControl(this.createSliderControl('Brightness Max', layerId, 'raster-brightness-max', paint['raster-brightness-max'] ?? 1, -1, 1, 0.05));
        appendControl(this.createSliderControl('Saturation', layerId, 'raster-saturation', paint['raster-saturation'] ?? 0, -1, 1, 0.05));
        appendControl(this.createSliderControl('Contrast', layerId, 'raster-contrast', paint['raster-contrast'] ?? 0, -1, 1, 0.05));
        appendControl(this.createSliderControl('Hue Rotate', layerId, 'raster-hue-rotate', paint['raster-hue-rotate'] ?? 0, 0, 360, 5));
        break;
    }

    if (!controlsContainer.children.length) {
      const fallback = document.createElement('p');
      fallback.className = 'layer-control-style-empty';
      fallback.textContent = 'No editable style properties detected.';
      controlsContainer.appendChild(fallback);
    }

    editor.appendChild(controlsContainer);

    const actions = document.createElement('div');
    actions.className = 'layer-control-style-actions';

    const applyBtn = document.createElement('button');
    applyBtn.type = 'button';
    applyBtn.className = 'layer-control-style-action layer-control-style-apply';
    applyBtn.textContent = 'Apply';
    applyBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      this.applyStyleFromEditor(layerId);
    });

    const resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'layer-control-style-action layer-control-style-reset';
    resetBtn.textContent = 'Reset';
    resetBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      this.resetLayerStyle(layerId);
    });

    const closeBtnBottom = document.createElement('button');
    closeBtnBottom.type = 'button';
    closeBtnBottom.className = 'layer-control-style-action layer-control-style-close-secondary';
    closeBtnBottom.textContent = 'Close';
    closeBtnBottom.addEventListener('click', (event) => {
      event.stopPropagation();
      this.toggleStyleEditor(layerId, false);
    });

    actions.appendChild(applyBtn);
    actions.appendChild(resetBtn);
    actions.appendChild(closeBtnBottom);
    editor.appendChild(actions);

    return editor;
  }

  createColorControl(label, layerId, property, value) {
    const control = document.createElement('div');
    control.className = 'layer-style-control layer-style-control-color';

    const labelEl = document.createElement('label');
    labelEl.textContent = label;
    control.appendChild(labelEl);

    const inputGroup = document.createElement('div');
    inputGroup.className = 'layer-style-color-group';

    const liveValue = this.getCurrentPaintValue(layerId, property, value);
    this.recordOriginalPaintValue(layerId, property, liveValue);
    const normalized = this.normalizeColor(liveValue);

    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.className = 'layer-style-color';
    colorInput.value = normalized;
    colorInput.dataset.property = property;

    const textInput = document.createElement('input');
    textInput.type = 'text';
    textInput.className = 'layer-style-color-text';
    textInput.value = normalized;
    textInput.dataset.propertyDisplay = property;
    textInput.readOnly = true;

    colorInput.addEventListener('input', (event) => {
      const colorValue = event.target.value;
      textInput.value = colorValue;
      try {
        this.map.setPaintProperty(layerId, property, colorValue);
      } catch (error) {
        console.warn(`Failed to set ${property} for ${layerId}:`, error);
      }
    });

    colorInput.addEventListener('change', (event) => {
      this.notifyStyleChange(layerId, { [property]: event.target.value });
    });

    inputGroup.appendChild(colorInput);
    inputGroup.appendChild(textInput);
    control.appendChild(inputGroup);
    return control;
  }

  createSliderControl(label, layerId, property, value, min, max, step) {
    const liveValue = this.getCurrentPaintValue(layerId, property, value, min);
    this.recordOriginalPaintValue(layerId, property, liveValue);
    const control = document.createElement('div');
    control.className = 'layer-style-control layer-style-control-slider';

    const labelEl = document.createElement('label');
    labelEl.textContent = label;
    control.appendChild(labelEl);

    const sliderWrapper = document.createElement('div');
    sliderWrapper.className = 'layer-style-slider-wrapper';

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = min;
    slider.max = max;
    slider.step = step;
    slider.value = liveValue;
    slider.dataset.property = property;
    slider.className = 'layer-style-slider';

    const valueDisplay = document.createElement('span');
    valueDisplay.className = 'layer-style-value';
    valueDisplay.dataset.property = property;
    valueDisplay.textContent = this.formatNumericValue(liveValue, step);

    slider.addEventListener('input', (event) => {
      const newVal = parseFloat(event.target.value);
      valueDisplay.textContent = this.formatNumericValue(newVal, step);
      try {
        this.map.setPaintProperty(layerId, property, newVal);
      } catch (error) {
        console.warn(`Failed to set ${property} for ${layerId}:`, error);
      }
    });

    slider.addEventListener('change', (event) => {
      const newVal = parseFloat(event.target.value);
      this.notifyStyleChange(layerId, { [property]: newVal });
    });

    sliderWrapper.appendChild(slider);
    sliderWrapper.appendChild(valueDisplay);
    control.appendChild(sliderWrapper);
    return control;
  }

  toggleStyleEditor(layerId, forceState) {
    const editor = this.styleEditors.get(layerId);
    if (!editor) {
      return;
    }

    const shouldOpen = forceState !== undefined ? forceState : !editor.classList.contains('expanded');

    if (shouldOpen) {
      // Close others
      this.styleEditors.forEach((panel, id) => {
        if (id !== layerId) {
          panel.classList.remove('expanded');
        }
      });
      editor.classList.add('expanded');
      this.activeStyleEditor = layerId;
      this.updateStyleEditorValues(layerId);
    } else {
      editor.classList.remove('expanded');
      if (this.activeStyleEditor === layerId) {
        this.activeStyleEditor = null;
      }
    }
  }

  applyStyleFromEditor(layerId) {
    const editor = this.styleEditors.get(layerId);
    if (!editor) {
      return;
    }

    const inputs = editor.querySelectorAll('[data-property]');
    const updates = {};
    inputs.forEach((input) => {
      const property = input.dataset.property;
      if (!property) {
        return;
      }
      let value;
      if (input.type === 'color') {
        value = input.value;
      } else if (input.type === 'range') {
        value = parseFloat(input.value);
      } else {
        return;
      }
      try {
        this.map.setPaintProperty(layerId, property, value);
        updates[property] = value;
      } catch (error) {
        console.warn(`Failed to apply ${property} for ${layerId}:`, error);
      }
    });

    if (Object.keys(updates).length > 0) {
      this.notifyStyleChange(layerId, updates);
    }
    this.updateStyleEditorValues(layerId);
  }

  resetLayerStyle(layerId) {
    const original = this.originalLayerStyles.get(layerId);
    if (!original) {
      return;
    }

    const { paint } = original;
    const applied = {};

    Object.entries(paint).forEach(([property, value]) => {
      try {
        const restoredValue = this.clonePaintValue(value);
        this.map.setPaintProperty(layerId, property, restoredValue);
        applied[property] = restoredValue;
      } catch (error) {
        console.warn(`Failed to reset ${property} for ${layerId}:`, error);
      }
    });

    if (Object.keys(applied).length > 0) {
      this.notifyStyleChange(layerId, applied);
    }

    this.updateStyleEditorValues(layerId);
  }

  applyPanelWidth(width, immediate = false) {
    const clamped = Math.round(Math.min(this.maxPanelWidth, Math.max(this.minPanelWidth, width)));
    const applyWidth = () => {
      this.panelWidth = clamped;
      const px = `${clamped}px`;
      this.panel.style.width = px;
      this.updateWidthDisplay();
    };

    if (immediate) {
      applyWidth();
      return;
    }

    if (this.widthFrame) {
      cancelAnimationFrame(this.widthFrame);
    }
    this.widthFrame = requestAnimationFrame(() => {
      applyWidth();
      this.widthFrame = null;
    });
  }

  updateWidthFromPointer(event, resetBaseline = false) {
    if (!this.widthSliderEl) {
      return;
    }

    const sliderWidth = this.widthDragRectWidth || this.widthSliderEl.getBoundingClientRect().width || 1;
    const widthRange = this.maxPanelWidth - this.minPanelWidth;

    let width;
    if (resetBaseline) {
      const rect = this.widthSliderEl.getBoundingClientRect();
      const relative = rect.width > 0 ? (event.clientX - rect.left) / rect.width : 0;
      const clampedRatio = Math.min(1, Math.max(0, relative));
      width = this.minPanelWidth + clampedRatio * widthRange;
      this.widthDragStartWidth = width;
      this.widthDragStartX = event.clientX;
    } else {
      const delta = event.clientX - (this.widthDragStartX || event.clientX);
      width = (this.widthDragStartWidth || this.panelWidth) + (delta / sliderWidth) * widthRange;
    }

    this.applyPanelWidth(width, this.isWidthSliderActive);
  }

  updateWidthDisplay() {
    if (this.widthValueEl) {
      this.widthValueEl.textContent = `${this.panelWidth}px`;
    }
    if (this.widthSliderEl) {
      this.widthSliderEl.setAttribute('aria-valuenow', String(this.panelWidth));
      const ratio = (this.panelWidth - this.minPanelWidth) / (this.maxPanelWidth - this.minPanelWidth || 1);
      if (this.widthThumbEl) {
        const sliderWidth = this.widthSliderEl.clientWidth || 1;
        const thumbWidth = this.widthThumbEl.offsetWidth || 14;
        const padding = 16; // matches CSS left/right padding
        const available = Math.max(0, sliderWidth - padding - thumbWidth);
        const clampedRatio = Math.min(1, Math.max(0, ratio));
        const leftPx = 8 + available * clampedRatio;
        this.widthThumbEl.style.left = `${leftPx}px`;
      }
    }
  }

  ensureOriginalLayerEntry(layerId) {
    if (!this.originalLayerStyles.has(layerId)) {
      this.originalLayerStyles.set(layerId, { paint: {} });
    }
    return this.originalLayerStyles.get(layerId);
  }

  recordOriginalPaintValue(layerId, property, value) {
    if (value === undefined || value === null) {
      return;
    }
    const original = this.ensureOriginalLayerEntry(layerId);
    if (property in original.paint) {
      return;
    }
    original.paint[property] = this.clonePaintValue(value);
  }

  getCurrentPaintValue(layerId, property, fallback, numericDefault) {
    let value;
    try {
      value = this.map.getPaintProperty(layerId, property);
    } catch (error) {
      value = undefined;
    }

    if (value === undefined || value === null) {
      if (fallback !== undefined) {
        value = fallback;
      } else if (numericDefault !== undefined) {
        value = numericDefault;
      }
    }

    if (numericDefault !== undefined && typeof numericDefault === 'number') {
      if (typeof value !== 'number') {
        const parsed = Number(value);
        value = Number.isNaN(parsed) ? numericDefault : parsed;
      }
    }

    if (typeof value === 'number' && Number.isNaN(value)) {
      value = numericDefault !== undefined ? numericDefault : 0;
    }

    return value;
  }

  clonePaintValue(value) {
    if (Array.isArray(value)) {
      return value.map((item) => this.clonePaintValue(item));
    }
    if (value && typeof value === 'object') {
      try {
        return JSON.parse(JSON.stringify(value));
      } catch (error) {
        return value;
      }
    }
    return value;
  }

  cacheOriginalLayerStyle(layerId, mapLayer) {
    if (!mapLayer) {
      return;
    }
    const original = this.ensureOriginalLayerEntry(layerId);
    const paintKeys = Object.keys(mapLayer.paint || {});
    paintKeys.forEach((prop) => {
      const value = this.getCurrentPaintValue(layerId, prop, mapLayer.paint[prop]);
      this.recordOriginalPaintValue(layerId, prop, value);
    });
    // Ensure entry exists even if no paint keys were discovered
    this.originalLayerStyles.set(layerId, original);
  }

  updateStyleEditorValues(layerId) {
    const editor = this.styleEditors.get(layerId);
    if (!editor || !this.map) {
      return;
    }
    let mapLayer;
    try {
      mapLayer = this.map.getLayer(layerId);
    } catch (error) {
      console.warn(`Failed to access layer ${layerId} for style sync:`, error);
      return;
    }
    if (!mapLayer) {
      return;
    }

    const inputs = editor.querySelectorAll('[data-property]');
    inputs.forEach((input) => {
      const property = input.dataset.property;
      if (!property) {
        return;
      }

      let currentValue;
      try {
        currentValue = this.map.getPaintProperty(layerId, property);
      } catch (error) {
        return;
      }

      if (currentValue === undefined) {
        return;
      }

      if (input.type === 'color') {
        const normalized = this.normalizeColor(currentValue);
        input.value = normalized;
        const textInput = editor.querySelector(`input.layer-style-color-text[data-property-display="${property}"]`);
        if (textInput) {
          textInput.value = normalized;
        }
      } else if (input.type === 'range' && typeof currentValue === 'number') {
        input.value = currentValue;
        const display = editor.querySelector(`span.layer-style-value[data-property="${property}"]`);
        if (display) {
          display.textContent = this.formatNumericValue(currentValue, parseFloat(input.step || '1'));
        }
      }
    });
  }

  normalizeColor(value) {
    if (typeof value === 'string') {
      if (value.startsWith('#')) {
        return value;
      }
      if (value.startsWith('rgb')) {
        const match = value.match(/\d+/g);
        if (match && match.length >= 3) {
          const [r, g, b] = match.map((num) => parseInt(num, 10));
          return this.rgbToHex(r, g, b);
        }
      }
    } else if (Array.isArray(value) && value.length >= 3) {
      return this.rgbToHex(value[0], value[1], value[2]);
    }
    return '#3388ff';
  }

  rgbToHex(r, g, b) {
    const clamp = (v) => Math.max(0, Math.min(255, Math.round(v)));
    const toHex = (v) => {
      const hex = clamp(v).toString(16);
      return hex.length === 1 ? `0${hex}` : hex;
    };
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  }

  formatNumericValue(value, step) {
    let decimals = 0;
    if (step && Number(step) !== 1) {
      const stepNumber = Number(step);
      if (stepNumber > 0 && stepNumber < 1) {
        decimals = Math.min(4, Math.ceil(Math.abs(Math.log10(stepNumber))));
      }
    }
    return value.toFixed(decimals);
  }

  notifyStyleChange(layerId, styleUpdates) {
    if (!styleUpdates || Object.keys(styleUpdates).length === 0 || !this.model) {
      return;
    }
    try {
      const currentEvents = this.model.get('_js_events') || [];
      const eventPayload = {
        type: 'layer_style_changed',
        layerId: layerId,
        style: styleUpdates
      };
      this.model.set('_js_events', [...currentEvents, eventPayload]);
      this.model.save_changes();
    } catch (error) {
      console.warn('Failed to notify layer style change:', error);
    }
  }

  isLegendControlPresent() {
    if (!this.widgetEl || !this.widgetEl._controls) {
      return false;
    }
    return this.widgetEl._controls.has(this.legendControlKey);
  }

  setLegendButtonState(active) {
    if (!this.legendButtonRef) {
      return;
    }
    if (active) {
      this.legendButtonRef.classList.add('layer-control-legend-active');
      this.legendButtonRef.setAttribute('aria-pressed', 'true');
    } else {
      this.legendButtonRef.classList.remove('layer-control-legend-active');
      this.legendButtonRef.removeAttribute('aria-pressed');
    }
  }

  syncLegendControlTrait(controlKey, legendOptions) {
    if (!this.model || typeof this.model.get !== 'function') {
      return;
    }
    try {
      const currentControls = this.model.get('_controls') || {};
      if (currentControls[controlKey]) {
        return;
      }
      const nextControls = { ...currentControls };
      nextControls[controlKey] = {
        type: 'legend',
        position: this.legendPosition,
        options: { position: this.legendPosition, ...(legendOptions || {}) },
      };
      this.model.set('_controls', nextControls);
      this.model.save_changes();
    } catch (error) {
      console.warn('Failed to sync legend control state:', error);
    }
  }

  openLegendContainer(controlKey, retries = 10) {
    if (!this.widgetEl || !this.widgetEl._controls) {
      if (retries > 0) {
        setTimeout(() => this.openLegendContainer(controlKey, retries - 1), 150);
      }
      return;
    }

    const control = this.widgetEl._controls.get(controlKey);
    if (!control) {
      if (retries > 0) {
        setTimeout(() => this.openLegendContainer(controlKey, retries - 1), 150);
      } else {
        this.setLegendButtonState(false);
      }
      return;
    }

    const legendState =
      control._anymapLegendState ||
      (typeof control.getState === 'function' ? control.getState() : null);
    const container =
      (legendState && legendState.container) ||
      (typeof control.getContainer === 'function' ? control.getContainer() : null);

    if (!container || !(container instanceof HTMLElement)) {
      if (retries > 0) {
        setTimeout(() => this.openLegendContainer(controlKey, retries - 1), 150);
      }
      return;
    }

    const panel = container.querySelector('.mapboxgl-legend-list');
    const toggleButton = container.querySelector('.mapboxgl-legend-switcher');
    const closeButton = container.querySelector('.mapboxgl-legend-close-button');

    this.configureLegendInteractions(container, panel, toggleButton, closeButton);

    const state = (this.widgetEl && this.widgetEl._controls && this.widgetEl._controls.get(controlKey)?._anymapLegendState) || legendState;
    const triggerRefresh = () => {
      if (state && typeof state.base?.updateLegendControl === 'function') {
        try {
          state.base.updateLegendControl();
        } catch (error) {
          console.debug('Legend refresh on open failed:', error);
        }
      } else if (control && typeof control.refreshLegend === 'function') {
        try {
          control.refreshLegend();
        } catch (error) {
          console.debug('Legend refresh via control failed:', error);
        }
      }
    };

    triggerRefresh();
    if (this.map && typeof this.map.once === 'function') {
      this.map.once('idle', () => triggerRefresh());
    }
  }

  configureLegendInteractions(container, panel, toggleButton, closeButton) {
    if (!container) {
      return;
    }

    const setVisibility = (visible, force) => {
      if (panel) {
        panel.style.display = visible ? 'block' : 'none';
      }
      if (toggleButton) {
        toggleButton.setAttribute('aria-expanded', visible ? 'true' : 'false');
        toggleButton.classList.toggle('anymap-legend-toggle-collapsed', !visible);
        toggleButton.classList.toggle('anymap-legend-toggle-expanded', visible);
      }
      if (visible || force) {
        this.setLegendButtonState(true);
      } else {
        this.setLegendButtonState(false);
      }
      if (container) {
        container.classList.toggle('anymap-legend-collapsed', !visible);
      }
      if (toggleButton) {
        toggleButton.style.margin = visible ? '0 0 6px 0' : '0';
      }
    };

    setVisibility(true, true);

    if (toggleButton && !toggleButton.__anymapLegendToggleHook) {
      toggleButton.__anymapLegendToggleHook = true;
      toggleButton.style.display = 'inline-flex';
      if (!toggleButton.getAttribute('aria-label')) {
        toggleButton.setAttribute('aria-label', 'Toggle legend');
      }
      const toggleHandler = (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        const isVisible = panel ? panel.style.display !== 'none' : false;
        setVisibility(!isVisible);
        if (!isVisible) {
          const state =
            (this.widgetEl && this.widgetEl._controls && this.widgetEl._controls.get(this.legendControlKey)?._anymapLegendState) ||
            null;
          if (state && typeof state.base?.updateLegendControl === 'function') {
            try {
              state.base.updateLegendControl();
            } catch (error) {
              console.debug('Legend refresh on expand failed:', error);
            }
          }
        }
      };
      toggleButton.addEventListener('click', toggleHandler, { capture: true });
    }

    if (closeButton && !closeButton.__anymapLegendCloseHook) {
      closeButton.__anymapLegendCloseHook = true;
      closeButton.title = 'Remove legend';
      closeButton.setAttribute('aria-label', 'Remove legend');
      closeButton.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        this.removeLegendControl();
      });
    }
  }

  showLegendControl() {
    const legendOptions = { ...(this.legendOptions || {}) };
    const ensureOption = (primary, alternate, value) => {
      if (!(primary in legendOptions) && (!alternate || !(alternate in legendOptions))) {
        legendOptions[primary] = value;
      }
    };
    ensureOption('showDefault', 'show_default', true);
    ensureOption('onlyRendered', 'only_rendered', true);
    this.legendOptions = { ...legendOptions };

    const controlsMap = this.widgetEl && this.widgetEl._controls;

    if (!controlsMap || !controlsMap.has(this.legendControlKey)) {
      if (!this.widgetEl) {
        console.warn('Widget element not available; unable to add legend control.');
        return;
      }
      scheduleLegendInitialization(
        this.legendControlKey,
        { position: this.legendPosition, options: legendOptions },
        this.map,
        this.widgetEl,
      );
      this.syncLegendControlTrait(this.legendControlKey, legendOptions);
      this.setLegendButtonState(true);
      this.openLegendContainer(this.legendControlKey, 12);
      return;
    }

    this.setLegendButtonState(true);
    this.openLegendContainer(this.legendControlKey, 6);
  }

  removeLegendControl() {
    const controlsMap = this.widgetEl && this.widgetEl._controls;
    let control = null;

    if (controlsMap && controlsMap.has(this.legendControlKey)) {
      control = controlsMap.get(this.legendControlKey);
      try {
        if (control && this.map && typeof this.map.removeControl === 'function') {
          this.map.removeControl(control);
        }
      } catch (error) {
        console.warn('Failed to remove legend control from map:', error);
      }
      controlsMap.delete(this.legendControlKey);
      if (control && control._anymapLegendState && typeof control._anymapLegendState.cleanup === 'function') {
        control._anymapLegendState.cleanup();
      }
    }

    if (this.model && typeof this.model.get === 'function') {
      try {
        const currentControls = { ...(this.model.get('_controls') || {}) };
        if (currentControls[this.legendControlKey]) {
          delete currentControls[this.legendControlKey];
          this.model.set('_controls', currentControls);
          this.model.save_changes();
        }
      } catch (error) {
        console.warn('Failed to sync legend removal:', error);
      }
    }

    this.setLegendButtonState(false);
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

class WidgetPanelControl {
  constructor(options = {}, map, model) {
    this.options = options;
    this.map = map;
    this.model = model;
    this.controlId = options.control_id || `widget-panel-${Math.random().toString(36).slice(2)}`;
    this.collapsed = options.collapsed !== false;
    this.position = options.position || 'top-right';
    this.widgetModelId = options.widget_model_id;
    this.panelWidth = options.panelWidth || 320;
    this.panelMinWidth = options.panelMinWidth || 220;
    this.panelMaxWidth = options.panelMaxWidth || 420;

    this.container = document.createElement('div');
    this.container.className = 'maplibregl-ctrl maplibregl-ctrl-group maplibregl-ctrl-widget-panel';

    this.button = document.createElement('button');
    this.button.type = 'button';
    this.button.className = 'widget-panel-toggle';
    const buttonLabel = options.description || options.label || 'Widget panel';
    this.button.title = buttonLabel;
    this.button.setAttribute('aria-label', buttonLabel);
    this.button.setAttribute('aria-expanded', (!this.collapsed).toString());

    const iconSpan = document.createElement('span');
    iconSpan.className = 'widget-panel-toggle-icon';
    iconSpan.textContent = options.icon || '⋮';
    this.button.appendChild(iconSpan);

    this.button.addEventListener('click', () => this.toggle());
    this.container.appendChild(this.button);

    this.panel = document.createElement('div');
    this.panel.className = 'widget-panel';
    this.panel.style.minWidth = `${this.panelMinWidth}px`;
    this.panel.style.maxWidth = `${this.panelMaxWidth}px`;
    this.panel.style.width = `${this.panelWidth}px`;
    this.panel.style.maxHeight = options.maxHeight || '70vh';

    if (this.position.startsWith('top')) {
      this.panel.style.top = '34px';
      this.panel.style.bottom = 'auto';
      this.panel.style.marginTop = '4px';
      this.panel.style.marginBottom = '0';
    } else {
      this.panel.style.bottom = '34px';
      this.panel.style.top = 'auto';
      this.panel.style.marginTop = '0';
      this.panel.style.marginBottom = '4px';
    }

    if (this.position.endsWith('left')) {
      this.panel.style.left = '0';
      this.panel.style.right = 'auto';
    } else {
      this.panel.style.right = '0';
      this.panel.style.left = 'auto';
    }

    if (this.collapsed) {
      this.panel.style.display = 'none';
    } else {
      this.panel.classList.add('expanded');
    }

    const header = document.createElement('div');
    header.className = 'widget-panel-header';

    const title = document.createElement('span');
    title.className = 'widget-panel-title';
    title.textContent = options.label || 'Widget Panel';
    header.appendChild(title);

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'widget-panel-close';
    closeButton.setAttribute('aria-label', 'Collapse widget panel');
    closeButton.innerHTML = '&times;';
    closeButton.addEventListener('click', () => this.collapse());
    header.appendChild(closeButton);

    this.panel.appendChild(header);

    this.content = document.createElement('div');
    this.content.className = 'widget-panel-content';
    this.panel.appendChild(this.content);

    this.container.appendChild(this.panel);

    this.widgetView = null;
    if (this.widgetModelId) {
      this.attachWidgetView(this.widgetModelId);
    }
  }

  async attachWidgetView(modelId) {
    if (!modelId) {
      return;
    }

    if (!this.model || !this.model.widget_manager) {
      console.warn('Widget manager not available for widget panel');
      return;
    }

    try {
      const widgetModel = await this.model.widget_manager.get_model(modelId);
      if (!widgetModel) {
        console.warn(`Widget model ${modelId} not found`);
        return;
      }

      const view = await this.model.widget_manager.create_view(widgetModel);

      this.disposeWidgetView();
      this.widgetView = view;

      this.content.innerHTML = '';
      if (typeof view.render === 'function') {
        await view.render();
      }
      this.content.appendChild(view.el);
      if (typeof view.trigger === 'function') {
        view.trigger('displayed');
      }
      this.content.classList.add('widget-panel-content-loaded');
    } catch (error) {
      console.error('Failed to attach widget panel view:', error);
    }
  }

  disposeWidgetView() {
    if (this.widgetView) {
      if (typeof this.widgetView.remove === 'function') {
        this.widgetView.remove();
      } else if (this.widgetView.el && this.widgetView.el.parentNode) {
        this.widgetView.el.parentNode.removeChild(this.widgetView.el);
      }
      this.widgetView = null;
    }
  }

  toggle() {
    if (this.collapsed) {
      this.expand();
    } else {
      this.collapse();
    }
  }

  expand() {
    if (!this.collapsed) {
      return;
    }
    this.collapsed = false;
    this.panel.style.display = 'block';
    requestAnimationFrame(() => {
      this.panel.classList.add('expanded');
    });
    this.button.setAttribute('aria-expanded', 'true');
  }

  collapse() {
    if (this.collapsed) {
      return;
    }
    this.collapsed = true;
    this.panel.classList.remove('expanded');
    this.button.setAttribute('aria-expanded', 'false');
    setTimeout(() => {
      if (this.collapsed) {
        this.panel.style.display = 'none';
      }
    }, 180);
  }

  onAdd(map) {
    this.map = map;
    return this.container;
  }

  onRemove() {
    this.disposeWidgetView();
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }
    this.map = null;
  }
}

function render({ model, el }) {
  const debugEnabled =
    (typeof window !== 'undefined' && Boolean(window.ANYMAP_DEBUG)) ||
    Boolean(model.get('_debug_logging'));
  const debugLog = (...args) => {
    if (debugEnabled) {
      console.log(...args);
    }
  };

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
  el.style.height = model.get("height");
  el.style.display = "block";
  el.style.margin = "0";
  el.style.padding = "0";
  el.style.overflow = "hidden";

  // Clear any existing content and cleanup
  if (el._map) {
    el._map.remove();
    el._map = null;
  }
  if (el._markers) {
    el._markers.forEach(marker => marker.remove());
    el._markers = [];
  }
  if (el._markerGroups) {
    el._markerGroups.forEach(markerGroup => {
      markerGroup.forEach(marker => marker.remove());
    });
    el._markerGroups.clear();
  }
  if (el._geomanInstance && typeof el._geomanInstance.destroy === 'function') {
    try {
      el._geomanInstance.destroy({ removeSources: true });
    } catch (error) {
      console.warn('Failed to destroy existing Geoman instance:', error);
    }
  }
  el._geomanInstance = null;
  el._geomanPromise = null;
  el._geomanEventListener = null;
  if (el._geomanModelListener) {
    model.off("change:geoman_data", el._geomanModelListener);
    el._geomanModelListener = null;
  }
  el._geomanSyncFromJs = false;
  el._pendingGeomanData = normalizeGeomanGeoJson(model.get("geoman_data"));

  el.innerHTML = "";
  el.appendChild(container);

  // Load and register protocols dynamically
  const loadProtocols = async () => {
    try {
      // Load MapLibre GL JS first
      if (!window.maplibregl) {
        const maplibreScript = document.createElement('script');
        maplibreScript.src = 'https://unpkg.com/maplibre-gl@5.10.0/dist/maplibre-gl.js';

        const previousDefine = window.define;
        const previousModule = window.module;
        const previousExports = window.exports;
        const hadAMDDefine = !!(previousDefine && previousDefine.amd);
        const hadModule = typeof previousModule !== 'undefined';
        const hadExports = typeof previousExports !== 'undefined';

        const restoreModuleEnv = () => {
          if (hadAMDDefine) {
            window.define = previousDefine;
          } else {
            delete window.define;
          }
          if (hadModule) {
            window.module = previousModule;
          } else {
            delete window.module;
          }
          if (hadExports) {
            window.exports = previousExports;
          } else {
            delete window.exports;
          }
        };

        if (hadAMDDefine) {
          window.define = undefined;
        }
        if (hadModule) {
          window.module = undefined;
        }
        if (hadExports) {
          window.exports = undefined;
        }

        await new Promise((resolve, reject) => {
          maplibreScript.onload = () => {
            restoreModuleEnv();
            resolve();
          };
          maplibreScript.onerror = (error) => {
            restoreModuleEnv();
            reject(error);
          };
          document.head.appendChild(maplibreScript);
        });

        if (
          !window.maplibregl &&
          typeof window.define === 'function' &&
          window.define.amd &&
          typeof window.require === 'function'
        ) {
          // Fallback for environments (e.g. VS Code notebooks) that force AMD loading
          window.maplibregl = await new Promise((resolve, reject) => {
            try {
              window.require(['maplibre-gl'], (module) => {
                if (module && module.default) {
                  resolve(module.default);
                } else {
                  resolve(module);
                }
              }, reject);
            } catch (err) {
              reject(err);
            }
          });
        }

        if (!window.maplibregl) {
          throw new Error('MapLibre GL JS failed to load');
        }

        if (!window.mapboxgl) {
          window.mapboxgl = window.maplibregl;
        }

        console.log("MapLibre GL JS loaded successfully");
      }

      if (!window.mapboxgl && window.maplibregl) {
        window.mapboxgl = window.maplibregl;
      }

      // Load MapLibre GL CSS
      if (!document.querySelector('link[href*="maplibre-gl.css"]')) {
        const maplibreCSS = document.createElement('link');
        maplibreCSS.rel = 'stylesheet';
        maplibreCSS.href = 'https://unpkg.com/maplibre-gl@5.10.0/dist/maplibre-gl.css';
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

      // Load MapLibre GL Export Control
      if (!resolveExportControlClass()) {
        const exportScript = document.createElement('script');
        exportScript.src = 'https://cdn.jsdelivr.net/npm/@watergis/maplibre-gl-export@4.1.0/dist/maplibre-gl-export.umd.js';

        const previousDefine = window.define;
        const previousModule = window.module;
        const previousExports = window.exports;
        const hadAMDDefine = !!(previousDefine && previousDefine.amd);
        const hadModule = typeof previousModule !== 'undefined';
        const hadExports = typeof previousExports !== 'undefined';

        const restoreModuleEnv = () => {
          if (hadAMDDefine) {
            window.define = previousDefine;
          } else {
            delete window.define;
          }
          if (hadModule) {
            window.module = previousModule;
          } else {
            delete window.module;
          }
          if (hadExports) {
            window.exports = previousExports;
          } else {
            delete window.exports;
          }
        };

        if (hadAMDDefine) {
          window.define = undefined;
        }
        if (hadModule) {
          window.module = undefined;
        }
        if (hadExports) {
          window.exports = undefined;
        }

        await new Promise((resolve, reject) => {
          exportScript.onload = () => {
            restoreModuleEnv();
            resolve();
          };
          exportScript.onerror = (error) => {
            restoreModuleEnv();
            reject(error);
          };
          document.head.appendChild(exportScript);
        });

        if (!resolveExportControlClass()) {
          console.warn('MapLibre export control failed to load - export functionality unavailable');
        }
      }

      if (!document.querySelector('link[href*="maplibre-gl-export.css"]')) {
        const exportCSS = document.createElement('link');
        exportCSS.rel = 'stylesheet';
        exportCSS.href = 'https://cdn.jsdelivr.net/npm/@watergis/maplibre-gl-export@4.1.0/dist/maplibre-gl-export.css';
        document.head.appendChild(exportCSS);
      }

      if (!resolveGeomanNamespace()) {
        const geomanScript = document.createElement('script');
        geomanScript.src = 'https://cdn.jsdelivr.net/npm/@geoman-io/maplibre-geoman-free@latest/dist/maplibre-geoman.umd.js';

        const previousDefine = window.define;
        const previousModule = window.module;
        const previousExports = window.exports;
        const hadAMDDefine = !!(previousDefine && previousDefine.amd);
        const hadModule = typeof previousModule !== 'undefined';
        const hadExports = typeof previousExports !== 'undefined';

        const restoreModuleEnv = () => {
          if (hadAMDDefine) {
            window.define = previousDefine;
          } else {
            delete window.define;
          }
          if (hadModule) {
            window.module = previousModule;
          } else {
            delete window.module;
          }
          if (hadExports) {
            window.exports = previousExports;
          } else {
            delete window.exports;
          }
        };

        if (hadAMDDefine) {
          window.define = undefined;
        }
        if (hadModule) {
          window.module = undefined;
        }
        if (hadExports) {
          window.exports = undefined;
        }

        await new Promise((resolve, reject) => {
          geomanScript.onload = () => {
            restoreModuleEnv();
            resolve();
          };
          geomanScript.onerror = (error) => {
            restoreModuleEnv();
            reject(error);
          };
          document.head.appendChild(geomanScript);
        });

        if (!resolveGeomanNamespace()) {
          console.warn('MapLibre Geoman plugin failed to load - geospatial editing unavailable');
        }
      }

      if (!document.querySelector('link[href*="maplibre-geoman.css"]')) {
        const geomanCSS = document.createElement('link');
        geomanCSS.rel = 'stylesheet';
        geomanCSS.href = 'https://cdn.jsdelivr.net/npm/@geoman-io/maplibre-geoman-free@latest/dist/maplibre-geoman.css';
        document.head.appendChild(geomanCSS);
      }

      // Load MapLibre GL Temporal Control
      if (!window.TemporalControl) {
        const temporalScript = document.createElement('script');
        temporalScript.type = 'module';
        temporalScript.textContent = `
          import TemporalControl from 'https://www.unpkg.com/maplibre-gl-temporal-control@1.2.0/build/index.js';
          window.TemporalControl = TemporalControl;
        `;
        document.head.appendChild(temporalScript);

        // Wait for the module to load
        await new Promise((resolve) => {
          const checkLoaded = setInterval(() => {
            if (window.TemporalControl) {
              clearInterval(checkLoaded);
              resolve();
            }
          }, 50);
          // Timeout after 5 seconds
          setTimeout(() => {
            clearInterval(checkLoaded);
            if (!window.TemporalControl) {
              console.warn('MapLibre Temporal Control failed to load - temporal animation unavailable');
            }
            resolve();
          }, 5000);
        });
      }

      if (!document.querySelector('link[href*="maplibre-gl-temporal-control"]')) {
        const temporalCSS = document.createElement('link');
        temporalCSS.rel = 'stylesheet';
        temporalCSS.href = 'https://www.unpkg.com/maplibre-gl-temporal-control@1.2.0/build/style.css';
        document.head.appendChild(temporalCSS);
      }

      // Load MapLibre GL Measures plugin
      if (!window.MeasuresControl) {
        // Temporarily disable AMD/CommonJS globals to encourage UMD builds to attach to window
        const previousDefine = window.define;
        const previousModule = window.module;
        const previousExports = window.exports;
        const hadAMDDefine = typeof previousDefine === 'function' && previousDefine.amd;
        const hadModule = typeof previousModule !== 'undefined';
        const hadExports = typeof previousExports !== 'undefined';

        const restoreModuleEnv = () => {
          if (hadAMDDefine) window.define = previousDefine;
          if (hadModule) window.module = previousModule;
          else delete window.module;
          if (hadExports) window.exports = previousExports;
          else delete window.exports;
        };

        const tryLoadScript = (src) => new Promise((resolve) => {
          const s = document.createElement('script');
          s.src = src;
          s.onload = () => resolve({ ok: true, src });
          s.onerror = () => resolve({ ok: false, src });
          document.head.appendChild(s);
        });

        const candidateScripts = [
          'https://cdn.jsdelivr.net/npm/maplibre-gl-measures@latest/dist/maplibre-gl-measures.min.js',
          'https://unpkg.com/maplibre-gl-measures@latest/dist/maplibre-gl-measures.min.js',
          'https://unpkg.com/maplibre-gl-measures@latest/dist/maplibre-gl-measures.js',
          'https://unpkg.com/maplibre-gl-measures@latest/dist/index.umd.js',
        ];

        let loaded = false;
        for (const src of candidateScripts) {
          // Disable AMD before injecting each attempt
          if (hadAMDDefine) window.define = undefined;
          if (hadModule) window.module = undefined;
          if (hadExports) window.exports = undefined;

          const result = await tryLoadScript(src);
          restoreModuleEnv();
          if (result.ok && (window.MeasuresControl || (window.maplibregl && window.maplibregl.MeasuresControl))) {
            if (!window.MeasuresControl && window.maplibregl?.MeasuresControl) {
              window.MeasuresControl = window.maplibregl.MeasuresControl;
            }
            loaded = true;
            break;
          }
        }

        // Disable AMD before injecting script
        if (hadAMDDefine) window.define = undefined;
        if (hadModule) window.module = undefined;
        if (hadExports) window.exports = undefined;

        // ESM fallback via dynamic import if still unavailable
        if (!loaded && !window.MeasuresControl) {
          try {
            const measuresModule = await import('https://esm.sh/maplibre-gl-measures@latest');
            const ctor = measuresModule?.default || measuresModule?.MeasuresControl || measuresModule?.Measures;
            if (ctor) {
              window.MeasuresControl = ctor;
              loaded = true;
            }
          } catch (e) {
            // ignore, will warn below
          }
        }

        if (window.MeasuresControl) {
          debugLog("MapLibre GL Measures loaded successfully");
        } else {
          console.warn('MapLibre GL Measures plugin failed to load - measurement tools unavailable');
        }
      }

      if (!document.querySelector('link[href*="maplibre-gl-measures.css"]')) {
        const measuresCSS = document.createElement('link');
        measuresCSS.rel = 'stylesheet';
        measuresCSS.href = 'https://cdn.jsdelivr.net/npm/maplibre-gl-measures@latest/dist/maplibre-gl-measures.css';
        document.head.appendChild(measuresCSS);
      }

      // Load GeoGrid plugin
      if (!resolveGeoGridClass()) {
        try {
          // Load GeoGrid as ES module via dynamic import
          const geoGridModule = await import('https://unpkg.com/geogrid-maplibre-gl@latest');
          window.GeoGrid = geoGridModule.GeoGrid || geoGridModule.default || geoGridModule;

          if (!resolveGeoGridClass()) {
            console.warn('GeoGrid plugin loaded but class not found - grid functionality unavailable');
          }
        } catch (error) {
          console.warn('Failed to load GeoGrid plugin:', error);
        }
      }

      if (!document.querySelector('link[href*="geogrid.css"]')) {
        const geogridCSS = document.createElement('link');
        geogridCSS.rel = 'stylesheet';
        geogridCSS.href = 'https://unpkg.com/geogrid-maplibre-gl@latest/dist/geogrid.css';
        document.head.appendChild(geogridCSS);

      }

      // Load InfoBox plugin (works with MapLibre)
      if (!window.MapboxInfoBoxControl || !window.MapboxGradientBoxControl) {
        const prevDefine = window.define;
        const prevModule = window.module;
        const prevExports = window.exports;
        const hadAMD = typeof prevDefine === 'function' && prevDefine.amd;
        const hadMod = typeof prevModule !== 'undefined';
        const hadExp = typeof prevExports !== 'undefined';

        const restoreEnv = () => {
          if (hadAMD) window.define = prevDefine; else delete window.define;
          if (hadMod) window.module = prevModule; else delete window.module;
          if (hadExp) window.exports = prevExports; else delete window.exports;
        };

        const tryLoad = (src) => new Promise((resolve) => {
          const s = document.createElement('script');
          s.src = src;
          s.onload = () => resolve({ ok: true, src });
          s.onerror = () => resolve({ ok: false, src });
          document.head.appendChild(s);
        });

        const candidates = [
          // infobox-control package
          'https://cdn.jsdelivr.net/npm/infobox-control@latest/dist/index.umd.js',
          'https://unpkg.com/infobox-control@latest/dist/index.umd.js',
          // alternative package name
          'https://cdn.jsdelivr.net/npm/mapbox-gl-infobox@latest/dist/index.umd.js',
          'https://unpkg.com/mapbox-gl-infobox@latest/dist/index.umd.js',
        ];

        let loaded = false;
        for (const src of candidates) {
          if (hadAMD) window.define = undefined;
          if (hadMod) window.module = undefined;
          if (hadExp) window.exports = undefined;

          /* eslint-disable no-await-in-loop */
          const result = await tryLoad(src);
          restoreEnv();
          if (result.ok && (window.MapboxInfoBoxControl || window.MapboxGradientBoxControl)) {
            loaded = true;
            break;
          }
        }

        if (!loaded && (!window.MapboxInfoBoxControl || !window.MapboxGradientBoxControl)) {
          try {
            let mod;
            try { mod = await import('https://esm.sh/infobox-control@latest'); } catch (_) {}
            if (!mod) {
              try { mod = await import('https://esm.sh/mapbox-gl-infobox@latest'); } catch (e2) { throw e2; }
            }
            const InfoCtor = mod?.MapboxInfoBoxControl || mod?.InfoBoxControl || mod?.default?.MapboxInfoBoxControl;
            const GradCtor = mod?.MapboxGradientBoxControl || mod?.GradientBoxControl || mod?.default?.MapboxGradientBoxControl;
            if (InfoCtor) window.MapboxInfoBoxControl = InfoCtor;
            if (GradCtor) window.MapboxGradientBoxControl = GradCtor;
          } catch (e) {
            console.warn('Failed to dynamically import mapbox-gl-infobox:', e);
          }
        }

        // Alias common globals if present under different names
        if (!window.MapboxInfoBoxControl && window.InfoBoxControl) {
          window.MapboxInfoBoxControl = window.InfoBoxControl;
        }
        if (!window.MapboxGradientBoxControl && window.GradientBoxControl) {
          window.MapboxGradientBoxControl = window.GradientBoxControl;
        }

        // Load CSS for InfoBox plugin
        const hasStyle = document.querySelector('link[href*="mapbox-gl-infobox"][href$="styles.css"]') ||
                         document.querySelector('link[href*="mapbox-gl-infobox"][href*="dist/styles.css"]') ||
                         document.querySelector('link[href*="infobox-control"][href$="styles.css"]') ||
                         document.querySelector('link[href*="infobox-control"][href*="dist/styles.css"]');
        if (!hasStyle) {
          const inject = (href) => { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l); };
          // try multiple popular paths
          inject('https://unpkg.com/infobox-control@latest/styles.css');
          inject('https://unpkg.com/infobox-control@latest/dist/styles.css');
          inject('https://unpkg.com/mapbox-gl-infobox@latest/styles.css');
          inject('https://unpkg.com/mapbox-gl-infobox@latest/dist/styles.css');
        }
      }

      // Load Legend plugin (watergis/mapbox-gl-legend)
      if (!resolveLegendControlClass()) {
        const prevDefineLg = window.define;
        const prevModuleLg = window.module;
        const prevExportsLg = window.exports;
        const hadAMDLg = typeof prevDefineLg === 'function' && prevDefineLg.amd;
        const hadModLg = typeof prevModuleLg !== 'undefined';
        const hadExpLg = typeof prevExportsLg !== 'undefined';

        const restoreEnvLg = () => {
          if (hadAMDLg) window.define = prevDefineLg; else delete window.define;
          if (hadModLg) window.module = prevModuleLg; else delete window.module;
          if (hadExpLg) window.exports = prevExportsLg; else delete window.exports;
        };

        const tryLoadLg = (src) => new Promise((resolve) => {
          const s = document.createElement('script');
          s.src = src;
          s.onload = () => resolve({ ok: true, src });
          s.onerror = () => resolve({ ok: false, src });
          document.head.appendChild(s);
        });

        const legendCandidates = [
          'https://cdn.jsdelivr.net/npm/@watergis/mapbox-gl-legend@latest/dist/cdn/mapbox-gl-legend.js',
          'https://unpkg.com/@watergis/mapbox-gl-legend@latest/dist/cdn/mapbox-gl-legend.js',
        ];

        let lgLoaded = false;
        for (const src of legendCandidates) {
          if (hadAMDLg) window.define = undefined;
          if (hadModLg) window.module = undefined;
          if (hadExpLg) window.exports = undefined;

          /* eslint-disable no-await-in-loop */
          const result = await tryLoadLg(src);
          restoreEnvLg();
          if (result.ok && resolveLegendControlClass()) {
            lgLoaded = true;
            break;
          }
        }

        if (!lgLoaded && !resolveLegendControlClass()) {
          try {
            let mod;
            try { mod = await import('https://esm.sh/@watergis/mapbox-gl-legend@latest'); } catch (_) {}
            if (!mod) {
              try { mod = await import('https://esm.sh/mapbox-gl-legend@latest'); } catch (e2) { throw e2; }
            }
            const LegendCtor = mod?.default?.LegendControl || mod?.LegendControl || mod?.default || mod?.MapboxLegendControl;
            if (LegendCtor && typeof LegendCtor === 'function') {
              window.MapboxLegendControl = LegendCtor;
            } else if (mod && typeof mod === 'object') {
              // Attempt to attach module under a known global for later resolution
              window.MapboxLegendControl = mod;
            }
          } catch (e) {
            console.warn('Failed to dynamically import mapbox-gl-legend:', e);
          }
        }

        // Load CSS for Legend plugin
        const hasLegendStyle = document.querySelector('link[href*="mapbox-gl-legend"][href*="style.css"]') ||
                               document.querySelector('link[href*="mapbox-gl-legend"][href*="styles.css"]') ||
                               document.querySelector('link[href*="@watergis/mapbox-gl-legend"][href*="style.css"]') ||
                               document.querySelector('link[href*="@watergis/mapbox-gl-legend"][href*="styles.css"]');
        if (!hasLegendStyle) {
          const inject = (href) => { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l); };
          inject('https://cdn.jsdelivr.net/npm/@watergis/mapbox-gl-legend@latest/css/styles.css');
          inject('https://unpkg.com/@watergis/mapbox-gl-legend@latest/css/styles.css');
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

        debugLog("DeckGL loaded successfully");
      }

      // Load Three.js for 3D rendering
      if (!window.THREE) {
        try {
          const threeModule = await import(`https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/build/three.module.min.js`);
          const namespace = { ...threeModule };
          if (threeModule.default && typeof threeModule.default === 'object') {
            Object.assign(namespace, threeModule.default);
          }
          window.THREE = Object.assign({}, window.THREE || {}, namespace); // Expose module exports on global THREE namespace
          debugLog("Three.js module loaded successfully");
        } catch (error) {
          console.error("Failed to load Three.js module:", error);
        }
      }

      // Load GLTFLoader for Three.js via bundled ESM helper while suppressing duplicate import warnings
      if (window.THREE && !window.GLTFLoader) {
        try {
          const originalWarn = console.warn;
          let suppressedDuplicateWarning = false;
          console.warn = (...args) => {
            if (
              args.length > 0 &&
              typeof args[0] === 'string' &&
              args[0].includes('Multiple instances of Three.js being imported')
            ) {
              suppressedDuplicateWarning = true;
              return;
            }
            originalWarn.apply(console, args);
          };
          try {
            const gltfModule = await import(`https://esm.sh/three@${THREE_VERSION}/examples/jsm/loaders/GLTFLoader?bundle`);
            window.GLTFLoader = gltfModule.GLTFLoader || gltfModule.default || null;
            if (window.GLTFLoader) {
              debugLog("GLTFLoader loaded successfully");
              if (suppressedDuplicateWarning) {
                debugLog("Suppressed duplicate Three.js warning emitted during GLTFLoader import");
              }
            } else {
              console.warn("GLTFLoader module loaded but no loader was exported");
            }
          } finally {
            console.warn = originalWarn;
          }
        } catch (error) {
          console.warn("Failed to load GLTFLoader:", error);
        }
      }

      // Load MapLibre Three Plugin using UMD bundle that exposes global MTP namespace
      if (window.THREE && !window.MaplibreThreePlugin) {
        if (!document.querySelector('script[data-source="maplibre-three-plugin"]')) {
          await new Promise((resolve, reject) => {
            const pluginScript = document.createElement('script');
            pluginScript.src = 'https://cdn.jsdelivr.net/npm/@dvt3d/maplibre-three-plugin@latest/dist/mtp.min.js';
            pluginScript.async = true;
            pluginScript.dataset.source = 'maplibre-three-plugin';
            pluginScript.onload = resolve;
            pluginScript.onerror = reject;
            document.head.appendChild(pluginScript);
          }).catch((error) => {
            console.warn("Failed to load MapLibre Three Plugin:", error);
          });
        }

        if (window.MTP && window.MTP.MapScene) {
          window.MaplibreThreePlugin = window.MTP;
          debugLog("MapLibre Three Plugin registered successfully");
        } else if (!window.MaplibreThreePlugin) {
          console.warn("MapLibre Three Plugin script loaded but MapScene not available");
        }
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
          debugLog("COG protocol registered successfully");
        } else {
          debugLog("COG protocol already registered");
        }
      } else {
        console.warn("MaplibreCOGProtocol not available");
      }

      // Register the PMTiles protocol
      if (window.pmtiles) {
        const pmtilesProtocol = new window.pmtiles.Protocol();
        maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);
        debugLog("PMTiles protocol registered successfully");
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

        debugLog("MapboxDraw configured for MapLibre compatibility with custom styles");
      } else {
        console.warn("MapboxDraw not available");
      }
    } catch (error) {
      console.error("Failed to initialize map protocols and libraries:", error);
    }
  };

  // Load protocols before initializing map
  Promise.resolve()
    .then(() => loadProtocols())
    .then(() => {
      // Initialize MapLibre map after protocols are loaded
      const map = new maplibregl.Map({
        container: container,
        style: model.get("style"),
      center: model.get("center"), // [lng, lat] format
      zoom: model.get("zoom"),
      bearing: model.get("bearing"),
      pitch: model.get("pitch"),
      antialias: model.get("antialias"),
      doubleClickZoom: model.get("double_click_zoom"),
      transformRequest: (url, resourceType) => {
        // Add custom headers if specified
        const customHeaders = model.get("request_headers");
        if (customHeaders && Object.keys(customHeaders).length > 0) {
          return {
            url: url,
            headers: customHeaders
          };
        }
        // Return undefined to use default behavior
        return undefined;
      }
    });

    // Force default cursor for all map interactions
    map.on('load', () => {
      const canvas = map.getCanvas();
      canvas.style.cursor = 'default';
    });

    // Store map instance for cleanup
    el._map = map;
    el._markers = [];
    el._markerGroups = new Map(); // Track marker groups by layer ID
    el._controls = new Map(); // Track added controls by type and position
    el._drawControl = null; // Track draw control instance
    el._terraDrawControl = null; // Track Terra Draw control instance
    el._streetViewPlugins = new Map(); // Track Street View plugin instances
    el._streetViewObservers = new Map(); // Track Street View mutation observers
    el._streetViewHandlers = new Map(); // Track Street View event handlers
    el._widgetId = widgetId;
    el._mapReady = false; // Track if map is fully loaded
    el._pendingCalls = []; // Queue for calls before map is ready
    el._flatgeobufLayers = new Map();
    el._flatgeobufLayerPromises = new Map();
    el._pendingFlatGeobufSync = false;
    el._featurePopupHandlers = new Map();
    el._featurePopupConfigs = new Map();
    el._featurePopupRetryTimer = null;
    el._pendingGeomanData = normalizeGeomanGeoJson(model.get("geoman_data"));

    const exportGeomanData = () => {
      // Try map.gm first (v0.5.0+ API), then fallback to el._geomanInstance
      const geomanInstance = map.gm || el._geomanInstance;

      if (!geomanInstance) {
        console.warn('[Geoman Export] No Geoman instance found');
        return;
      }

      try {
        const exported = geomanInstance.features.exportGeoJson();
        el._lastExportedData = exported; // Store for comparison
        el._geomanSyncFromJs = true;
        model.set("geoman_data", exported);
        model.save_changes();
        // Update mirrored style source if present
        if (typeof el._refreshGeomanStyleLayers === 'function') {
          el._refreshGeomanStyleLayers(exported);
        }
      } catch (error) {
        console.error('[Geoman Export] Failed to export Geoman features:', error);
      }
    };

    const importGeomanData = (data, skipExport = false) => {
      el._pendingGeomanData = normalizeGeomanGeoJson(data);
      // Try map.gm first (v0.5.0+ API), then fallback to el._geomanInstance
      const geomanInstance = map.gm || el._geomanInstance;
      if (!geomanInstance) {
        return;
      }
      try {
        const collection = el._pendingGeomanData;

        // Always use delete/import approach to ensure features are editable
        // setSourceGeoJson doesn't make features properly editable
        deleteAndImportFeatures(geomanInstance, collection);

        el._pendingGeomanData = null;
        if (!skipExport) {
          exportGeomanData();
        }
        // Also update mirrored style source if present
        try {
          if (el._geomanStyle && map.getSource(el._geomanStyle.srcId)) {
            map.getSource(el._geomanStyle.srcId).setData(collection || { type: 'FeatureCollection', features: [] });
          }
        } catch (_e) {}
      } catch (error) {
        console.error('Failed to import Geoman data:', error);
      }

      // Helper function for delete/import approach
      function deleteAndImportFeatures(geomanInstance, collection) {
        // Use atomic update to ensure map renders correctly
        if (geomanInstance.features.updateManager && geomanInstance.features.updateManager.withAtomicSourcesUpdate) {
          geomanInstance.features.updateManager.withAtomicSourcesUpdate(() => {
            clearAndImport(geomanInstance, collection);
          });
        } else {
          clearAndImport(geomanInstance, collection);
        }
      }

      function clearAndImport(geomanInstance, collection) {
        // Clear all existing features by ID
        const featureIds = Array.from(geomanInstance.features.featureStore.keys());
        featureIds.forEach((featureId) => {
          try {
            geomanInstance.features.delete(featureId);
          } catch (deleteError) {
            console.warn('Failed to delete Geoman feature:', featureId, deleteError);
          }
        });

        // Import new features if any
        if (collection.features.length > 0) {
          geomanInstance.features.importGeoJson(collection);

          // Disable global edit mode after import so vertices are hidden by default
          // User will need to select individual features to edit them
          if (geomanInstance.globalEditModeEnabled && geomanInstance.globalEditModeEnabled()) {
            geomanInstance.disableGlobalEditMode();
          }
        }
      }
    };

    const scheduleGeomanInitialization = (controlKey, controlOptions = {}) => {
      if (el._geomanInstance || el._geomanPromise) {
        console.warn('Geoman control is already initialized or initialization is in progress.');
        return;
      }

      const geomanNamespace = resolveGeomanNamespace();
      if (!geomanNamespace) {
        console.warn('MapLibre Geoman namespace is unavailable.');
        return;
      }

      // In v0.5.0+, window.Geoman should be the Geoman class/constructor
      // It might be accessed as Geoman.Geoman or just Geoman depending on the build
      const GeomanConstructor = geomanNamespace.Geoman || geomanNamespace;
      if (typeof GeomanConstructor !== 'function') {
        console.warn('MapLibre Geoman constructor is unavailable.');
        return;
      }

      const position = controlOptions.position || 'top-left';
      const geomanOptions = buildGeomanOptions(position, controlOptions.geoman_options || {}, controlOptions.collapsed);
      const initialCollapsed = Object.prototype.hasOwnProperty.call(controlOptions, 'collapsed')
        ? controlOptions.collapsed
        : undefined;
      const showInfoBox = Boolean(controlOptions && controlOptions.show_info_box);
      const infoBoxMode = (controlOptions && controlOptions.info_box_mode) || 'click';
      const infoBoxTolerance = Number(controlOptions && controlOptions.info_box_tolerance);
      el._gmShowInfoBox = showInfoBox;
      el._gmInfoMode = infoBoxMode;
      el._gmInfoTolerance = infoBoxTolerance;

      el._controls.set(controlKey, { type: 'geoman', pending: true });

      try {
        // Use v0.5.0 synchronous constructor API
        const instance = new GeomanConstructor(map, geomanOptions);

        // Fallback: if Geoman doesn't emit gm:loaded promptly, attach info box handlers early
        try {
          setTimeout(() => {
            try {
              if (el._geomanEventListener) return;
              // Minimal early ensure/hit-test using only geoman_data
              const ensureEarlyBox = () => {
                const container = map.getContainer ? map.getContainer() : el;
                if (!container) return null;
                let box = container.querySelector('.gm-info-box');
                if (!box) {
                  box = document.createElement('div');
                  box.className = 'gm-info-box';
                  box.style.position = 'absolute';
                  box.style.bottom = '10px';
                  box.style.right = '10px';
                  box.style.zIndex = '1000';
                  box.style.background = 'rgba(255,255,255,0.95)';
                  box.style.border = '1px solid rgba(0,0,0,0.15)';
                  box.style.borderRadius = '6px';
                  box.style.padding = '6px 10px';
                  box.style.minWidth = '160px';
                  box.style.maxWidth = '280px';
                  box.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';
                  box.style.fontSize = '12px';
                  box.style.color = '#333';
                  box.style.display = 'none';
                  const title = document.createElement('div');
                  title.style.fontWeight = '600';
                  title.style.marginBottom = '4px';
                  title.textContent = 'Feature info';
                  const content = document.createElement('div');
                  content.className = 'gm-info-box-content';
                  box.appendChild(title);
                  box.appendChild(content);
                  container.appendChild(box);
                }
                return box;
              };
              const showEarly = (props) => {
                const box = ensureEarlyBox();
                if (!box) return;
                const content = box.querySelector('.gm-info-box-content');
                if (content) {
                  content.innerHTML = '';
                  const entries = Object.entries(props || {});
                  if (entries.length === 0) {
                    const none = document.createElement('div');
                    none.textContent = 'No properties';
                    content.appendChild(none);
                  } else {
                    const list = document.createElement('div');
                    entries.slice(0, 16).forEach(([k, v]) => {
                      const row = document.createElement('div');
                      const kEl = document.createElement('span');
                      kEl.style.color = '#555';
                      kEl.textContent = `${k}: `;
                      const vEl = document.createElement('span');
                      vEl.style.color = '#111';
                      try { vEl.textContent = typeof v === 'object' ? JSON.stringify(v) : String(v); }
                      catch (_e) { vEl.textContent = String(v); }
                      row.appendChild(kEl); row.appendChild(vEl); list.appendChild(row);
                    });
                    if (entries.length > 16) {
                      const more = document.createElement('div');
                      more.style.color = '#777';
                      more.style.marginTop = '4px';
                      more.textContent = `(+${entries.length - 16} more)`;
                      list.appendChild(more);
                    }
                    content.appendChild(list);
                  }
                }
                box.style.display = 'block';
              };
              const hideEarly = () => {
                const container = map.getContainer ? map.getContainer() : el;
                if (!container) return;
                const box = container.querySelector('.gm-info-box');
                if (box) {
                  box.style.display = 'none';
                  const content = box.querySelector('.gm-info-box-content');
                  if (content) content.textContent = '';
                }
              };
// Geometry helper functions (shared)
const sqr = (n) => n * n;
const dist2 = (a, b) => sqr(a.x - b.x) + sqr(a.y - b.y);
const distToSegment2 = (p, a, b) => {
  const vx = b.x - a.x, vy = b.y - a.y;
  const wx = p.x - a.x, wy = p.y - a.y;
  const c1 = vx * wx + vy * wy;
  if (c1 <= 0) return dist2(p, a);
  const c2 = vx * vx + vy * vy;
  if (c2 <= c1) return dist2(p, b);
  const t = c1 / (c2 || 1e-12);
  const proj = { x: a.x + t * vx, y: a.y + t * vy };
  return dist2(p, proj);
};
const pointInRing = (pt, ring) => {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const intersect = ((yi > pt[1]) !== (yj > pt[1])) &&
      (pt[0] < (xj - xi) * (pt[1] - yi) / ((yj - yi) || 1e-12) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
};
const pointInPolygon = (pt, poly) => {
  if (!Array.isArray(poly) || poly.length === 0) return false;
  if (!pointInRing(pt, poly[0])) return false;
  for (let h = 1; h < poly.length; h++) {
    if (pointInRing(pt, poly[h])) return false;
  }
  return true;
};
// END geometry helpers

// (Remove local definitions from showEarly/hideEarly logic)
              const earlyLookup = (lngLat) => {
                try {
                  const data = model.get('geoman_data') || { type: 'FeatureCollection', features: [] };
                  const features = Array.isArray(data.features) ? data.features : [];
                  if (!features.length) return null;
                  const pt = map.project([lngLat.lng, lngLat.lat]);
                  const tol = Number.isFinite(el._gmInfoTolerance) ? Math.max(1, Number(el._gmInfoTolerance)) : 8;
                  const threshold2 = tol * tol;
                  let best = null;
                  let bestScore = Infinity;
                  for (const f of features) {
                    if (!f || !f.geometry) continue;
                    const g = f.geometry;
                    if (g.type === 'Point') {
                      const p = map.project(g.coordinates);
                      const d2 = dist2(pt, p);
                      if (d2 <= threshold2 && d2 < bestScore) { best = f.properties || {}; bestScore = d2; }
                    } else if (g.type === 'MultiPoint') {
                      for (const c of g.coordinates || []) {
                        const p = map.project(c);
                        const d2 = dist2(pt, p);
                        if (d2 <= threshold2 && d2 < bestScore) { best = f.properties || {}; bestScore = d2; }
                      }
                    } else if (g.type === 'LineString') {
                      const coords = g.coordinates || [];
                      for (let i = 1; i < coords.length; i++) {
                        const a = map.project(coords[i - 1]), b = map.project(coords[i]);
                        const d2 = distToSegment2(pt, a, b);
                        if (d2 <= threshold2 && d2 < bestScore) { best = f.properties || {}; bestScore = d2; }
                      }
                    } else if (g.type === 'MultiLineString') {
                      for (const line of g.coordinates || []) {
                        for (let i = 1; i < line.length; i++) {
                          const a = map.project(line[i - 1]), b = map.project(line[i]);
                          const d2 = distToSegment2(pt, a, b);
                          if (d2 <= threshold2 && d2 < bestScore) { best = f.properties || {}; bestScore = d2; }
                        }
                      }
                    } else if (g.type === 'Polygon') {
                      if (pointInPolygon([lngLat.lng, lngLat.lat], g.coordinates)) return f.properties || {};
                    } else if (g.type === 'MultiPolygon') {
                      for (const poly of g.coordinates || []) {
                        if (pointInPolygon([lngLat.lng, lngLat.lat], poly)) return f.properties || {};
                      }
                    }
                  }
                  return best;
                } catch (_e) { return null; }
              };
              const onEarlyClick = (e) => {
                if (!el._gmShowInfoBox || el._gmInfoMode === 'hover') return;
                const props = earlyLookup(e.lngLat);
                if (props) showEarly(props); else hideEarly();
              };
              const onEarlyMove = (e) => {
                if (!el._gmShowInfoBox || el._gmInfoMode !== 'hover') return;
                const props = earlyLookup(e.lngLat);
                if (props) showEarly(props); else hideEarly();
              };
              map.on('click', onEarlyClick);
              map.on('mousemove', onEarlyMove);
              el._gmInfoHandlers = { move: onEarlyMove, click: onEarlyClick };
            } catch (_err) {}
          }, 400);
        } catch (_e) {}

        // Wait for gm:loaded event to ensure adapter is fully initialized
        map.once('gm:loaded', () => {
          try {
            el._geomanInstance = instance;
            el._controls.set(controlKey, instance);
            let stylePaint = controlOptions.geoman_paint || null;
            if (stylePaint && typeof stylePaint !== 'object') {
              console.warn('[Geoman] Invalid paint config: expected object, got', typeof stylePaint);
              stylePaint = null;
            }
            const paintAbove = controlOptions?.geoman_paint_above ?? false; // default false

            // Info box UI (optional)
            let infoBoxEl = null;
            const ensureInfoBox = () => {
              if (!el._gmShowInfoBox) return null;
              if (infoBoxEl && infoBoxEl.isConnected) return infoBoxEl;
              try {
                const container = map.getContainer ? map.getContainer() : el;
                if (!container) return null;
                const box = document.createElement('div');
                box.className = 'gm-info-box';
                box.style.position = 'absolute';
                box.style.bottom = '10px';
                box.style.right = '10px';
                box.style.zIndex = '1000';
                box.style.background = 'rgba(255,255,255,0.95)';
                box.style.border = '1px solid rgba(0,0,0,0.15)';
                box.style.borderRadius = '6px';
                box.style.padding = '6px 10px';
                box.style.minWidth = '160px';
                box.style.maxWidth = '280px';
                box.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';
                box.style.fontSize = '12px';
                box.style.color = '#333';
                box.style.display = 'none';
                const title = document.createElement('div');
                title.style.fontWeight = '600';
                title.style.marginBottom = '4px';
                title.textContent = 'Feature info';
                const content = document.createElement('div');
                content.className = 'gm-info-box-content';
                box.appendChild(title);
                box.appendChild(content);
                container.appendChild(box);
                infoBoxEl = box;
                return box;
              } catch (_e) {
                return null;
              }
            };
            const hideInfoBox = () => {
              if (infoBoxEl) {
                infoBoxEl.style.display = 'none';
                const content = infoBoxEl.querySelector('.gm-info-box-content');
                if (content) content.textContent = '';
              }
            };
            el._gmEnsureInfoBox = ensureInfoBox;
            el._gmHideInfoBox = hideInfoBox;
            const showInfoBoxWithProps = (props) => {
              const box = ensureInfoBox();
              if (!box) return;
              const entries = Object.entries(props || {});
              const content = box.querySelector('.gm-info-box-content');
              if (content) {
                content.innerHTML = '';
                if (entries.length === 0) {
                  const none = document.createElement('div');
                  none.textContent = 'No properties';
                  content.appendChild(none);
                } else {
                  const list = document.createElement('div');
                  for (const [k, v] of entries.slice(0, 16)) {
                    const row = document.createElement('div');
                    const keyEl = document.createElement('span');
                    keyEl.style.color = '#555';
                    keyEl.textContent = `${k}: `;
                    const valEl = document.createElement('span');
                    valEl.style.color = '#111';
                    try {
                      valEl.textContent = typeof v === 'object' ? JSON.stringify(v) : String(v);
                    } catch (_e) {
                      valEl.textContent = String(v);
                    }
                    row.appendChild(keyEl);
                    row.appendChild(valEl);
                    list.appendChild(row);
                  }
                  if (entries.length > 16) {
                    const more = document.createElement('div');
                    more.style.color = '#777';
                    more.style.marginTop = '4px';
                    more.textContent = `(+${entries.length - 16} more)`;
                    list.appendChild(more);
                  }
                  content.appendChild(list);
                }
              }
              box.style.display = 'block';
            };
            // Mirrored style layers for visualizing geoman_data with custom paint
            // Accept a unique key (e.g., position or controlKey) to avoid ID conflicts
            const ensureGeomanStyleLayers = (paintConfig, controlKey = 'default') => {
              if (!paintConfig) return;
              const srcId = `geoman-style-src-${controlKey}`;
              const fillId = `geoman-style-fill-${controlKey}`;
              const lineId = `geoman-style-line-${controlKey}`;
              const pointId = `geoman-style-point-${controlKey}`;
              try {
                if (!map.getSource(srcId)) {
                  map.addSource(srcId, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
                }
              } catch (_e) {}
              // Placement: default above Geoman; if paintAbove === false, push below first geoman layer
              let beforeId = undefined;
              if (!paintAbove) {
                try {
                  const layers = (map.getStyle() && map.getStyle().layers) || [];
                  for (const ly of layers) {
                    const id = (ly && ly.id) || '';
                    if (id && (id.startsWith('gm-') || id.includes('geoman') || id.includes('gm'))) {
                      beforeId = id;
                      break;
                    }
                  }
                } catch (_e2) {}
              }
              if (!map.getLayer(fillId)) {
                try {
                  const layer = {
                    id: fillId,
                    type: 'fill',
                    source: srcId,
                    filter: ['any',
                      ['==', ['geometry-type'], 'Polygon'],
                      ['==', ['geometry-type'], 'MultiPolygon']
                    ],
                    paint: Object.assign({
                      'fill-color': '#90caf9',
                      'fill-opacity': 0.2
                    }, (paintConfig.fill || {}))
                  };
                  if (beforeId) map.addLayer(layer, beforeId); else map.addLayer(layer);
                } catch (_e3) {}
              }
              if (!map.getLayer(lineId)) {
                try {
                  const layer = {
                    id: lineId,
                    type: 'line',
                    source: srcId,
                    filter: ['any',
                      ['==', ['geometry-type'], 'LineString'],
                      ['==', ['geometry-type'], 'MultiLineString']
                    ],
                    paint: Object.assign({
                      'line-color': '#42a5f5',
                      'line-width': 2.5
                    }, (paintConfig.line || {}))
                  };
                  if (beforeId) map.addLayer(layer, beforeId); else map.addLayer(layer);
                } catch (_e4) {}
              }
              if (!map.getLayer(pointId)) {
                try {
                  const layer = {
                    id: pointId,
                    type: 'circle',
                    source: srcId,
                    filter: ['any',
                      ['==', ['geometry-type'], 'Point'],
                      ['==', ['geometry-type'], 'MultiPoint']
                    ],
                    paint: Object.assign({
                      'circle-radius': 5,
                      'circle-color': '#1976d2',
                      'circle-stroke-color': '#0d47a1',
                      'circle-stroke-width': 1.5
                    }, (paintConfig.point || {}))
                  };
                  if (beforeId) map.addLayer(layer, beforeId); else map.addLayer(layer);
                } catch (_e5) {}
              }
              el._geomanStyle = { srcId, fillId, lineId, pointId };
            };
            const refreshGeomanStyleLayers = (collection) => {
              try {
                if (!stylePaint || !el._geomanStyle) return;
                const srcId = el._geomanStyle.srcId;
                if (map.getSource(srcId)) {
                  map.getSource(srcId).setData(collection || { type: 'FeatureCollection', features: [] });
                }
              } catch (_e) {}
            };
            const setGeomanMirrorVisibility = (visible) => {
              if (!el._geomanStyle) return;
              const { fillId, lineId, pointId } = el._geomanStyle;
              const vis = visible ? 'visible' : 'none';
              try { if (map.getLayer(fillId)) map.setLayoutProperty(fillId, 'visibility', vis); } catch (_e) {}
              try { if (map.getLayer(lineId)) map.setLayoutProperty(lineId, 'visibility', vis); } catch (_e) {}
              try { if (map.getLayer(pointId)) map.setLayoutProperty(pointId, 'visibility', vis); } catch (_e) {}
              el._geomanMirrorVisible = !!visible;
            };
            // Store functions on element for access from exportGeomanData
            el._refreshGeomanStyleLayers = refreshGeomanStyleLayers;
            el._setGeomanMirrorVisibility = setGeomanMirrorVisibility;
            if (stylePaint) ensureGeomanStyleLayers(stylePaint);
            const findPropsForFeatureId = (fid) => {
              if (!fid) return null;
              try {
                const data = model.get('geoman_data') || { type: 'FeatureCollection', features: [] };
                const f = (data.features || []).find((x) => {
                  if (!x) return false;
                  const idOk = x.id === fid || String(x.id) === String(fid);
                  const gmOk = x.properties && (x.properties.__gm_id === fid || String(x.properties.__gm_id) === String(fid));
                  return idOk || gmOk;
                });
                if (f && f.properties) return f.properties;
              } catch (_e2) {}
              return null;
            };

            // Heuristic helpers to detect current selection when Geoman doesn't provide id in payload
            const getSelectedFeatureIds = () => {
              try {
                const geomanInstance = map.gm || el._geomanInstance;
                const featuresApi = geomanInstance?.features;
                if (!featuresApi) return [];
                if (typeof featuresApi.getSelectedIds === 'function') {
                  const ids = featuresApi.getSelectedIds();
                  if (Array.isArray(ids)) return ids;
                }
                if (typeof featuresApi.getSelected === 'function') {
                  const sel = featuresApi.getSelected();
                  if (Array.isArray(sel) && sel.length > 0) {
                    const ids = sel.map((f) => {
                      const gj = f?.geojson || f?.feature || f;
                      return (f && (f.id || f.featureId)) || gj?.id || gj?.properties?.__gm_id || null;
                    }).filter((x) => x != null);
                    if (ids.length > 0) return ids;
                  }
                  if (sel && Array.isArray(sel.features)) {
                    const ids = sel.features.map((f) => {
                      return (f && (f.id || (f.properties && f.properties.__gm_id))) || null;
                    }).filter((x) => x != null);
                    if (ids.length > 0) return ids;
                  }
                }
                const selectedIds =
                  featuresApi.selectedIds ||
                  featuresApi.selection?.selectedIds ||
                  featuresApi.selection?.ids ||
                  [];
                if (Array.isArray(selectedIds) && selectedIds.length > 0) return selectedIds;
                const store = featuresApi.featureStore;
                if (store && typeof store.forEach === 'function') {
                  const ids = [];
                  store.forEach((val, key) => {
                    if (!val) return;
                    const isSelected =
                      val.selected || val.isSelected || (val.state && (val.state.selected || val.state.isSelected));
                    if (isSelected) {
                      const gj = val.geojson || val;
                      const gmId = gj?.properties && gj.properties.__gm_id;
                      ids.push(gmId != null ? gmId : key);
                    }
                  });
                  if (ids.length > 0) return ids;
                }
              } catch (_e) {}
              return [];
            };

            let _infoUpdateTimer = null;
            const updateInfoFromCurrentSelection = (force = false) => {
              if (!el._gmShowInfoBox) return;
              if (!force) {
                if (_infoUpdateTimer) return;
                _infoUpdateTimer = setTimeout(() => {
                  _infoUpdateTimer = null;
                  updateInfoFromCurrentSelection(true);
                }, 120);
                return;
              }
              try {
                const ids = getSelectedFeatureIds();
                if (Array.isArray(ids) && ids.length > 0) {
                  const props = findPropsForFeatureId(ids[0]);
                  if (props && Object.keys(props).length > 0) {
                    showInfoBoxWithProps(props);
                  } else {
                    showInfoBoxWithProps({});
                  }
                }
              } catch (_e) {}
            };

            // Determine feature properties at a point using only geoman_data
            const updateInfoFromEventPoint = (ev, force = false) => {
              if (!el._gmShowInfoBox || !ev || !ev.lngLat) return;
              if (!force) {
                if (_infoUpdateTimer) return;
                _infoUpdateTimer = setTimeout(() => {
                  _infoUpdateTimer = null;
                  updateInfoFromEventPoint(ev, true);
                }, 120);
                return;
              }
              // Geometry helpers (inline)
              const sqr = (n) => n * n;
              const dist2 = (a, b) => sqr(a.x - b.x) + sqr(a.y - b.y);
              const distToSegment2 = (p, a, b) => {
                const vx = b.x - a.x;
                const vy = b.y - a.y;
                const wx = p.x - a.x;
                const wy = p.y - a.y;
                const c1 = vx * wx + vy * wy;
                if (c1 <= 0) return dist2(p, a);
                const c2 = vx * vx + vy * vy;
                if (c2 <= c1) return dist2(p, b);
                const t = c1 / (c2 || 1e-12);
                const proj = { x: a.x + t * vx, y: a.y + t * vy };
                return dist2(p, proj);
              };
              const pointInRing = (pt, ring) => {
                let inside = false;
                for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
                  const xi = ring[i][0], yi = ring[i][1];
                  const xj = ring[j][0], yj = ring[j][1];
                  const intersect = ((yi > pt[1]) !== (yj > pt[1])) &&
                    (pt[0] < (xj - xi) * (pt[1] - yi) / ((yj - yi) || 1e-12) + xi);
                  if (intersect) inside = !inside;
                }
                return inside;
              };
              const pointInPolygon = (pt, poly) => {
                if (!Array.isArray(poly) || poly.length === 0) return false;
                if (!pointInRing(pt, poly[0])) return false;
                for (let h = 1; h < poly.length; h++) {
                  if (pointInRing(pt, poly[h])) return false;
                }
                return true;
              };
              const flashInfoGeometry = (geometry) => {
                try {
                  if (!geometry) return;
                  const srcId = 'gm-info-flash-src';
                  const fillId = 'gm-info-flash-fill';
                  const lineId = 'gm-info-flash-line';
                  const pointId = 'gm-info-flash-point';
                  const fc = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry }] };
                  if (map.getSource(srcId)) {
                    map.getSource(srcId).setData(fc);
                  } else {
                    map.addSource(srcId, { type: 'geojson', data: fc });
                  }
                  // Fill (polygons)
                  if (!map.getLayer(fillId)) {
                    try {
                      map.addLayer({
                        id: fillId,
                        type: 'fill',
                        source: srcId,
                        filter: ['==', ['geometry-type'], 'Polygon'],
                        paint: {
                          'fill-color': '#fff176',
                          'fill-opacity': 0.45
                        }
                      });
                    } catch (_e) {}
                  }
                  // Line (lines + polygon outlines)
                  if (!map.getLayer(lineId)) {
                    try {
                      map.addLayer({
                        id: lineId,
                        type: 'line',
                        source: srcId,
                        filter: ['any', ['==', ['geometry-type'], 'LineString'], ['==', ['geometry-type'], 'Polygon']],
                        paint: {
                          'line-color': '#fdd835',
                          'line-width': 4
                        }
                      });
                    } catch (_e2) {}
                  }
                  // Points
                  if (!map.getLayer(pointId)) {
                    try {
                      map.addLayer({
                        id: pointId,
                        type: 'circle',
                        source: srcId,
                        filter: ['==', ['geometry-type'], 'Point'],
                        paint: {
                          'circle-radius': 7,
                          'circle-color': '#ffca28',
                          'circle-stroke-color': '#f57f17',
                          'circle-stroke-width': 2
                        }
                      });
                    } catch (_e3) {}
                  }
                  // Auto clear after a short delay
                  setTimeout(() => {
                    try {
                      if (map.getSource(srcId)) {
                        map.getSource(srcId).setData({ type: 'FeatureCollection', features: [] });
                      }
                    } catch (_e4) {}
                  }, 700);
                } catch (_flashErr) {}
              };
              try {
                const data = model.get('geoman_data') || { type: 'FeatureCollection', features: [] };
                const features = Array.isArray(data.features) ? data.features : [];
                const clickPoint = map.project([ev.lngLat.lng, ev.lngLat.lat]);
                const tol = Number.isFinite(el._gmInfoTolerance)
                  ? Math.max(1, Number(el._gmInfoTolerance))
                  : (el._gmInfoMode === 'hover' ? 6 : 8);
                const threshold2 = tol * tol;
                let best = null;
                let bestGeom = null;
                let bestScore = Infinity;
                for (const f of features) {
                  if (!f || !f.geometry) continue;
                  const g = f.geometry;
                  if (g.type === 'Point') {
                    const p = map.project(g.coordinates);
                    const d2 = dist2(clickPoint, p);
                    if (d2 <= threshold2 && d2 < bestScore) {
                      best = f.properties || {};
                      bestGeom = g;
                      bestScore = d2;
                    }
                  } else if (g.type === 'MultiPoint') {
                    for (const c of g.coordinates || []) {
                      const p = map.project(c);
                      const d2 = dist2(clickPoint, p);
                      if (d2 <= threshold2 && d2 < bestScore) {
                        best = f.properties || {};
                        bestGeom = { type: 'Point', coordinates: c };
                        bestScore = d2;
                      }
                    }
                  } else if (g.type === 'LineString') {
                    const coords = g.coordinates || [];
                    for (let i = 1; i < coords.length; i++) {
                      const a = map.project(coords[i - 1]);
                      const b = map.project(coords[i]);
                      const d2 = distToSegment2(clickPoint, a, b);
                      if (d2 <= threshold2 && d2 < bestScore) {
                        best = f.properties || {};
                        bestGeom = g;
                        bestScore = d2;
                      }
                    }
                  } else if (g.type === 'MultiLineString') {
                    for (const line of g.coordinates || []) {
                      for (let i = 1; i < line.length; i++) {
                        const a = map.project(line[i - 1]);
                        const b = map.project(line[i]);
                        const d2 = distToSegment2(clickPoint, a, b);
                        if (d2 <= threshold2 && d2 < bestScore) {
                          best = f.properties || {};
                          bestGeom = g;
                          bestScore = d2;
                        }
                      }
                    }
                  } else if (g.type === 'Polygon') {
                    const pt = [ev.lngLat.lng, ev.lngLat.lat];
                    if (pointInPolygon(pt, g.coordinates)) {
                      best = f.properties || {};
                      bestGeom = g;
                      bestScore = 0;
                      break;
                    }
                  } else if (g.type === 'MultiPolygon') {
                    const pt = [ev.lngLat.lng, ev.lngLat.lat];
                    let hit = false;
                    for (const poly of g.coordinates || []) {
                      if (pointInPolygon(pt, poly)) { hit = true; break; }
                    }
                    if (hit) {
                      best = f.properties || {};
                      bestGeom = g;
                      bestScore = 0;
                      break;
                    }
                  }
                }
                if (best) {
                  showInfoBoxWithProps(best);
                  // Flash highlight only on explicit clicks (force === true)
                  if (force && bestGeom) {
                    flashInfoGeometry(bestGeom);
                  }
                } else {
                  hideInfoBox();
                }
              } catch (_e) {
                // ignore
              }
            };

            // Debounced exporter to avoid excessive trait churn while drawing
            let geomanExportTimer = null;
            const scheduleGeomanExport = () => {
              if (geomanExportTimer) {
                clearTimeout(geomanExportTimer);
              }
              // Small debounce to batch rapid event bursts
              geomanExportTimer = setTimeout(() => {
                geomanExportTimer = null;
                exportGeomanData();
              }, 50);
            };

            const geomanListener = (event) => {
              try {
                const currentEvents = model.get("_js_events") || [];
                const geomanEvent = {
                  type: 'geoman',
                  name: event?.name,
                  eventType: event?.type,
                  payload: event?.payload,
                };
                model.set("_js_events", [...currentEvents, geomanEvent]);
                model.save_changes();
              } catch (evtError) {
                console.warn('Failed to forward Geoman event:', evtError);
              }

              // Always schedule an export on any Geoman event; debounced above
              scheduleGeomanExport();
            // Update status for Python
            updateAndSyncGeomanStatus();

              // Update info box only when explicitly using event mode (disabled by default)
              if (el._gmShowInfoBox && (el._gmInfoMode === 'event')) {
                try {
                  // Heuristics to extract a feature id from event payload
                  const p = event?.payload || {};
                  let fid = p.id || p.featureId || p.feature?.id || p.target?.id;
                  // Also try __gm_id if present
                  if (!fid && p && p.feature && p.feature.properties && p.feature.properties.__gm_id) {
                    fid = p.feature.properties.__gm_id;
                  }
                  if (!fid && Array.isArray(p.features) && p.features.length > 0) {
                    const f0 = p.features[0];
                    fid = f0?.id || (f0?.properties && f0.properties.__gm_id);
                  }
                  // Try direct properties from payload first
                  const directProps =
                    (p && p.properties) ||
                    (p && p.feature && p.feature.properties) ||
                    (Array.isArray(p.features) && p.features[0] && p.features[0].properties) ||
                    null;
                  if (directProps && Object.keys(directProps).length > 0) {
                    showInfoBoxWithProps(directProps);
                  } else if (fid != null) {
                    const props = findPropsForFeatureId(fid);
                    if (props && Object.keys(props).length > 0) {
                      showInfoBoxWithProps(props);
                    } else {
                      // If there are no properties, show an empty state rather than hiding immediately
                      showInfoBoxWithProps({});
                    }
                  } else {
                    // For generic events (e.g., toolbar toggles), do not hide aggressively.
                    // Only hide on explicit clear/reset events if we can detect them.
                    const name = (event && (event.name || event.type)) || '';
                    if (name.includes('clear') || name.includes('delete') || name.includes('unselect')) {
                      hideInfoBox();
                    }
                    // Attempt to read current selection when no fid present
                    updateInfoFromCurrentSelection();
                  }
                } catch (_e) {
                  // ignore info box errors
                }
              }
            };

            // Boost info box updates on selection/edit/move events by name match
            const originalGeomanListener = geomanListener;
            const enhancedListener = (ev) => {
              originalGeomanListener(ev);
              try {
                const nm = (ev && (ev.name || ev.type) || '').toLowerCase();
                if (
                  nm.includes('select') ||
                  nm.includes('edit') ||
                  nm.includes('move') ||
                  nm.includes('change') ||
                  nm.includes('drag') ||
                  nm.includes('vertex') ||
                  nm.includes('update')
                ) {
                  updateInfoFromCurrentSelection(true);
                }
              } catch (_e) {}
            };

            // Use enhanced listener that forces selection refresh on relevant events
            instance.setGlobalEventsListener(enhancedListener);
            el._geomanEventListener = enhancedListener;

            // Attach info-box listeners according to mode: click (default) or hover
            try {
              // Persist tolerance and mode for later use
              el._gmInfoMode = infoBoxMode;
              el._gmInfoTolerance = Number.isFinite(infoBoxTolerance) ? infoBoxTolerance : undefined;

              // Provide a reusable attach function for external callers (e.g., after data load)
              el._gmAttachInfoHandlers = () => {
                try {
                  // Clean up any previous handlers
                  if (el._gmInfoHandler) {
                    const { eventType, handler } = el._gmInfoHandler;
                    try { map.off(eventType, handler); } catch (_e) {}
                    el._gmInfoHandler = null;
                  }
                  if (el._gmInfoDomHandler) {
                    const { eventType, handler } = el._gmInfoDomHandler;
                    try { map.getCanvasContainer().removeEventListener(eventType, handler, true); } catch (_e) {}
                    el._gmInfoDomHandler = null;
                  }

                  // Map-level handler (bubbles)
                  let eventType, handler;
                  if (el._gmInfoMode === 'hover') {
                    eventType = 'mousemove';
                    handler = (e) => updateInfoFromEventPoint(e);
                  } else {
                    eventType = 'click';
                    handler = (e) => updateInfoFromEventPoint(e, true);
                  }
                  map.on(eventType, handler);
                  el._gmInfoHandler = { eventType, handler };

                  // DOM capture handler (in case Geoman stops propagation)
                  const domEvent = (el._gmInfoMode === 'hover') ? 'mousemove' : 'click';
                  const domHandler = (ev) => {
                    try {
                      if (!el._gmShowInfoBox) return;
                      const rect = map.getCanvas().getBoundingClientRect();
                      const x = ev.clientX - rect.left;
                      const y = ev.clientY - rect.top;
                      const lngLat = map.unproject([x, y]);
                      if (!lngLat) return;
                      updateInfoFromEventPoint({ lngLat }, domEvent === 'click');
                    } catch (_e) {}
                  };
                  map.getCanvasContainer().addEventListener(domEvent, domHandler, true);
                  el._gmInfoDomHandler = { eventType: domEvent, handler: domHandler };
                } catch (_e3) {}
              };
              // Expose a direct updater for convenience
              el._gmUpdateInfoFromEvent = (e, force = false) => updateInfoFromEventPoint(e, force);

              // Attach now
              el._gmAttachInfoHandlers();
            } catch (_e) {}

            if (el._pendingGeomanData) {
              importGeomanData(el._pendingGeomanData);
            } else {
              exportGeomanData();
            }
            // Ensure mirrored style reflects current data
            try {
              if (stylePaint) {
                ensureGeomanStyleLayers(stylePaint);
                const currentData = model.get('geoman_data') || { type: 'FeatureCollection', features: [] };
                refreshGeomanStyleLayers(currentData);
              }
            } catch (_e) {}
            // Sync initial toolbar status
            updateAndSyncGeomanStatus();

            // Helpers for OSM transport loading into Geoman
            async function ensureOsmToGeojsonLoaded() {
              if (typeof window.osmtogeojson === 'function') return true;
              const tried = [];
              const sources = [
                'https://cdn.jsdelivr.net/npm/osmtogeojson@3.0.0/osmtogeojson.min.js',
                'https://cdn.jsdelivr.net/npm/osmtogeojson@3.0.0/osmtogeojson.js',
                'https://unpkg.com/osmtogeojson@3.0.0/dist/osmtogeojson.min.js',
                'https://unpkg.com/osmtogeojson@3.0.0/osmtogeojson.js'
              ];
              for (const src of sources) {
                try {
                  if (typeof window.osmtogeojson === 'function') return true;
                  const s = document.createElement('script');
                  s.src = src;
                  s.async = true;
                  s.defer = true;
                  s.setAttribute('data-osm2geojson', 'true');
                  await new Promise((resolve, reject) => {
                    s.onload = resolve;
                    s.onerror = reject;
                    document.head.appendChild(s);
                  });
                  if (typeof window.osmtogeojson === 'function') return true;
                } catch (e) {
                  tried.push(src);
                }
              }
              return false;
            }

            function convertOsmTransportToGeoJsonLite(osmJson, keys) {
              try {
                const keySet = new Set(Array.isArray(keys) && keys.length ? keys : ['highway', 'railway']);
                const features = [];
                const pushFeature = (geom, props) => {
                  if (!geom || !geom.type) return;
                  features.push({
                    type: 'Feature',
                    properties: props || {},
                    geometry: geom
                  });
                };
                const hasTransportTag = (tags) => {
                  if (!tags) return false;
                  for (const k of keySet) {
                    if (Object.prototype.hasOwnProperty.call(tags, k)) return true;
                  }
                  return false;
                };
                const elements = Array.isArray(osmJson?.elements) ? osmJson.elements : [];
                // Group relation members to build MultiLineStrings
                for (const el of elements) {
                  if (!hasTransportTag(el.tags)) continue;
                  const props = { ...(el.tags || {}), _osm_id: el.id, _osm_type: el.type };
                  if (el.type === 'node' && typeof el.lon === 'number' && typeof el.lat === 'number') {
                    pushFeature({ type: 'Point', coordinates: [el.lon, el.lat] }, props);
                  } else if (el.type === 'way' && Array.isArray(el.geometry) && el.geometry.length >= 2) {
                    const coords = el.geometry.map((p) => [p.lon, p.lat]);
                    pushFeature({ type: 'LineString', coordinates: coords }, props);
                  } else if (el.type === 'relation' && Array.isArray(el.members)) {
                    const lines = [];
                    for (const m of el.members) {
                      if (m.type === 'way' && Array.isArray(m.geometry) && m.geometry.length >= 2) {
                        lines.push(m.geometry.map((p) => [p.lon, p.lat]));
                      }
                    }
                    if (lines.length === 1) {
                      pushFeature({ type: 'LineString', coordinates: lines[0] }, props);
                    } else if (lines.length > 1) {
                      pushFeature({ type: 'MultiLineString', coordinates: lines }, props);
                    }
                  }
                }
                return { type: 'FeatureCollection', features };
              } catch (e) {
                console.warn('Lite OSM->GeoJSON conversion failed:', e);
                return { type: 'FeatureCollection', features: [] };
              }
            }

            async function fetchOsmTransportGeoJSON(bbox, options = {}) {
              const keys = Array.isArray(options.keys) && options.keys.length ? options.keys : ['highway', 'railway'];
              const timeout = options.timeout || 25;
              const [w, s, e, n] = bbox;
              // Transform bbox from GeoJSON format [west, south, east, north]
              // to Overpass API format (s,w,n,e): south,west,north,east
              const bboxStr = `${s},${w},${n},${e}`;
              const body = [
                `[out:json][timeout:${timeout}];`,
                '(',
                ...keys.flatMap((k) => [
                  `node["${k}"](${bboxStr});`,
                  `way["${k}"](${bboxStr});`,
                  `relation["${k}"](${bboxStr});`,
                ]),
                ');',
                'out body geom;'
              ].join('');
              const endpoints = [
                'https://overpass-api.de/api/interpreter',
                'https://overpass.kumi.systems/api/interpreter',
                'https://overpass.openstreetmap.ru/api/interpreter',
                'https://overpass.osm.ch/api/interpreter'
              ];
              let osmJson = null;
              let lastErr = null;
              for (const url of endpoints) {
                try {
                  const resp = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
                    body: new URLSearchParams({ data: body }).toString(),
                  });
                  if (!resp.ok) throw new Error(`Overpass error ${resp.status}`);
                  osmJson = await resp.json();
                  break;
                } catch (e) {
                  lastErr = e;
                  continue;
                }
              }
              if (!osmJson) {
                const endpointList = endpoints.join(', ');
                const lastErrMsg = lastErr && lastErr.message ? lastErr.message : String(lastErr);
                throw new Error(
                  `All Overpass endpoints failed. Tried: ${endpointList}. Last error: ${lastErrMsg}`
                );
              }
              // Try full converter; fall back to lite converter for transport use-cases
              const loaded = await ensureOsmToGeojsonLoaded();
              if (loaded && typeof window.osmtogeojson === 'function') {
                try {
                  return window.osmtogeojson(osmJson, { flatProperties: true });
                } catch (e) {
                  console.warn('osmtogeojson conversion failed, using lite converter:', e);
                }
              }
              return convertOsmTransportToGeoJsonLite(osmJson, keys);
            }

            // Loading overlay for OSM operations
            function showOsmLoading(text) {
              try {
                const mapContainer = map.getContainer ? map.getContainer() : el;
                if (!mapContainer) return null;
                let overlay = mapContainer.querySelector('.gm-osm-loading');
                if (!overlay) {
                  overlay = document.createElement('div');
                  overlay.className = 'gm-osm-loading';
                  overlay.style.position = 'absolute';
                  overlay.style.top = '10px';
                  overlay.style.left = '10px';
                  overlay.style.zIndex = '1000';
                  overlay.style.background = 'rgba(255,255,255,0.92)';
                  overlay.style.border = '1px solid rgba(0,0,0,0.15)';
                  overlay.style.borderRadius = '6px';
                  overlay.style.padding = '6px 10px';
                  overlay.style.display = 'flex';
                  overlay.style.alignItems = 'center';
                  overlay.style.gap = '8px';
                  overlay.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';
                  const spinner = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                  spinner.setAttribute('width', '18');
                  spinner.setAttribute('height', '18');
                  spinner.setAttribute('viewBox', '0 0 50 50');
                  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                  circle.setAttribute('cx', '25');
                  circle.setAttribute('cy', '25');
                  circle.setAttribute('r', '20');
                  circle.setAttribute('fill', 'none');
                  circle.setAttribute('stroke', '#1976D2');
                  circle.setAttribute('stroke-width', '5');
                  circle.setAttribute('stroke-linecap', 'round');
                  const anim = document.createElementNS('http://www.w3.org/2000/svg', 'animateTransform');
                  anim.setAttribute('attributeName', 'transform');
                  anim.setAttribute('type', 'rotate');
                  anim.setAttribute('from', '0 25 25');
                  anim.setAttribute('to', '360 25 25');
                  anim.setAttribute('dur', '0.9s');
                  anim.setAttribute('repeatCount', 'indefinite');
                  circle.appendChild(anim);
                  spinner.appendChild(circle);
                  const label = document.createElement('span');
                  label.className = 'gm-osm-loading-text';
                  label.style.fontSize = '12px';
                  label.style.color = '#333';
                  label.textContent = text || 'Loading OSM…';
                  overlay.appendChild(spinner);
                  overlay.appendChild(label);
                  mapContainer.appendChild(overlay);
                } else {
                  const label = overlay.querySelector('.gm-osm-loading-text');
                  if (label) label.textContent = text || 'Loading OSM…';
                }
                return overlay;
              } catch (_e) {
                return null;
              }
            }
            function hideOsmLoading() {
              try {
                const mapContainer = map.getContainer ? map.getContainer() : el;
                if (!mapContainer) return;
                const overlay = mapContainer.querySelector('.gm-osm-loading');
                if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
              } catch (_e) {}
            }

            async function loadOsmTransportToGeoman(opts = {}) {
              const geomanInstance = map.gm || el._geomanInstance;
              if (!geomanInstance) return;
              let bbox = opts.bbox;
              if (!Array.isArray(bbox) || bbox.length !== 4) {
                const b = map.getBounds();
                bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
              }
              const keys = Array.isArray(opts.keys) ? opts.keys : undefined;
              showOsmLoading('Loading OSM…');
              try {
                const data = await fetchOsmTransportGeoJSON(bbox, { keys, timeout: opts.timeout });
                const collection = data && data.type === 'FeatureCollection'
                  ? data
                  : { type: 'FeatureCollection', features: [] };
                try {
                  importGeomanData(collection);
                } catch (e) {
                  console.warn('Failed to import OSM transport GeoJSON into Geoman: ' + (e && e.message ? e.message : e));
                }
              } finally {
                hideOsmLoading();
              }
            }

            // Add a separate Union toggle control beneath the Geoman control
            try {
              class UnionToggleControl {
                constructor(geomanInstance, modelRef) {
                  this._geomanInstance = geomanInstance;
                  this._model = modelRef;
                  this._container = null;
                  this._button = null;
                }
                onAdd(mapRef) {
                  this._map = mapRef;
                  const container = document.createElement('div');
                  container.className = 'maplibregl-ctrl maplibregl-ctrl-group gm-union-ctrl';
                  const btn = document.createElement('button');
                  btn.type = 'button';
                  btn.className = 'maplibregl-ctrl-icon gm-union-button';
                  btn.setAttribute('title', 'Union');
                  btn.setAttribute('aria-label', 'Union');
                  btn.setAttribute('aria-pressed', 'false');
                  // Simple union SVG icon
                  btn.innerHTML = `
                    <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                      <rect x="3.5" y="6" width="10.5" height="10.5" rx="2" ry="2" fill="#00E5FF" stroke="#000" stroke-opacity="0.85" stroke-width="0.8"/>
                      <rect x="9.5" y="4" width="10.5" height="10.5" rx="2" ry="2" fill="#FF4081" stroke="#000" stroke-opacity="0.85" stroke-width="0.8"/>
                      <rect x="9" y="9" width="6" height="6" fill="#FFEB3B" stroke="#000" stroke-opacity="0.9" stroke-width="0.6"/>
                    </svg>
                  `;
                  btn.style.display = 'flex';
                  btn.style.alignItems = 'center';
                  btn.style.justifyContent = 'center';

                  this.setPressed = (pressed) => {
                    if (pressed) {
                      btn.setAttribute('aria-pressed', 'true');
                      btn.classList.add('gm-active');
                      btn.style.boxShadow = '0 0 0 2px rgba(33,150,243,0.8) inset';
                      btn.style.backgroundColor = 'rgba(33, 150, 243, 0.15)';
                      // If split is on, turn it off to avoid conflicts
                      try {
                        if (typeof splitCtrl !== 'undefined' && splitCtrl?._button?.getAttribute('aria-pressed') === 'true') {
                          splitCtrl.setPressed(false);
                          const currentEvents = this._model.get("_js_events") || [];
                          this._model.set("_js_events", [
                            ...currentEvents,
                            { type: 'geoman_split_toggled', enabled: false }
                          ]);
                          this._model.save_changes();
                        }
                      } catch (_e) {}
                    } else {
                      btn.setAttribute('aria-pressed', 'false');
                      btn.classList.remove('gm-active');
                      btn.style.boxShadow = '';
                      btn.style.backgroundColor = '';
                    }
                  };

                  const isActiveButton = (buttonEl) => {
                    return buttonEl.getAttribute('aria-pressed') === 'true'
                      || buttonEl.classList.contains('active')
                      || buttonEl.classList.contains('gm-active');
                  };

                  const getButtonLabel = (buttonEl) => {
                    return (buttonEl.getAttribute('title')
                      || buttonEl.getAttribute('aria-label')
                      || (buttonEl.textContent ? buttonEl.textContent.trim() : '')).toLowerCase();
                  };

                  const deactivateOtherToolsExceptSnap = () => {
                    const container = this._geomanInstance?.control?.container;
                    if (!container) return;
                    const buttons = Array.from(container.querySelectorAll('.gm-control-button'));
                    buttons.forEach((b) => {
                      const label = getButtonLabel(b);
                      const isSnap = label.includes('snap');
                      if (!isSnap && isActiveButton(b)) {
                        // Toggle off
                        b.click();
                      }
                    });
                  };

                  btn.addEventListener('click', () => {
                    const currentlyPressed = btn.getAttribute('aria-pressed') === 'true';
                    const next = !currentlyPressed;
                    this.setPressed(next);
                    if (next) {
                      // Deactivate other tools except snapping
                      deactivateOtherToolsExceptSnap();
                    }
                    // Notify Python
                    try {
                      const currentEvents = this._model.get("_js_events") || [];
                      this._model.set("_js_events", [
                        ...currentEvents,
                        { type: 'geoman_union_toggled', enabled: next }
                      ]);
                      this._model.save_changes();
                    } catch (evtErr) {
                      console.warn('Failed to notify union toggle:', evtErr);
                    }
                  });

                  container.appendChild(btn);
                  this._container = container;
                  this._button = btn;
                  return container;
                }
                onRemove() {
                  if (this._container && this._container.parentNode) {
                    this._container.parentNode.removeChild(this._container);
                  }
                  this._map = undefined;
                }
              }
              const unionCtrl = new UnionToggleControl(instance, model);
              // Place in same corner as Geoman; adding after Geoman stacks beneath
              map.addControl(unionCtrl, position);
              el._unionControl = unionCtrl;

              // Add Split toggle control (free split mode)
              class SplitToggleControl {
                constructor(geomanInstance, modelRef) {
                  this._geomanInstance = geomanInstance;
                  this._model = modelRef;
                  this._container = null;
                  this._button = null;
                  this._map = null;
                  this._active = false;
                  this._splitCoords = [];
                  this._onClick = null;
                  this._onDblClick = null;
                  this._onKeyDown = null;
                  this._keyTarget = null;
                }
                onAdd(mapRef) {
                  this._map = mapRef;
                  const container = document.createElement('div');
                  container.className = 'maplibregl-ctrl maplibregl-ctrl-group gm-split-ctrl';
                  const btn = document.createElement('button');
                  btn.type = 'button';
                  btn.className = 'maplibregl-ctrl-icon gm-split-button';
                  btn.setAttribute('title', 'Split');
                  btn.setAttribute('aria-label', 'Split');
                  btn.setAttribute('aria-pressed', 'false');
                  btn.innerHTML = `
                    <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                      <rect x="3" y="3" width="18" height="18" rx="3" ry="3" fill="#E0E0E0" stroke="#000" stroke-opacity="0.6" stroke-width="0.6"/>
                      <polyline points="4,20 12,12 20,4" fill="none" stroke="#1976D2" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                      <circle cx="12" cy="12" r="2" fill="#90CAF9" stroke="#0D47A1" stroke-width="0.8"/>
                    </svg>
                  `;
                  btn.style.display = 'flex';
                  btn.style.alignItems = 'center';
                  btn.style.justifyContent = 'center';

                  this._updateDrawSource = () => {
                    const srcId = 'split-draw';
                    const lineId = 'split-draw-line';
                    const pointId = 'split-draw-points';
                    const fc = this._splitCoords.length >= 2
                      ? {
                          type: 'FeatureCollection',
                          features: [
                            {
                              type: 'Feature',
                              geometry: { type: 'LineString', coordinates: this._splitCoords },
                              properties: {}
                            },
                            ...this._splitCoords.map(c => ({
                              type: 'Feature',
                              geometry: { type: 'Point', coordinates: c },
                              properties: {}
                            }))
                          ]
                        }
                      : { type: 'FeatureCollection', features: this._splitCoords.map(c => ({
                          type: 'Feature',
                          geometry: { type: 'Point', coordinates: c },
                          properties: {}
                        })) };
                    if (this._map.getSource(srcId)) {
                      try {
                        this._map.getSource(srcId).setData(fc);
                      } catch (e) {
                        try {
                          this._map.removeLayer(lineId);
                          this._map.removeLayer(pointId);
                        } catch (_err) {}
                        try {
                          this._map.removeSource(srcId);
                        } catch (_err2) {}
                        this._map.addSource(srcId, { type: 'geojson', data: fc });
                      }
                    } else {
                      this._map.addSource(srcId, { type: 'geojson', data: fc });
                    }
                    if (!this._map.getLayer(lineId)) {
                      try {
                        this._map.addLayer({
                          id: lineId,
                          type: 'line',
                          source: srcId,
                          filter: ['==', ['geometry-type'], 'LineString'],
                          paint: {
                            'line-color': '#2196F3',
                            'line-width': 3
                          }
                        });
                      } catch (_e) {}
                    }
                    if (!this._map.getLayer(pointId)) {
                      try {
                        this._map.addLayer({
                          id: pointId,
                          type: 'circle',
                          source: srcId,
                          filter: ['==', ['geometry-type'], 'Point'],
                          paint: {
                            'circle-radius': 4,
                            'circle-color': '#64B5F6',
                            'circle-stroke-color': '#1565C0',
                            'circle-stroke-width': 1.5
                          }
                        });
                      } catch (_e) {}
                    }
                  };

                  this._clearDrawSource = () => {
                    const srcId = 'split-draw';
                    const lineId = 'split-draw-line';
                    const pointId = 'split-draw-points';
                    if (this._map.getSource(srcId)) {
                      try { this._map.removeLayer(lineId); } catch (_e) {}
                      try { this._map.removeLayer(pointId); } catch (_e) {}
                      try { this._map.removeSource(srcId); } catch (_e) {}
                    }
                  };

                  this._cleanupListeners = () => {
                    if (this._onClick) { this._map.off('click', this._onClick); this._onClick = null; }
                    if (this._onDblClick) { this._map.off('dblclick', this._onDblClick); this._onDblClick = null; }
                    if (this._onKeyDown && this._keyTarget) {
                      try { this._keyTarget.removeEventListener('keydown', this._onKeyDown); } catch (_e) {}
                      this._onKeyDown = null;
                      this._keyTarget = null;
                    }
                    // Restore double-click zoom to user's preference instead of always enabling
                    try {
                      if (this._map.doubleClickZoom) {
                        const userPreference = this._model.get("double_click_zoom");
                        if (userPreference) {
                          this._map.doubleClickZoom.enable();
                        } else {
                          this._map.doubleClickZoom.disable();
                        }
                      }
                    } catch (_e) {}
                  };

                  this.finishSplit = () => {
                    if (this._splitCoords.length >= 2) {
                      try {
                        const currentEvents = this._model.get("_js_events") || [];
                        this._model.set("_js_events", [
                          ...currentEvents,
                          { type: 'geoman_split_line', coordinates: this._splitCoords }
                        ]);
                        this._model.save_changes();
                      } catch (evtErr) {
                        console.warn('Failed to notify split line:', evtErr);
                      }
                    }
                    this._splitCoords = [];
                    this._clearDrawSource();
                    this._cleanupListeners();
                    this.setPressed(false);
                  };

                  this.setPressed = (pressed) => {
                    if (pressed) {
                      btn.setAttribute('aria-pressed', 'true');
                      btn.classList.add('gm-active');
                      btn.style.boxShadow = '0 0 0 2px rgba(33,150,243,0.8) inset';
                      btn.style.backgroundColor = 'rgba(33, 150, 243, 0.15)';
                      this._active = true;
                      // Deactivate other tools except snapping
                      const container = this._geomanInstance?.control?.container;
                      if (container) {
                        const buttons = Array.from(container.querySelectorAll('.gm-control-button'));
                        const getButtonLabel = (buttonEl) =>
                          (buttonEl.getAttribute('title')
                            || buttonEl.getAttribute('aria-label')
                            || (buttonEl.textContent ? buttonEl.textContent.trim() : '')).toLowerCase();
                        const isActiveButton = (buttonEl) =>
                          buttonEl.getAttribute('aria-pressed') === 'true'
                          || buttonEl.classList.contains('active')
                          || buttonEl.classList.contains('gm-active');
                        buttons.forEach((b) => {
                          const label = getButtonLabel(b);
                          const isSnap = label.includes('snap');
                          if (!isSnap && isActiveButton(b)) b.click();
                        });
                      }
                      // If union is on, turn it off
                      try {
                        if (unionCtrl?._button?.getAttribute('aria-pressed') === 'true') {
                          unionCtrl.setPressed(false);
                          const currentEvents = this._model.get("_js_events") || [];
                          this._model.set("_js_events", [
                            ...currentEvents,
                            { type: 'geoman_union_toggled', enabled: false }
                          ]);
                          this._model.save_changes();
                        }
                      } catch (_e) {}

                      // Start drawing
                      this._splitCoords = [];
                      try { this._map.doubleClickZoom && this._map.doubleClickZoom.disable(); } catch (_e) {}
                      this._onClick = (e) => {
                        this._splitCoords.push([e.lngLat.lng, e.lngLat.lat]);
                        this._updateDrawSource();
                      };
                      this._onDblClick = () => this.finishSplit();
                      this._map.on('click', this._onClick);
                      this._map.on('dblclick', this._onDblClick);
                      // Keyboard support
                      const keyTarget = this._map.getCanvas ? this._map.getCanvas() : null;
                      if (keyTarget) {
                        try { if (!keyTarget.hasAttribute('tabindex')) keyTarget.setAttribute('tabindex', '0'); } catch (_e) {}
                        this._keyTarget = keyTarget;
                        this._onKeyDown = (ev) => {
                          const key = ev.key || ev.code;
                          if (key === 'Enter') {
                            ev.preventDefault();
                            this.finishSplit();
                          } else if (key === 'Escape' || key === 'Esc') {
                            ev.preventDefault();
                            this._splitCoords = [];
                            this._clearDrawSource();
                            this._cleanupListeners();
                            this.setPressed(false);
                          }
                        };
                        keyTarget.addEventListener('keydown', this._onKeyDown);
                      }
                    } else {
                      btn.setAttribute('aria-pressed', 'false');
                      btn.classList.remove('gm-active');
                      btn.style.boxShadow = '';
                      btn.style.backgroundColor = '';
                      this._active = false;
                      this._cleanupListeners();
                      this._splitCoords = [];
                      this._clearDrawSource();
                    }
                  };

                  btn.addEventListener('click', () => {
                    const currentlyPressed = btn.getAttribute('aria-pressed') === 'true';
                    const next = !currentlyPressed;
                    this.setPressed(next);
                    try {
                      const currentEvents = this._model.get("_js_events") || [];
                      this._model.set("_js_events", [
                        ...currentEvents,
                        { type: 'geoman_split_toggled', enabled: next }
                      ]);
                      this._model.save_changes();
                    } catch (evtErr) {
                      console.warn('Failed to notify split toggle:', evtErr);
                    }
                  });

                  container.appendChild(btn);
                  this._container = container;
                  this._button = btn;
                  return container;
                }
                onRemove() {
                  this._cleanupListeners();
                  if (this._container && this._container.parentNode) {
                    this._container.parentNode.removeChild(this._container);
                  }
                  this._map = undefined;
                }
              }
              const splitCtrl = new SplitToggleControl(instance, model);
              // Initialize split control without adding a separate control container
              try {
                splitCtrl.onAdd(map);
                // Append the split button into the existing union control group to form a single grouped control
                if (unionCtrl && unionCtrl._container && splitCtrl._button) {
                  unionCtrl._container.appendChild(splitCtrl._button);
                  // Point the split control's container to the union container for consistent cleanup/styling
                  splitCtrl._container = unionCtrl._container;
                }
              } catch (_e) {}
              el._splitControl = splitCtrl;

              // Add Info toggle control (enable/disable info box interaction)
              try {
                class InfoToggleControl {
                  constructor(modelRef) {
                    this._model = modelRef;
                    this._container = null;
                    this._button = null;
                    this._map = null;
                  }
                  setPressed(pressed) {
                    if (!this._button) return;
                    this._button.setAttribute('aria-pressed', pressed ? 'true' : 'false');
                    if (pressed) {
                      this._button.classList.add('gm-active');
                      this._button.style.boxShadow = '0 0 0 2px rgba(33,150,243,0.8) inset';
                      this._button.style.backgroundColor = 'rgba(33, 150, 243, 0.15)';
                    } else {
                      this._button.classList.remove('gm-active');
                      this._button.style.boxShadow = '';
                      this._button.style.backgroundColor = '';
                    }
                  }
                  onAdd(mapRef) {
                    this._map = mapRef;
                    const container = (unionCtrl && unionCtrl._container) ? unionCtrl._container : document.createElement('div');
                    if (!unionCtrl || !unionCtrl._container) {
                      container.className = 'maplibregl-ctrl maplibregl-ctrl-group gm-info-ctrl';
                    }
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'maplibregl-ctrl-icon gm-info-button';
                    btn.setAttribute('title', 'Toggle Info');
                    btn.setAttribute('aria-label', 'Toggle Info');
                    btn.setAttribute('aria-pressed', (el._gmShowInfoBox ? 'true' : 'false'));
                    btn.innerHTML = `
                      <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                        <circle cx="12" cy="12" r="9" fill="#ffffff" stroke="#1976D2" stroke-width="1.2"/>
                        <text x="12" y="16" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#1976D2">i</text>
                      </svg>
                    `;
                    btn.style.display = 'flex';
                    btn.style.alignItems = 'center';
                    btn.style.justifyContent = 'center';
                    this._button = btn;
                    this.setPressed(!!el._gmShowInfoBox);
                    btn.addEventListener('click', () => {
                      const next = !(el._gmShowInfoBox === true);
                      el._gmShowInfoBox = next;
                      this.setPressed(next);
                      try {
                        // Deactivate other Geoman tools when info button is enabled
                        if (next) {
                          const geomanInstance = map.gm || el._geomanInstance;
                          const container = geomanInstance?.control?.container;
                          if (container) {
                            const buttons = Array.from(container.querySelectorAll('.gm-control-button'));
                            const getButtonLabel = (b) => ((b.getAttribute('title') || b.getAttribute('aria-label') || (b.textContent ? b.textContent.trim() : '')).toLowerCase());
                            const isActiveButton = (b) => b.getAttribute('aria-pressed') === 'true' || b.classList.contains('active') || b.classList.contains('gm-active');
                            buttons.forEach((b) => {
                              const label = getButtonLabel(b);
                              const isSnap = label.includes('snap');
                              if (!isSnap && isActiveButton(b)) {
                                b.click();
                              }
                            });
                          }
                        }
                        if (!next && typeof el._gmHideInfoBox === 'function') {
                          el._gmHideInfoBox();
                        }
                        if (typeof el._gmAttachInfoHandlers === 'function') {
                          el._gmAttachInfoHandlers();
                        }
                        // Ensure mirror visible when info is enabled and no edit tool active
                        try {
                          if (stylePaint) setGeomanMirrorVisibility(true);
                        } catch (_eVis2) {}
                        const events = model.get("_js_events") || [];
                        model.set("_js_events", [...events, { type: 'geoman_info_toggled', enabled: next }]);
                        model.save_changes();
                      } catch (_e) {}
                    });
                    container.appendChild(btn);
                    this._container = container;
                    return container;
                  }
                  onRemove() {
                    if (this._container && this._button && this._button.parentNode === this._container) {
                      this._container.removeChild(this._button);
                    }
                    this._map = null;
                  }
                }
                const infoCtrl = new InfoToggleControl(model);
                try {
                  infoCtrl.onAdd(map);
                  unionCtrl._container.appendChild(infoCtrl._button);
                  infoCtrl._container = unionCtrl._container;
                } catch (_e) {}
                el._infoControl = infoCtrl;
              } catch (_e) {}

              // Add OSM Transport load control (button appended into union group)
              try {
                class OsmTransportControl {
                  constructor(geomanInstance) {
                    this._geomanInstance = geomanInstance;
                    this._container = null;
                    this._button = null;
                    this._map = null;
                  }
                  onAdd(mapRef) {
                    this._map = mapRef;
                    const container = unionCtrl && unionCtrl._container
                      ? unionCtrl._container
                      : document.createElement('div');
                    if (!unionCtrl || !unionCtrl._container) {
                      container.className = 'maplibregl-ctrl maplibregl-ctrl-group gm-osm-ctrl';
                    }
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'maplibregl-ctrl-icon gm-osm-button';
                    btn.setAttribute('title', 'Load OSM Transport');
                    btn.setAttribute('aria-label', 'Load OSM Transport');
                    btn.innerHTML = `
                      <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                        <!-- Network lines -->
                        <polyline points="4,18 10,12 16,14 20,6" fill="none" stroke="#1976D2" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <!-- Nodes -->
                        <circle cx="4" cy="18" r="2.2" fill="#00AA55" stroke="#0D4D2A" stroke-width="0.8"/>
                        <circle cx="10" cy="12" r="2.2" fill="#00AA55" stroke="#0D4D2A" stroke-width="0.8"/>
                        <circle cx="16" cy="14" r="2.2" fill="#00AA55" stroke="#0D4D2A" stroke-width="0.8"/>
                        <circle cx="20" cy="6" r="2.2" fill="#00AA55" stroke="#0D4D2A" stroke-width="0.8"/>
                      </svg>
                    `;
                    btn.style.display = 'flex';
                    btn.style.alignItems = 'center';
                    btn.style.justifyContent = 'center';
                    btn.addEventListener('click', async () => {
                      try {
                        // Deactivate other tools except snapping
                        const containerEl = this._geomanInstance?.control?.container;
                        if (containerEl) {
                          const buttons = Array.from(containerEl.querySelectorAll('.gm-control-button'));
                          const getButtonLabel = (b) => ((b.getAttribute('title') || b.getAttribute('aria-label') || (b.textContent ? b.textContent.trim() : '')).toLowerCase());
                          const isActiveButton = (b) => b.getAttribute('aria-pressed') === 'true' || b.classList.contains('active') || b.classList.contains('gm-active');
                          buttons.forEach((b) => {
                            const label = getButtonLabel(b);
                            const isSnap = label.includes('snap');
                            if (!isSnap && isActiveButton(b)) b.click();
                          });
                        }
                        await loadOsmTransportToGeoman({});

                        // Workaround: If info button is active, toggle an editing tool then reactivate info
                        // This ensures info button handlers work with newly loaded features
                        if (el._gmShowInfoBox && el._infoControl) {
                          setTimeout(() => {
                            try {
                              const containerEl = this._geomanInstance?.control?.container;
                              if (containerEl) {
                                // Find the remove/delete button
                                const buttons = Array.from(containerEl.querySelectorAll('.gm-control-button'));
                                const getButtonLabel = (b) => ((b.getAttribute('title') || b.getAttribute('aria-label') || (b.textContent ? b.textContent.trim() : '')).toLowerCase());
                                const removeBtn = buttons.find(b => {
                                  const label = getButtonLabel(b);
                                  return label.includes('remov') || label.includes('delete');
                                });
                                if (removeBtn) {
                                  // Activate remove tool briefly
                                  removeBtn.click();
                                  // Then reactivate info button
                                  setTimeout(() => {
                                    if (el._infoControl && el._infoControl._button) {
                                      el._infoControl._button.click();
                                    }
                                  }, 50);
                                }
                              }
                            } catch (_e) {}
                          }, 100);
                        }
                      } catch (err) {
                        console.warn('Failed to load OSM transport:', err);
                      }
                    });
                    container.appendChild(btn);
                    this._container = container;
                    this._button = btn;
                    return container;
                  }
                  onRemove() {
                    try {
                      if (this._container && this._button && this._button.parentNode === this._container) {
                        this._container.removeChild(this._button);
                      }
                    } catch (_e) {}
                    this._map = undefined;
                  }
                }
                const osmCtrl = new OsmTransportControl(instance);
                try {
                  osmCtrl.onAdd(map);
                  // The guard `if (!unionCtrl || !unionCtrl._container)` always evaluates to false.
                  // Therefore, the block is unreachable and has been removed.
                  // If needed, add logic here to handle cases when unionCtrl is not present.
                } catch (_e) {}
                el._osmTransportControl = osmCtrl;
              } catch (_e) {}

              // Observe Geoman toolbar and auto-deactivate Union when another tool turns active
              try {
                const geomanContainer = instance?.control?.container;
                const isActiveButton = (buttonEl) =>
                  buttonEl.getAttribute('aria-pressed') === 'true'
                  || buttonEl.classList.contains('active')
                  || buttonEl.classList.contains('gm-active');
                const getButtonLabel = (buttonEl) =>
                  (buttonEl.getAttribute('title')
                    || buttonEl.getAttribute('aria-label')
                    || (buttonEl.textContent ? buttonEl.textContent.trim() : '')).toLowerCase();
                if (geomanContainer) {
                  const observer = new MutationObserver(() => {
                    const buttons = Array.from(geomanContainer.querySelectorAll('.gm-control-button'));
                    const activeNonSnap = buttons.some((b) => {
                      const label = getButtonLabel(b);
                      const isSnap = label.includes('snap');
                      return !isSnap && isActiveButton(b);
                    });
                    if (activeNonSnap) {
                      if (unionCtrl?._button?.getAttribute('aria-pressed') === 'true') {
                        unionCtrl.setPressed(false);
                        try {
                          const currentEvents = model.get("_js_events") || [];
                          model.set("_js_events", [
                            ...currentEvents,
                            { type: 'geoman_union_toggled', enabled: false }
                          ]);
                          model.save_changes();
                        } catch (_e) {}
                      }
                      if (splitCtrl?._button?.getAttribute('aria-pressed') === 'true') {
                        splitCtrl.setPressed(false);
                        try {
                          const currentEvents = model.get("_js_events") || [];
                          model.set("_js_events", [
                            ...currentEvents,
                            { type: 'geoman_split_toggled', enabled: false }
                          ]);
                          model.save_changes();
                        } catch (_e2) {}
                      }
                      // Also disable info mode to prevent interference with edit/delete tools
                      if (el._gmShowInfoBox) {
                        el._gmShowInfoBox = false;
                        try {
                          if (el._infoControl && el._infoControl._button) {
                            el._infoControl.setPressed(false);
                          }
                          if (typeof el._gmHideInfoBox === 'function') {
                            el._gmHideInfoBox();
                          }
                          const currentEvents = model.get("_js_events") || [];
                          model.set("_js_events", [
                            ...currentEvents,
                            { type: 'geoman_info_toggled', enabled: false }
                          ]);
                          model.save_changes();
                        } catch (_e3) {}
                      }
                    }
                  });
                  observer.observe(geomanContainer, { attributes: true, subtree: true, attributeFilter: ['class', 'aria-pressed'] });
                  el._unionObserver = observer;
                }
              } catch (obsErr) {
                console.warn('Failed to observe Geoman toolbar for union toggle sync:', obsErr);
              }
            } catch (e) {
              console.warn('Failed to add Union toggle control:', e);
            }

            if (typeof initialCollapsed === 'boolean') {
              requestAnimationFrame(() => {
                applyGeomanCollapsedState(instance, initialCollapsed);
              });
            }
          } catch (error) {
            console.error('Failed to initialize MapLibre Geoman control after load:', error);
            el._controls.delete(controlKey);
          }
        });
      } catch (error) {
        console.error('Failed to create MapLibre Geoman instance:', error);
        el._controls.delete(controlKey);
      }
    };

    const geomanModelListener = () => {
      const newData = model.get("geoman_data");

      // If this change originated from a JS export, check if data actually changed
      if (el._geomanSyncFromJs) {
        // Compare the new data with what we last exported
        const lastExported = el._lastExportedData || { type: 'FeatureCollection', features: [] };
        const newDataStr = JSON.stringify(newData);
        const lastExportedStr = JSON.stringify(lastExported);

        if (newDataStr === lastExportedStr) {
          // Data unchanged - skip import to avoid circular updates
          el._geomanSyncFromJs = false;
          return;
        } else {
          // Data changed from Python even though we just exported - process it
          el._geomanSyncFromJs = false;
        }
      }

      // Import data set from Python without re-exporting to avoid feedback loops
      importGeomanData(model.get("geoman_data"), true);

    // Ensure info box handlers are active after data loads using the exposed attach function
    try {
      if (el._gmShowInfoBox && typeof el._gmAttachInfoHandlers === 'function' && !el._gmInfoHandlers) {
        el._gmAttachInfoHandlers();
      }
    } catch (_e) {}
    };

    model.on("change:geoman_data", geomanModelListener);
    el._geomanModelListener = geomanModelListener;

    // Helpers to query Geoman toolbar status and sync to Python
    function getGeomanToolbarStatus(geomanInstance) {
      const status = {
        activeButtons: [],
        isCollapsed: null,
        globalEditMode: false,
      };
      try {
        status.globalEditMode = !!(geomanInstance.globalEditModeEnabled && geomanInstance.globalEditModeEnabled());
      } catch (e) {
        // ignore
      }
      try {
        if (geomanInstance && geomanInstance.control && geomanInstance.control.container) {
          const container = geomanInstance.control.container;
          status.isCollapsed = !container.querySelector('.gm-reactive-controls');
          const buttons = Array.from(container.querySelectorAll('.gm-control-button'));
          buttons.forEach((btn) => {
            const pressed = btn.getAttribute('aria-pressed') === 'true'
              || btn.classList.contains('active')
              || btn.classList.contains('gm-active');
            if (pressed) {
              const label = btn.getAttribute('title')
                || btn.getAttribute('aria-label')
                || (btn.textContent ? btn.textContent.trim() : '');
              if (label) {
                status.activeButtons.push(label);
              }
            }
          });
        }
      } catch (e) {
        // ignore
      }
      return status;
    }

    function updateAndSyncGeomanStatus() {
      try {
        const geomanInstance = map.gm || el._geomanInstance;
        if (!geomanInstance) return;
        const status = getGeomanToolbarStatus(geomanInstance);
        model.set('geoman_status', status);
        model.save_changes();
        // Also forward as event for observers if desired
        const currentEvents = model.get('_js_events') || [];
        model.set('_js_events', [...currentEvents, { type: 'geoman_status', status }]);
        model.save_changes();
      } catch (e) {
        // ignore
      }
    }

    const ensureFlatGeobufLibrary = (() => {
      let loaderPromise = null;

      const hasFlatGeobuf = () =>
        !!(window.flatgeobuf && (window.flatgeobuf.geojson || window.flatgeobuf.deserialize));

      const formatLoadError = (error, src) => {
        if (!error) {
          return `Unknown error loading ${src}`;
        }
        if (error instanceof Event) {
          const target = error.target;
          if (target && target.tagName === 'SCRIPT') {
            return `Failed to load ${src || target.src || 'external script'}`;
          }
          return `Event "${error.type || 'error'}" while loading ${src}`;
        }
        if (typeof error === 'object' && 'message' in error && error.message) {
          return error.message;
        }
        return String(error);
      };

      const loadScript = (src) =>
        new Promise((resolve, reject) => {
          const script = document.createElement('script');
          script.src = src;
          script.async = true;
          script.crossOrigin = 'anonymous';
          script.onload = () => resolve(window.flatgeobuf);
          script.onerror = (error) => {
            script.remove();
            reject(new Error(formatLoadError(error, src)));
          };
          document.head.appendChild(script);
        });

      const tryCdnSources = async () => {
        const cdnSources = [
          'https://unpkg.com/flatgeobuf@latest/dist/flatgeobuf-geojson.min.js',
          'https://cdn.jsdelivr.net/npm/flatgeobuf@latest/dist/flatgeobuf-geojson.min.js',
        ];

        let lastError = null;
        for (const src of cdnSources) {
          try {
            const module = await loadScript(src);
            if (hasFlatGeobuf()) {
              return module || window.flatgeobuf;
            }
          } catch (error) {
            console.warn(`FlatGeobuf loader: ${error.message || error}`);
            lastError = error;
          }
        }
        throw lastError || new Error('Unable to load FlatGeobuf library from CDN sources.');
      };

      return () => {
        if (loaderPromise) {
          return loaderPromise;
        }

        if (hasFlatGeobuf()) {
          loaderPromise = Promise.resolve(window.flatgeobuf);
          loaderPromise.catch(() => {
            loaderPromise = null;
          });
          return loaderPromise;
        }

        if (typeof window.require === 'function') {
          loaderPromise = new Promise((resolve, reject) => {
            try {
              window.require(
                ['flatgeobuf/dist/flatgeobuf-geojson.min'],
                (module) => {
                  if (!window.flatgeobuf) {
                    window.flatgeobuf = module;
                  }
                  resolve(module || window.flatgeobuf);
                },
                async (err) => {
                  console.warn('FlatGeobuf AMD loader failed, falling back to CDN.', err);
                  try {
                    const module = await tryCdnSources();
                    resolve(module);
                  } catch (cdnError) {
                    reject(cdnError);
                  }
                },
              );
            } catch (error) {
              console.warn('FlatGeobuf AMD loader threw synchronously, falling back to CDN.', error);
              tryCdnSources()
                .then((module) => resolve(module))
                .catch((cdnError) => reject(cdnError));
            }
          });
          loaderPromise.catch(() => {
            loaderPromise = null;
          });
          return loaderPromise;
        }

        loaderPromise = tryCdnSources();
        loaderPromise.catch(() => {
          loaderPromise = null;
        });
        return loaderPromise;
      };
    })();

    async function loadFlatGeobufGeoJSON(url, bbox) {
      await ensureFlatGeobufLibrary();

      const normalizeBBox = (value) => {
        if (!value) {
          return undefined;
        }
        if (Array.isArray(value)) {
          if (value.length !== 4) {
            console.warn('FlatGeobuf bbox array must have four numbers [minX, minY, maxX, maxY].', value);
            return undefined;
          }
          const [minX, minY, maxX, maxY] = value;
          if ([minX, minY, maxX, maxY].some((v) => typeof v !== 'number' || Number.isNaN(v))) {
            console.warn('FlatGeobuf bbox array contains non-numeric values.', value);
            return undefined;
          }
          return { minX, minY, maxX, maxY };
        }
        if (typeof value === 'object') {
          const { minX, minY, maxX, maxY } = value;
          if ([minX, minY, maxX, maxY].some((v) => typeof v !== 'number' || Number.isNaN(v))) {
            console.warn('FlatGeobuf bbox object contains invalid values.', value);
            return undefined;
          }
          return { minX, minY, maxX, maxY };
        }
        console.warn('FlatGeobuf bbox must be an array or object.', value);
        return undefined;
      };

      if (!url || typeof url !== 'string') {
        throw new Error('FlatGeobuf layer requires a URL string.');
      }

      const normalizedBBox = normalizeBBox(bbox);
      const effectiveBBox =
        normalizedBBox ||
        {
          minX: -1e12,
          minY: -1e12,
          maxX: 1e12,
          maxY: 1e12,
        };

      const module = (window.flatgeobuf && (window.flatgeobuf.geojson || window.flatgeobuf)) || {};
      const deserialize = module.deserialize || (module.geojson && module.geojson.deserialize);
      if (!deserialize) {
        throw new Error('FlatGeobuf deserialize helper is unavailable.');
      }

      let iterable;
      try {
        const options = normalizedBBox || effectiveBBox;
        iterable = deserialize(url, options);
      } catch (error) {
        console.warn('FlatGeobuf deserialize failed, retrying without bbox.', error);
        iterable = deserialize(url, effectiveBBox);
      }

      const features = [];

      if (iterable && typeof iterable[Symbol.asyncIterator] === 'function') {
        try {
          for await (const feature of iterable) {
            features.push(feature);
          }
        } catch (error) {
          console.warn('FlatGeobuf streaming failed, retrying without bbox.', error);
          const retryIterable = deserialize(url, effectiveBBox);
          for await (const feature of retryIterable) {
            features.push(feature);
          }
        }
        return { type: 'FeatureCollection', features };
      }

      const maybeGeoJSON = await iterable;
      if (maybeGeoJSON && Array.isArray(maybeGeoJSON.features)) {
        return maybeGeoJSON;
      }

      throw new Error('Unexpected response from FlatGeobuf deserialize helper.');
    }

    async function addFlatGeobufLayerFromConfig(layerConfig, { logErrors = true } = {}) {
      if (!layerConfig || !layerConfig.url) {
        if (logErrors) {
          console.warn('FlatGeobuf layer configuration missing url.', layerConfig);
        }
        return;
      }

      const layerId = layerConfig.layerId || layerConfig.id;
      const sourceId = layerConfig.sourceId || `${layerId}_source`;
      const layerType = layerConfig.layerType || layerConfig.type || 'fill';

      try {
        const geojson = await loadFlatGeobufGeoJSON(layerConfig.url, layerConfig.bbox);

        if (map.getSource(sourceId)) {
          map.getSource(sourceId).setData(geojson);
        } else {
          map.addSource(sourceId, {
            type: 'geojson',
            data: geojson,
          });
        }

        if (map.getLayer(layerId)) {
          map.removeLayer(layerId);
        }

        const layerDefinition = {
          id: layerId,
          type: layerType,
          source: sourceId,
        };

        if (layerConfig.paint) {
          layerDefinition.paint = layerConfig.paint;
        }
        if (layerConfig.layout) {
          layerDefinition.layout = layerConfig.layout;
        }
        if (layerConfig.filter) {
          layerDefinition.filter = layerConfig.filter;
        }
        if (layerConfig.promoteId !== undefined) {
          layerDefinition.promoteId = layerConfig.promoteId;
        }
        if (layerConfig.minzoom !== undefined) {
          layerDefinition.minzoom = layerConfig.minzoom;
        }
        if (layerConfig.maxzoom !== undefined) {
          layerDefinition.maxzoom = layerConfig.maxzoom;
        }
        if (layerConfig.metadata) {
          layerDefinition.metadata = layerConfig.metadata;
        }

        map.addLayer(layerDefinition, layerConfig.beforeId || undefined);
        el._flatgeobufLayers.set(layerId, { sourceId, layerConfig });
      } catch (error) {
        if (logErrors) {
          console.error('Failed to add FlatGeobuf layer:', error);
        }
      }
    }

    function removeFlatGeobufLayer(layerId) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
      const current = el._flatgeobufLayers.get(layerId);
      if (current && current.sourceId && map.getSource(current.sourceId)) {
        map.removeSource(current.sourceId);
      }
      el._flatgeobufLayers.delete(layerId);
      detachFeaturePopup(layerId);
    }

    async function syncFlatGeobufLayers() {
      const configuredLayers = model.get('flatgeobuf_layers') || {};
      const desiredIds = new Set(Object.keys(configuredLayers));

      for (const layerId of desiredIds) {
        const layerConfig = configuredLayers[layerId];
        await addFlatGeobufLayerFromConfig(layerConfig);
        attachFeaturePopup(layerId);
      }

      for (const existingId of Array.from(el._flatgeobufLayers.keys())) {
        if (!desiredIds.has(existingId)) {
          removeFlatGeobufLayer(existingId);
        }
      }
    }

    model.on('change:flatgeobuf_layers', () => {
      if (el._mapReady) {
        syncFlatGeobufLayers();
      } else {
        el._pendingFlatGeobufSync = true;
      }
    });

    const escapeHtml = (value) => {
      if (value === null || value === undefined) {
        return '';
      }
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    };

    const formatPopupValue = (value) => {
      if (value === null || value === undefined) {
        return '';
      }
      if (typeof value === 'object') {
        try {
          return JSON.stringify(value);
        } catch (_err) {
          return String(value);
        }
      }
      return String(value);
    };

    function renderPopupContent(config, feature) {
      if (!feature || !feature.properties) {
        return '';
      }
      const properties = feature.properties || {};

      // If template is provided, use it
      if (config.template && typeof config.template === 'string') {
        const template = config.template;
        // Replace {{property}} or {property} with actual values
        const rendered = template.replace(/\{\{(\w+)\}\}|\{(\w+)\}/g, (match, doubleBraced, singleBraced) => {
          const propName = doubleBraced || singleBraced;
          const value = properties[propName];
          return value !== undefined && value !== null ? escapeHtml(String(value)) : '';
        });
        return `<div class="anymap-popup">${rendered}</div>`;
      }

      const fieldDefs = Array.isArray(config.fields) ? config.fields : null;
      const maxProperties =
        typeof config.maxProperties === 'number' && config.maxProperties > 0
          ? config.maxProperties
          : 25;

      let rows = [];
      if (fieldDefs && fieldDefs.length > 0) {
        rows = fieldDefs.map((def) => {
          const fieldName = def && def.name !== undefined ? def.name : def;
          const label = (def && def.label !== undefined ? def.label : fieldName);
          const value = properties[fieldName];
          return {
            label: label !== undefined ? label : fieldName,
            value: formatPopupValue(value),
          };
        });
      } else {
        rows = Object.keys(properties)
          .slice(0, maxProperties)
          .map((key) => ({
            label: key,
            value: formatPopupValue(properties[key]),
          }));
      }

      const title =
        config.title !== undefined && config.title !== null
          ? config.title
          : config.titleField && properties[config.titleField] !== undefined
            ? properties[config.titleField]
            : null;

      let html = '<div class="anymap-popup">';
      if (title) {
        html += `<div class="anymap-popup__title">${escapeHtml(title)}</div>`;
      }

      if (!rows.length) {
        html += '<div class="anymap-popup__empty">No attributes</div>';
      } else {
        html += '<table class="anymap-popup__table">';
        rows.forEach((row) => {
          html += `<tr><th>${escapeHtml(row.label)}</th><td>${escapeHtml(row.value)}</td></tr>`;
        });
        html += '</table>';
      }

      html += '</div>';
      return html;
    }

    function detachFeaturePopup(layerId, { keepConfig = false } = {}) {
      const handler = el._featurePopupHandlers.get(layerId);
      if (handler) {
        map.off('click', layerId, handler.click);
        map.off('mouseenter', layerId, handler.enter);
        map.off('mouseleave', layerId, handler.leave);
        if (
          handler.state &&
          handler.state.popup &&
          typeof handler.state.popup.remove === 'function'
        ) {
          handler.state.popup.remove();
        }
        el._featurePopupHandlers.delete(layerId);
      }
      if (!keepConfig) {
        el._featurePopupConfigs.delete(layerId);
      }
    }

    function attachFeaturePopup(layerId) {
      if (!el._featurePopupConfigs.has(layerId)) {
        return;
      }
      const config = el._featurePopupConfigs.get(layerId);
      if (!map.getLayer(layerId)) {
        return;
      }

      detachFeaturePopup(layerId, { keepConfig: true });

      const popupState = { popup: null };
      const maxWidth = typeof config.maxWidth === 'string' ? config.maxWidth : '320px';
      const trigger = config.trigger || 'click'; // Default to 'click' if not specified

      const showPopup = (event) => {
        const feature = event && event.features && event.features[0];
        if (!feature) {
          if (popupState.popup) {
            popupState.popup.remove();
            popupState.popup = null;
          }
          return;
        }

        const content = renderPopupContent(config, feature);
        if (!content) {
          if (popupState.popup) {
            popupState.popup.remove();
            popupState.popup = null;
          }
          return;
        }

        if (popupState.popup) {
          popupState.popup.remove();
        }

        const isHoverTrigger = trigger === 'hover';
        popupState.popup = new maplibregl.Popup({
          closeButton: isHoverTrigger ? false : (config.closeButton !== false),
          closeOnClick: !isHoverTrigger,
          maxWidth,
        })
          .setLngLat(event.lngLat)
          .setHTML(content)
          .addTo(map);

        popupState.popup.on('close', () => {
          popupState.popup = null;
        });
      };

      const clickHandler = (event) => {
        if (trigger === 'click') {
          showPopup(event);
        }
      };

      const enterHandler = (event) => {
        map.getCanvas().style.cursor = 'pointer';
        if (trigger === 'hover') {
          showPopup(event);
        }
      };

      const leaveHandler = () => {
        map.getCanvas().style.cursor = '';
        if (trigger === 'hover' && popupState.popup) {
          popupState.popup.remove();
          popupState.popup = null;
        }
      };

      map.on('click', layerId, clickHandler);
      map.on('mouseenter', layerId, enterHandler);
      map.on('mouseleave', layerId, leaveHandler);

      el._featurePopupHandlers.set(layerId, {
        click: clickHandler,
        enter: enterHandler,
        leave: leaveHandler,
        state: popupState,
      });
    }

    function refreshFeaturePopups() {
      if (!el._featurePopupConfigs || el._featurePopupConfigs.size === 0) {
        return;
      }
      el._featurePopupConfigs.forEach((_config, layerId) => {
        attachFeaturePopup(layerId);
      });
    }

    function enableFeaturePopup(config = {}) {
      const layerId = config.layerId;
      if (!layerId) {
        console.warn('enableFeaturePopup requires a layerId.', config);
        return;
      }

      el._featurePopupConfigs.set(layerId, {
        ...config,
      });
      attachFeaturePopup(layerId);
    }

    function disableFeaturePopup(layerId) {
      if (!layerId) {
        return;
      }
      detachFeaturePopup(layerId, { keepConfig: false });
    }

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

            // Get beforeId from layer metadata if it was stored
            const beforeId = layerConfig.metadata && layerConfig.metadata.beforeId;

            if (isCogLayer && !window._cogProtocolRegistered) {
              // Retry adding COG-dependent layers after source is ready
              setTimeout(() => {
                if (!map.getLayer(layerId) && map.getSource(sourceId)) {
                  try {
                    if (beforeId) {
                      map.addLayer(layerConfig, beforeId);
                    } else {
                      map.addLayer(layerConfig);
                    }
                    console.log(`COG layer ${layerId} added successfully on retry`);
                  } catch (retryError) {
                    console.warn(`Failed to add COG layer ${layerId} on retry:`, retryError);
                  }
                }
              }, 600);
            } else {
              // Restore layer with beforeId if it was specified
              if (beforeId) {
                map.addLayer(layerConfig, beforeId);
              } else {
                map.addLayer(layerConfig);
              }
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

                  debugLog('Draw control restored successfully with custom styles');
                } else {
                  console.warn('MapboxDraw not available or already added during restore');
                }
                return;
              case 'layer_control':
                // Handle layer control restoration
                control = new LayerControl(controlOptions || {}, map, model, el);
                break;
              case 'geoman': {
                scheduleGeomanInitialization(controlKey, {
                  position,
                  geoman_options: controlOptions?.geoman_options || {},
                  collapsed: controlOptions?.collapsed,
                  show_info_box: controlOptions?.show_info_box,
                  info_box_mode: controlOptions?.info_box_mode,
                  info_box_tolerance: controlOptions?.info_box_tolerance,
                  geoman_paint: controlOptions?.geoman_paint,
                  geoman_paint_above: controlOptions?.geoman_paint_above,
                });
                return;
              }
              case 'export': {
                const ExportControlClass = resolveExportControlClass();
                if (!ExportControlClass) {
                  console.warn('MapLibre export control not available during restore');
                  return;
                }
                const { options: exportOptions, startCollapsed } = normalizeExportControlOptions(
                  controlOptions || {},
                );
                control = new ExportControlClass(exportOptions);
                control.__anymapStartCollapsed = startCollapsed;
                break;
              }
              case 'geogrid': {
                const GeoGridClass = resolveGeoGridClass();
                if (!GeoGridClass) {
                  console.warn('GeoGrid plugin not available during restore');
                  return;
                }
                // Remove position from options as GeoGrid doesn't use it
                const { position: _, gridStyle, labelStyle, ...otherConfig } = controlOptions || {};

                // Map MapLibre paint properties to GeoGrid style properties
                const geogridOptions = {
                  map,
                  ...otherConfig,
                  ...(gridStyle && { gridStyle: mapToGeoGridStyle(gridStyle) }),
                  ...(labelStyle && { labelStyle: mapToGeoGridStyle(labelStyle) })
                };

                try {
                  const geogridInstance = new GeoGridClass(geogridOptions);

                  // Explicitly call add() to render the grid on the map
                  if (typeof geogridInstance.add === 'function') {
                    geogridInstance.add();
                  }

                  el._geogridInstance = geogridInstance;
                  el._controls.set(controlKey, { type: 'geogrid', instance: geogridInstance });
                } catch (error) {
                  console.error('Failed to restore GeoGrid instance:', error);
                }
                return;
              }
              case 'widget_panel':
                control = new WidgetPanelControl(controlOptions || {}, map, model);
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
              case 'measures':
                // Handle measures control restoration
                if (window.MeasuresControl) {
                  try {
                    const measuresOptions = controlOptions.measures_options || {};
                    control = new window.MeasuresControl(measuresOptions);
                    console.log('Measures control restored successfully');
                  } catch (error) {
                    console.error('Failed to restore Measures control:', error);
                    return;
                  }
                } else {
                  console.warn('MeasuresControl not available during restore');
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
              case 'temporal':
                // Handle temporal control restoration
                if (window.TemporalControl) {
                  // Separate frames from options and resolve layer ids to layer objects
                  const framesInput = (controlOptions && Array.isArray(controlOptions.frames)) ? controlOptions.frames : [];
                  const { position: _ignoredPosition, frames: _ignoredFrames, ...restTemporalOpts } = controlOptions || {};

                  const temporalFrames = framesInput.map((frame, idx) => {
                    const frameLayers = (frame && Array.isArray(frame.layers)) ? frame.layers : [];
                    const resolvedLayers = frameLayers.map((layerOrId) => {
                      if (typeof layerOrId === 'string') {
                        const style = map.getStyle && map.getStyle();
                        const layerObj = (style && Array.isArray(style.layers)) ? style.layers.find((ly) => ly.id === layerOrId) : undefined;
                        if (!layerObj) {
                          console.warn(`Temporal control restore: layer id not found: ${layerOrId}`);
                        }
                        return layerObj || null;
                      }
                      return layerOrId;
                    }).filter(Boolean);

                    return {
                      title: frame && frame.title !== undefined ? frame.title : `Frame ${idx + 1}`,
                      layers: resolvedLayers,
                    };
                  });

                  const temporalOptions = {
                    interval: restTemporalOpts.interval || 1000,
                    performance: restTemporalOpts.performance || false,
                    ...restTemporalOpts,
                  };

                  control = new window.TemporalControl(temporalFrames, temporalOptions);
                  console.log('Temporal control restored successfully');
                } else {
                  console.warn('TemporalControl not available during restore');
                  return;
                }
                break;
              case 'infobox': {
                if (!window.MapboxInfoBoxControl && window.InfoBoxControl) {
                  window.MapboxInfoBoxControl = window.InfoBoxControl;
                }
                if (!window.MapboxInfoBoxControl) {
                  console.warn('MapboxInfoBoxControl not available during restore');
                  return;
                }
                try {
                  const { position: _pos, formatter, formatter_template, ...other } = controlOptions || {};
                  let finalOptions = { showOnHover: true, showOnClick: true, ...other };
                  if (typeof formatter === 'function') {
                    finalOptions.formatter = formatter;
                  } else if (typeof formatter === 'string' && formatter.length > 0) {
                    const template = formatter;
                    finalOptions.formatter = (properties) => {
                      const safe = properties || {};
                      return template.replace(/\{\{?\s*(\w+)\s*\}?\}/g, (_, k) => (safe[k] ?? ''));
                    };
                  } else if (typeof formatter_template === 'string' && formatter_template.length > 0) {
                    const template = formatter_template;
                    finalOptions.formatter = (properties) => {
                      const safe = properties || {};
                      return template.replace(/\{\{?\s*(\w+)\s*\}?\}/g, (_, k) => (safe[k] ?? ''));
                    };
                  }
                  const base = new window.MapboxInfoBoxControl(finalOptions);
                  const targetLayerId = finalOptions.layerId || finalOptions.layerID || finalOptions.layer || null;
                  control = {
                    onAdd(m) {
                      const el = base.onAdd(m);
                      try {
                        if (el && el.classList) {
                          el.classList.add('maplibregl-ctrl');
                          el.classList.add('maplibregl-ctrl-group');
                          if (!el.style.margin) {
                            el.style.margin = '10px';
                          }
                        }
                        // Provide a reliable content box in case plugin doesn't render one until events
                        let content = el.querySelector('.anymap-infobox-content');
                        if (!content) {
                          content = document.createElement('div');
                          content.className = 'anymap-infobox-content';
                          content.style.background = 'rgba(255,255,255,0.95)';
                          content.style.borderRadius = '4px';
                          content.style.padding = '6px 8px';
                          content.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';
                          content.style.fontSize = '12px';
                          content.style.maxWidth = '260px';
                          content.style.display = 'none';
                          el.appendChild(content);
                        }
                        // Attach hover/click listeners to populate content from layer features
                        if (targetLayerId) {
                          const updateFromPoint = (pt) => {
                            try {
                              const feats = m.queryRenderedFeatures(pt, { layers: [targetLayerId] });
                              if (feats && feats.length > 0) {
                                const props = feats[0].properties || {};
                                const html = (typeof finalOptions.formatter === 'function')
                                  ? finalOptions.formatter(props)
                                  : Object.keys(props).map(k => `<div><b>${k}</b>: ${props[k]}</div>`).join('');
                                if (html && html.length > 0) {
                                  content.innerHTML = html;
                                  content.style.display = '';
                                } else {
                                  content.style.display = 'none';
                                }
                              } else {
                                content.style.display = 'none';
                              }
                            } catch (e) {
                              // ignore
                            }
                          };
                          if (finalOptions.showOnHover !== false) {
                            m.on('mousemove', (ev) => updateFromPoint(ev.point));
                          }
                          if (finalOptions.showOnClick !== false) {
                            m.on('click', (ev) => updateFromPoint(ev.point));
                          }
                        }
                      } catch (_) {}
                      return el;
                    },
                    onRemove(m) { if (typeof base.onRemove === 'function') base.onRemove(m); },
                    updateOptions: base.updateOptions ? base.updateOptions.bind(base) : undefined,
                  };
                  console.log('InfoBox control restored successfully');
                } catch (error) {
                  console.error('Failed to restore InfoBox control:', error);
                  return;
                }
                break;
              }
              case 'gradientbox': {
                if (!window.MapboxGradientBoxControl && window.GradientBoxControl) {
                  window.MapboxGradientBoxControl = window.GradientBoxControl;
                }
                if (!window.MapboxGradientBoxControl) {
                  console.warn('MapboxGradientBoxControl not available during restore');
                  return;
                }
                try {
                  const { position: _pos, weight_property, minMaxValues, ...other } = controlOptions || {};
                  const options = normalizeGradientOptions({ ...other, minMaxValues });
                  if (!options.minMaxValues && (other.min_value != null || other.max_value != null)) {
                    options.minMaxValues = { minValue: other.min_value ?? 0, maxValue: other.max_value ?? 1 };
                  } else if (minMaxValues) {
                    options.minMaxValues = minMaxValues;
                  }
                  if (weight_property && typeof weight_property === 'string') {
                    options.weightGetter = (properties) => {
                      const p = properties || {};
                      const val = p[weight_property];
                      const num = Number(val);
                      return Number.isFinite(num) ? num : 0;
                    };
                  }
                  // Expand min/max to multiple common shapes so various builds pick them up
                  const minVal = (options.min_value != null) ? Number(options.min_value) : (options.minMaxValues?.minValue ?? options.min ?? options.domain?.[0]);
                  const maxVal = (options.max_value != null) ? Number(options.max_value) : (options.minMaxValues?.maxValue ?? options.max ?? options.domain?.[1]);
                  if (Number.isFinite(minVal) && Number.isFinite(maxVal)) {
                    options.minValue = minVal; // common
                    options.maxValue = maxVal;
                    options.minMaxValues = { minValue: minVal, maxValue: maxVal };
                    options.minMax = { min: minVal, max: maxVal };
                    options.domain = [minVal, maxVal];
                  }
                  const base = new window.MapboxGradientBoxControl(options);
                  control = {
                    onAdd(m) {
                      const el = base.onAdd(m);
                      try {
                        if (el && el.classList) {
                          el.classList.add('maplibregl-ctrl');
                          el.classList.add('maplibregl-ctrl-group');
                          if (!el.style.margin) {
                            el.style.margin = '10px';
                          }
                        }
                      } catch (_) {}
                      return el;
                    },
                    onRemove(m) { if (typeof base.onRemove === 'function') base.onRemove(m); },
                    updateOptions: base.updateOptions ? base.updateOptions.bind(base) : undefined,
                  };
                  console.log('GradientBox control restored successfully');
                } catch (error) {
                  console.error('Failed to restore GradientBox control:', error);
                  return;
                }
                break;
              }
              case 'legend': {
                const { position: _pos, ...other } = controlOptions || {};
                scheduleLegendInitialization(controlKey, { position, options: other }, map, el);
                return;
              }
              case 'html': {
                // Restore HTML control
                const htmlContent = controlOptions.html || '';
                const bgColor = controlOptions.bgColor || 'white';

                control = {
                  onAdd(map) {
                    const container = document.createElement('div');
                    container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
                    container.style.background = bgColor;
                    container.style.padding = '10px';
                    container.style.borderRadius = '4px';
                    container.style.boxShadow = '0 0 0 2px rgba(0,0,0,0.1)';
                    container.innerHTML = htmlContent;
                    this._container = container;
                    return container;
                  },
                  onRemove() {
                    if (this._container && this._container.parentNode) {
                      this._container.parentNode.removeChild(this._container);
                    }
                    this._container = null;
                  },
                  updateHTML(newHTML) {
                    if (this._container) {
                      this._container.innerHTML = newHTML;
                    }
                  },
                  updateBgColor(newColor) {
                    if (this._container) {
                      this._container.style.background = newColor;
                    }
                  }
                };
                console.log('HTML control restored successfully');
                break;
              }
              default:
                console.warn(`Unknown control type during restore: ${controlType}`);
                return;
            }

            map.addControl(control, position);
            if (controlType === 'export') {
              applyExportControlCollapsedState(
                control,
                control.__anymapStartCollapsed !== false,
              );
            }
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

      syncFlatGeobufLayers();
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

        // Check if there are already calls in _js_calls that haven't been processed
        const existingCalls = model.get("_js_calls") || [];
        if (existingCalls.length > 0) {
          existingCalls.forEach(call => {
            executeMapMethod(map, call, el);
          });
          // Clear them
          model.set("_js_calls", []);
          model.save_changes();
        }

        // Process any pending calls that came in before map was ready
        if (el._pendingCalls && el._pendingCalls.length > 0) {
          el._pendingCalls.forEach(call => {
            executeMapMethod(map, call, el);
          });
          el._pendingCalls = [];
        } else {
        }

        if (el._pendingFlatGeobufSync) {
          syncFlatGeobufLayers();
          el._pendingFlatGeobufSync = false;
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
      refreshFeaturePopups();
    });

    map.on('click', (e) => {
      const clickData = {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat
      };
      // Update the clicked trait immediately
      model.set("clicked", clickData);
      model.save_changes();
      // Also send as event for backwards compatibility
      sendEvent('click', {
        lngLat: [e.lngLat.lng, e.lngLat.lat],
        point: [e.point.x, e.point.y]
      });
    });

    // Pointer interaction events for Python-side on_interaction()
    map.on('mousemove', (e) => {
      sendEvent('mousemove', {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        point: [e.point.x, e.point.y]
      });
    });

    map.on('mousedown', (e) => {
      sendEvent('mousedown', {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        point: [e.point.x, e.point.y]
      });
    });

    map.on('mouseup', (e) => {
      sendEvent('mouseup', {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        point: [e.point.x, e.point.y]
      });
    });

    map.on('dblclick', (e) => {
      sendEvent('dblclick', {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        point: [e.point.x, e.point.y]
      });
    });

    map.on('contextmenu', (e) => {
      sendEvent('contextmenu', {
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        point: [e.point.x, e.point.y]
      });
    });

    map.on('styledata', () => {
      refreshFeaturePopups();
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

      if (el._mapReady) {
        // Map is ready, execute calls immediately
        calls.forEach(call => {
          executeMapMethod(map, call, el);
        });
      } else {
        // Map not ready yet, queue the calls
        el._pendingCalls.push(...calls);
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
            const [layerConfig, beforeId] = args;
            const actualLayerId = layerConfig.id;

            // If layer already exists, remove it first to allow re-adding with new position
            if (map.getLayer(actualLayerId)) {
              try {
                map.removeLayer(actualLayerId);
              } catch (error) {
                console.error('[addLayer] Error removing existing layer:', error);
              }
            }

            try {
              // Pass beforeId to map.addLayer if provided
              if (beforeId) {
                map.addLayer(layerConfig, beforeId);
              } else {
                map.addLayer(layerConfig);
              }
              // Persist layer in model state
              const currentLayers = model.get("_layers") || {};
              currentLayers[actualLayerId] = layerConfig;
              model.set("_layers", currentLayers);
              model.save_changes();
              attachFeaturePopup(actualLayerId);
            } catch (error) {
              console.error('[addLayer] Error adding layer:', error);
              // Try adding without beforeId as fallback
              if (beforeId) {
                try {
                  map.addLayer(layerConfig);
                  const currentLayers = model.get("_layers") || {};
                  currentLayers[actualLayerId] = layerConfig;
                  model.set("_layers", currentLayers);
                  model.save_changes();
                  attachFeaturePopup(actualLayerId);
                } catch (retryError) {
                  console.error('[addLayer] Retry also failed:', retryError);
                }
              }
            }
            break;

          case 'addFlatGeobufLayer':
            const flatgeobufConfig = args[0] || {};
            addFlatGeobufLayerFromConfig(flatgeobufConfig);
            if (flatgeobufConfig && (flatgeobufConfig.layerId || flatgeobufConfig.id)) {
              attachFeaturePopup(flatgeobufConfig.layerId || flatgeobufConfig.id);
            }
            break;

          case 'removeFlatGeobufLayer':
            const targetFlatLayerId = args[0];
            if (targetFlatLayerId) {
              removeFlatGeobufLayer(targetFlatLayerId);
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
              detachFeaturePopup(removeLayerId);
            }
            break;

          case 'setStyle':
            map.setStyle(args[0]);
            break;

          case 'enableFeaturePopup':
            enableFeaturePopup(args[0] || {});
            break;

          case 'disableFeaturePopup':
            const disableArg = args[0];
            const targetLayer =
              disableArg && typeof disableArg === 'object' ? disableArg.layerId : disableArg;
            disableFeaturePopup(targetLayer);
            break;

          case 'addMarker':
            const markerData = args[0];
            const markerOptions = markerData.options || {};

            // Extract scale option (not a native MapLibre option)
            const markerScale = markerOptions.scale || 1.0;
            delete markerOptions.scale; // Remove before passing to MapLibre

            const marker = new maplibregl.Marker(markerOptions)
              .setLngLat(markerData.coordinates)
              .addTo(map);

            // Apply scale to the marker's inner element so MapLibre updates to the outer
            // transform (positioning) do not overwrite the sizing.
            if (markerScale !== 1.0) {
              const markerElement = marker.getElement();
              const markerInner = markerElement.querySelector('svg') || markerElement.firstElementChild;
              if (markerInner) {
                markerInner.style.transform = `scale(${markerScale})`;
                markerInner.style.transformOrigin = 'center center';
              }
            }

            if (markerData.popup) {
              const popup = new maplibregl.Popup()
                .setHTML(markerData.popup);
              marker.setPopup(popup);
            }

            // Add tooltip support (shows on hover)
            if (markerData.tooltip) {
              const tooltip = new maplibregl.Popup({
                closeButton: false,
                closeOnClick: false,
                className: 'marker-tooltip'
              }).setHTML(markerData.tooltip);

              const markerElement = marker.getElement();
              markerElement.addEventListener('mouseenter', () => {
                tooltip.setLngLat(markerData.coordinates).addTo(map);
              });
              markerElement.addEventListener('mouseleave', () => {
                tooltip.remove();
              });
            }

            el._markers.push(marker);
            break;

          case 'addMarkerGroup':
            const groupData = args[0];
            const layerId = groupData.layerId;
            const markers = groupData.markers || [];
            const groupVisible = groupData.visible !== false;
            const groupOpacity = groupData.opacity !== undefined ? groupData.opacity : 1.0;

            // Create array to store markers in this group
            const markerGroup = [];

            // Create each marker in the group
            markers.forEach((markerDef) => {
              const markerOpts = markerDef.options || {};
              const markerScale = markerDef.scale || 1.0;

              const groupMarker = new maplibregl.Marker(markerOpts)
                .setLngLat([markerDef.lng, markerDef.lat])
                .addTo(map);

              // Apply scale
              if (markerScale !== 1.0) {
                const markerEl = groupMarker.getElement();
                const markerInner = markerEl.querySelector('svg') || markerEl.firstElementChild;
                if (markerInner) {
                  markerInner.style.transform = `scale(${markerScale})`;
                  markerInner.style.transformOrigin = 'center center';
                }
              }

              // Apply opacity
              if (groupOpacity !== 1.0) {
                const markerEl = groupMarker.getElement();
                markerEl.style.opacity = groupOpacity;
              }

              // Apply visibility
              if (!groupVisible) {
                const markerEl = groupMarker.getElement();
                markerEl.style.display = 'none';
              }

              // Add popup if provided
              if (markerDef.popup) {
                const popup = new maplibregl.Popup().setHTML(markerDef.popup);
                groupMarker.setPopup(popup);
              }

              // Add tooltip if provided
              if (markerDef.tooltip) {
                const tooltip = new maplibregl.Popup({
                  closeButton: false,
                  closeOnClick: false,
                  className: 'marker-tooltip'
                }).setHTML(markerDef.tooltip);

                const markerEl = groupMarker.getElement();
                markerEl.addEventListener('mouseenter', () => {
                  tooltip.setLngLat([markerDef.lng, markerDef.lat]).addTo(map);
                });
                markerEl.addEventListener('mouseleave', () => {
                  tooltip.remove();
                });
              }

              markerGroup.push(groupMarker);
            });

            // Store the marker group
            el._markerGroups.set(layerId, markerGroup);

            // Trigger layer control to update and show the new marker group
            // Find any layer control instances and trigger checkForNewLayers
            if (el._controls) {
              el._controls.forEach((control) => {
                if (control && typeof control.checkForNewLayers === 'function') {
                  setTimeout(() => {
                    control.checkForNewLayers();
                  }, 50);
                }
              });
            }
            break;

          case 'setMarkerGroupVisibility':
            const markerGroupVisLayerId = args[0];
            const markerGroupVisible = args[1];
            const visMarkerGroup = el._markerGroups.get(markerGroupVisLayerId);

            if (visMarkerGroup) {
              visMarkerGroup.forEach((marker) => {
                const markerEl = marker.getElement();
                markerEl.style.display = markerGroupVisible ? '' : 'none';
              });
            }
            break;

          case 'setMarkerGroupOpacity':
            const markerGroupOpacityLayerId = args[0];
            const markerGroupOpacity = args[1];
            const opacityMarkerGroup = el._markerGroups.get(markerGroupOpacityLayerId);

            if (opacityMarkerGroup) {
              opacityMarkerGroup.forEach((marker) => {
                const markerEl = marker.getElement();
                markerEl.style.opacity = markerGroupOpacity;
              });
            }
            break;

          case 'removeMarkerGroup':
            const markerGroupRemoveLayerId = args[0];
            const removeMarkerGroup = el._markerGroups.get(markerGroupRemoveLayerId);

            if (removeMarkerGroup) {
              // Remove all markers in the group from the map
              removeMarkerGroup.forEach((marker) => marker.remove());
              // Remove the group from tracking
              el._markerGroups.delete(markerGroupRemoveLayerId);
            }
            break;

          case 'fitBounds':
            const [bounds, options] = args;
            // bounds are already in [[lng,lat], [lng,lat]] format
            map.fitBounds(bounds, options || {});
            break;

          case 'addControl':
            const [controlType, controlOptions] = args;
            const position = controlOptions?.position || 'top-right';
            const controlIdForKey = controlType === 'widget_panel'
              ? (controlOptions?.control_id || `widget_panel_${Date.now()}`)
              : null;
            if (controlType === 'widget_panel' && controlOptions && !controlOptions.control_id) {
              controlOptions.control_id = controlIdForKey;
            }
            const controlKey = controlType === 'widget_panel'
              ? `widget_panel_${controlIdForKey}`
              : controlType === 'html'
              ? `html_${controlOptions?.control_id || `${position}_${Date.now()}`}`
              : `${controlType}_${position}`;

            // Normalize gradient options for multiple plugin builds
            const normalizeGradientOptions = (options) => {
              const out = { ...(options || {}) };
              const domain = Array.isArray(out.domain) ? out.domain : undefined;
              const minVal = (out.min_value != null) ? Number(out.min_value)
                : (out.minMaxValues?.minValue ?? out.min ?? (domain ? domain[0] : undefined));
              const maxVal = (out.max_value != null) ? Number(out.max_value)
                : (out.minMaxValues?.maxValue ?? out.max ?? (domain ? domain[1] : undefined));
              if (Number.isFinite(minVal) && Number.isFinite(maxVal)) {
                out.minValue = minVal;
                out.maxValue = maxVal;
                out.minMaxValues = { minValue: minVal, maxValue: maxVal };
                out.minMax = { min: minVal, max: maxVal };
                out.domain = [minVal, maxVal];
              }
              if (Array.isArray(out.colors)) {
                out.colorRamp = out.colors;
                out.palette = out.colors;
                out.gradient = out.colors;
              }
              return out;
            };

            // Check if this control is already added
            if (el._controls.has(controlKey)) {
              const existingControl = el._controls.get(controlKey);

              // For HTML controls, remove and recreate instead of updating
              if (controlType === 'html') {
                map.removeControl(existingControl);
                el._controls.delete(controlKey);
              } else if (
                existingControl &&
                typeof existingControl.updateOptions === 'function' &&
                controlOptions &&
                Object.keys(controlOptions).length > 0
              ) {
                try {
                  const normalized = controlType === 'gradientbox' ? normalizeGradientOptions(controlOptions) : controlOptions;
                  existingControl.updateOptions(normalized);
                } catch (updateError) {
                  console.debug(
                    `Failed to refresh options for existing ${controlType} control:`,
                    updateError,
                  );
                }
                return;
              } else {
                return;
              }
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
                control = new LayerControl(controlOptions || {}, map, model, el);
                break;
              case 'geoman': {
                scheduleGeomanInitialization(controlKey, {
                  position,
                  geoman_options: controlOptions?.geoman_options || {},
                  collapsed: controlOptions?.collapsed,
                });
                return;
              }
              case 'export': {
                const ExportControlClass = resolveExportControlClass();
                if (!ExportControlClass) {
                  console.warn('MapLibre export control not available');
                  return;
                }
                const { options: exportOptions, startCollapsed } = normalizeExportControlOptions(
                  controlOptions || {},
                );
                control = new ExportControlClass(exportOptions);
                control.__anymapStartCollapsed = startCollapsed;
                break;
              }
              case 'geogrid': {
                const GeoGridClass = resolveGeoGridClass();
                if (!GeoGridClass) {
                  console.warn('GeoGrid plugin not available');
                  return;
                }
                // Remove position from options as GeoGrid doesn't use it
                const { position: _, gridStyle, labelStyle, ...otherConfig } = controlOptions || {};

                // Map MapLibre paint properties to GeoGrid style properties
                const geogridOptions = {
                  map,
                  ...otherConfig,
                  ...(gridStyle && { gridStyle: mapToGeoGridStyle(gridStyle) }),
                  ...(labelStyle && { labelStyle: mapToGeoGridStyle(labelStyle) })
                };

                try {
                  const geogridInstance = new GeoGridClass(geogridOptions);

                  // Explicitly call add() to render the grid on the map
                  if (typeof geogridInstance.add === 'function') {
                    geogridInstance.add();
                  }

                  el._geogridInstance = geogridInstance;
                  el._controls.set(controlKey, { type: 'geogrid', instance: geogridInstance });
                } catch (error) {
                  console.error('Failed to create GeoGrid instance:', error);
                }
                return;
              }
              case 'widget_panel':
                control = new WidgetPanelControl(controlOptions || {}, map, model);
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

              case 'measures':
                if (window.MeasuresControl) {
                  try {
                    const measuresOptions = controlOptions.measures_options || {};
                    control = new window.MeasuresControl(measuresOptions);
                    console.log('Measures control added successfully');
                  } catch (error) {
                    console.error('Failed to create Measures control:', error);
                    return;
                  }
                } else {
                  console.warn('MeasuresControl not available');
                  return;
                }
                break;

              case 'infobox': {
                if (!window.MapboxInfoBoxControl) {
                  console.warn('MapboxInfoBoxControl not available');
                  return;
                }
                try {
                  const { position: _pos, formatter, formatter_template, ...other } = controlOptions || {};

                  let finalOptions = { showOnHover: true, showOnClick: true, ...other };
                  if (typeof formatter === 'function') {
                    finalOptions.formatter = formatter;
                  } else if (typeof formatter === 'string' && formatter.length > 0) {
                    const template = formatter;
                    finalOptions.formatter = (properties) => {
                      const safe = properties || {};
                      return template.replace(/\{\{?\s*(\w+)\s*\}?\}/g, (_, k) => (safe[k] ?? ''));
                    };
                  } else if (typeof formatter_template === 'string' && formatter_template.length > 0) {
                    const template = formatter_template;
                    finalOptions.formatter = (properties) => {
                      const safe = properties || {};
                      return template.replace(/\{\{?\s*(\w+)\s*\}?\}/g, (_, k) => (safe[k] ?? ''));
                    };
                  } else {
                    finalOptions.formatter = (properties) => {
                      const props = properties || {};
                      const rows = Object.keys(props).map(k => `<tr><th>${k}</th><td>${props[k]}</td></tr>`).join('');
                      return `<table class="anymap-infobox">${rows}</table>`;
                    };
                  }

                  const base = new window.MapboxInfoBoxControl(finalOptions);
                  control = {
                    onAdd(m) {
                      const el = base.onAdd(m);
                      try {
                        if (el && el.classList) {
                          el.classList.add('maplibregl-ctrl');
                          el.classList.add('maplibregl-ctrl-group');
                          el.style.margin = '10px';
                          el.style.padding = '0px';
                        }
                        // Provide a reliable content box in case plugin doesn't render one until events
                        let content = el.querySelector('.anymap-infobox-content');
                        if (!content) {
                          content = document.createElement('div');
                          content.className = 'anymap-infobox-content';
                          content.style.background = 'rgba(255,255,255,0.95)';
                          content.style.borderRadius = '4px';
                          content.style.padding = '8px 10px';
                          content.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';
                          content.style.fontSize = '12px';
                          content.style.maxWidth = '260px';
                          content.style.display = 'none';
                          el.appendChild(content);
                        }
                        // Attach hover/click listeners to populate content from layer features if layerId provided
                        const targetLayerId = (finalOptions.layerId || finalOptions.layer || finalOptions.layerID);
                        if (targetLayerId) {
                          const updateFromPoint = (pt) => {
                            try {
                              const feats = m.queryRenderedFeatures(pt, { layers: [targetLayerId] });
                              if (feats && feats.length > 0) {
                                const props = feats[0].properties || {};
                                const html = (typeof finalOptions.formatter === 'function')
                                  ? finalOptions.formatter(props)
                                  : Object.keys(props).map(k => `<div><b>${k}</b>: ${props[k]}</div>`).join('');
                                if (html && html.length > 0) {
                                  content.innerHTML = html;
                                  content.style.display = '';
                                } else {
                                  content.style.display = 'none';
                                }
                              } else {
                                content.style.display = 'none';
                              }
                            } catch (e) { /* ignore */ }
                          };
                          if (finalOptions.showOnHover !== false) {
                            m.on('mousemove', (ev) => updateFromPoint(ev.point));
                          }
                          if (finalOptions.showOnClick !== false) {
                            m.on('click', (ev) => updateFromPoint(ev.point));
                          }
                        }
                      } catch (_) {}
                      return el;
                    },
                    onRemove(m) { if (typeof base.onRemove === 'function') base.onRemove(m); },
                    updateOptions: base.updateOptions ? (opts) => base.updateOptions(opts) : undefined,
                  };
                  console.log('InfoBox control added successfully');
                } catch (error) {
                  console.error('Failed to create InfoBox control:', error);
                  return;
                }
                break;
              }

              case 'gradientbox': {
                if (!window.MapboxGradientBoxControl) {
                  console.warn('MapboxGradientBoxControl not available');
                  return;
                }
                try {
                  const { position: _pos, weight_property, minMaxValues, ...other } = controlOptions || {};
                  const options = normalizeGradientOptions({ ...other, minMaxValues });

                  // Handle min/max values normalization
                  if (!options.minMaxValues && (other.min_value != null || other.max_value != null)) {
                    options.minMaxValues = { minValue: other.min_value ?? 0, maxValue: other.max_value ?? 1 };
                  } else if (minMaxValues) {
                    options.minMaxValues = minMaxValues;
                  }

                  if (weight_property && typeof weight_property === 'string') {
                    options.weightGetter = (properties) => {
                      const p = properties || {};
                      const val = p[weight_property];
                      const num = Number(val);
                      return Number.isFinite(num) ? num : 0;
                    };
                  }

                  // Expand min/max to multiple common shapes so various builds pick them up
                  const minVal = (options.min_value != null) ? Number(options.min_value) : (options.minMaxValues?.minValue ?? options.min ?? options.domain?.[0]);
                  const maxVal = (options.max_value != null) ? Number(options.max_value) : (options.minMaxValues?.maxValue ?? options.max ?? options.domain?.[1]);
                  if (Number.isFinite(minVal) && Number.isFinite(maxVal)) {
                    options.minValue = minVal; // common
                    options.maxValue = maxVal;
                    options.minMaxValues = { minValue: minVal, maxValue: maxVal };
                    options.minMax = { min: minVal, max: maxVal };
                    options.domain = [minVal, maxVal];
                  }

                  const base = new window.MapboxGradientBoxControl(options);
                  control = {
                    onAdd(m) {
                      const el = base.onAdd(m);
                      try {
                        if (el && el.classList) {
                          el.classList.add('maplibregl-ctrl');
                          el.classList.add('maplibregl-ctrl-group');
                          el.style.margin = '10px';
                        }
                      } catch (_) {}
                      return el;
                    },
                    onRemove(m) { if (typeof base.onRemove === 'function') base.onRemove(m); },
                    updateOptions: (opts) => {
                      const normalized = normalizeGradientOptions(opts || {});
                      if (base.updateOptions) base.updateOptions(normalized);
                    },
                  };
                  console.log('GradientBox control added successfully');
                } catch (error) {
                  console.error('Failed to create GradientBox control:', error);
                  return;
                }
                break;
              }

              case 'legend': {
                const { position: _pos, ...other } = controlOptions || {};
                scheduleLegendInitialization(controlKey, { position, options: other }, map, el);
                return;
              }

              case 'maplibre_geocoder': {
                if (!window.MaplibreGeocoder) {
                  console.warn('MapLibre GL Geocoder library not available. Please include the library.');
                  return;
                }

                try {
                  const geocoderConfig = { ...controlOptions };
                  const position = geocoderConfig.position || 'top-left';

                  // Remove position from config as it's handled separately
                  delete geocoderConfig.position;

                  // Create geocoding API configuration
                  const apiKey = geocoderConfig.apiKey;
                  const maplibreApi = geocoderConfig.maplibreApi || 'maptiler';
                  const language = geocoderConfig.language;
                  const proximity = geocoderConfig.proximity;
                  const bbox = geocoderConfig.bbox;
                  const country = geocoderConfig.country;
                  const types = geocoderConfig.types;
                  const limit = geocoderConfig.limit || 5;

                  // Build the geocoding API configuration
                  let geocoderApi;

                  if (maplibreApi === 'maptiler') {
                    // Maptiler geocoding API
                    geocoderApi = {
                      forwardGeocode: async (config) => {
                        const features = [];
                        try {
                          let url = `https://api.maptiler.com/geocoding/${encodeURIComponent(config.query)}.json?key=${apiKey}&limit=${limit}`;

                          if (language) url += `&language=${language}`;
                          if (proximity) url += `&proximity=${proximity.join(',')}`;
                          if (bbox) url += `&bbox=${bbox.join(',')}`;
                          if (country) url += `&country=${country}`;
                          if (types) url += `&types=${types}`;

                          const response = await fetch(url);
                          const data = await response.json();

                          for (const feature of data.features || []) {
                            features.push({
                              type: 'Feature',
                              geometry: feature.geometry,
                              place_name: feature.place_name || feature.text,
                              properties: feature.properties || {},
                              text: feature.text,
                              place_type: feature.place_type,
                              center: feature.center
                            });
                          }
                        } catch (e) {
                          console.error('Maptiler geocoding error:', e);
                        }
                        return { features };
                      }
                    };
                  } else if (maplibreApi === 'mapbox') {
                    // Mapbox geocoding API
                    geocoderApi = {
                      forwardGeocode: async (config) => {
                        const features = [];
                        try {
                          let url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(config.query)}.json?access_token=${apiKey}&limit=${limit}`;

                          if (language) url += `&language=${language}`;
                          if (proximity) url += `&proximity=${proximity.join(',')}`;
                          if (bbox) url += `&bbox=${bbox.join(',')}`;
                          if (country) url += `&country=${country}`;
                          if (types) url += `&types=${types}`;

                          const response = await fetch(url);
                          const data = await response.json();

                          for (const feature of data.features || []) {
                            features.push({
                              type: 'Feature',
                              geometry: feature.geometry,
                              place_name: feature.place_name,
                              properties: feature.properties || {},
                              text: feature.text,
                              place_type: feature.place_type,
                              center: feature.center
                            });
                          }
                        } catch (e) {
                          console.error('Mapbox geocoding error:', e);
                        }
                        return { features };
                      }
                    };
                  } else {
                    console.error(`Unsupported geocoding API: ${maplibreApi}`);
                    return;
                  }

                  // Clean up config before passing to MaplibreGeocoder
                  delete geocoderConfig.apiKey;
                  delete geocoderConfig.maplibreApi;
                  delete geocoderConfig.language;
                  delete geocoderConfig.proximity;
                  delete geocoderConfig.bbox;
                  delete geocoderConfig.country;
                  delete geocoderConfig.types;
                  delete geocoderConfig.limit;

                  // Set required maplibregl reference
                  geocoderConfig.maplibregl = maplibregl;

                  // Create the geocoder control
                  control = new window.MaplibreGeocoder(geocoderApi, geocoderConfig);

                  // Set up event handlers
                  control.on('result', (e) => {
                    if (geocoderConfig.enableEventLogging) {
                      console.log('Geocoder result:', e.result);
                    }
                    sendEvent('geocoder.result', { result: e.result });
                  });

                  control.on('results', (e) => {
                    if (geocoderConfig.enableEventLogging) {
                      console.log('Geocoder results:', e.results);
                    }
                    sendEvent('geocoder.results', { results: e.results });
                  });

                  control.on('error', (e) => {
                    console.error('Geocoder error:', e.error);
                    sendEvent('geocoder.error', { error: e.error });
                  });

                  console.log('MapLibre GL Geocoder control added successfully');
                } catch (error) {
                  console.error('Failed to initialize MapLibre GL Geocoder:', error);
                  return;
                }
                break;
              }
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
              case 'temporal':
                if (window.TemporalControl) {
                  // Separate frames from options and resolve layer ids to layer objects
                  const framesInput = (controlOptions && Array.isArray(controlOptions.frames)) ? controlOptions.frames : [];
                  const { position: _ignoredPosition, frames: _ignoredFrames, ...restTemporalOpts } = controlOptions || {};

                  const temporalFrames = framesInput.map((frame, idx) => {
                    const frameLayers = (frame && Array.isArray(frame.layers)) ? frame.layers : [];
                    const resolvedLayers = frameLayers.map((layerOrId) => {
                      if (typeof layerOrId === 'string') {
                        const style = map.getStyle && map.getStyle();
                        const layerObj = (style && Array.isArray(style.layers)) ? style.layers.find((ly) => ly.id === layerOrId) : undefined;
                        if (!layerObj) {
                          console.warn(`Temporal control add: layer id not found: ${layerOrId}`);
                        }
                        return layerObj || null;
                      }
                      return layerOrId;
                    }).filter(Boolean);

                    return {
                      title: frame && frame.title !== undefined ? frame.title : `Frame ${idx + 1}`,
                      layers: resolvedLayers,
                    };
                  });

                  const temporalOptions = {
                    interval: restTemporalOpts.interval || 1000,
                    performance: restTemporalOpts.performance || false,
                    ...restTemporalOpts,
                  };

                  control = new window.TemporalControl(temporalFrames, temporalOptions);
                  console.log('Temporal control added successfully');
                } else {
                  console.warn('TemporalControl not available');
                  return;
                }
                break;

              case 'html': {
                // Create a custom HTML control
                const htmlContent = controlOptions.html || '';
                const bgColor = controlOptions.bgColor || 'white';

                control = {
                  onAdd(map) {
                    const container = document.createElement('div');
                    container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
                    container.style.background = bgColor;
                    container.style.padding = '10px';
                    container.style.borderRadius = '4px';
                    container.style.boxShadow = '0 0 0 2px rgba(0,0,0,0.1)';
                    container.innerHTML = htmlContent;
                    this._container = container;
                    return container;
                  },
                  onRemove() {
                    if (this._container && this._container.parentNode) {
                      this._container.parentNode.removeChild(this._container);
                    }
                    this._container = null;
                  },
                  updateHTML(newHTML) {
                    if (this._container) {
                      this._container.innerHTML = newHTML;
                    }
                  },
                  updateBgColor(newColor) {
                    if (this._container) {
                      this._container.style.background = newColor;
                    }
                  }
                };
                console.log('HTML control added successfully');
                break;
              }

              default:
                console.warn(`Unknown control type: ${controlType}`);
                return;
            }

            map.addControl(control, position);
            if (controlType === 'export') {
              applyExportControlCollapsedState(
                control,
                control.__anymapStartCollapsed !== false,
              );
            }
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
            } else if (removeControlType === 'geoman') {
              if (el._geomanInstance && typeof el._geomanInstance.destroy === 'function') {
                try {
                  el._geomanInstance.destroy({ removeSources: true });
                } catch (error) {
                  console.warn('Failed to destroy Geoman instance:', error);
                }
              }
              el._geomanInstance = null;
              el._geomanPromise = null;
              el._geomanEventListener = null;
              el._controls.delete(removeControlKey);
              el._geomanSyncFromJs = true;
              model.set('geoman_data', { type: 'FeatureCollection', features: [] });
              model.save_changes();
              el._pendingGeomanData = normalizeGeomanGeoJson(model.get('geoman_data'));
            } else if (removeControlType === 'geogrid') {
              if (el._geogridInstance && typeof el._geogridInstance.remove === 'function') {
                try {
                  el._geogridInstance.remove();
                } catch (error) {
                  console.warn('Failed to remove GeoGrid instance:', error);
                }
              }
              el._geogridInstance = null;
              el._controls.delete(removeControlKey);
              console.log(`GeoGrid control ${removeControlKey} removed`);
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

          case 'removeWidgetControl':
            const [widgetControlId] = args;
            if (widgetControlId) {
              const widgetControlKey = `widget_panel_${widgetControlId}`;
              if (el._controls.has(widgetControlKey)) {
                const widgetControl = el._controls.get(widgetControlKey);
                map.removeControl(widgetControl);
                el._controls.delete(widgetControlKey);
              } else {
                console.warn(`Widget control ${widgetControlId} not found`);
              }
            }
            break;

          case 'updateHTML':
            const [updateControlKey, newHTML, newBgColor] = args;
            if (el._controls.has(updateControlKey)) {
              const htmlControl = el._controls.get(updateControlKey);
              if (htmlControl && typeof htmlControl.updateHTML === 'function') {
                htmlControl.updateHTML(newHTML);
                if (newBgColor && typeof htmlControl.updateBgColor === 'function') {
                  htmlControl.updateBgColor(newBgColor);
                }
                console.log(`HTML control ${updateControlKey} updated successfully`);
              } else {
                console.warn(`HTML control ${updateControlKey} does not support updates`);
              }
            } else {
              console.warn(`HTML control ${updateControlKey} not found`);
            }
            break;

          case 'removeHTML':
            const [removeHtmlControlKey] = args;
            if (el._controls.has(removeHtmlControlKey)) {
              const htmlControl = el._controls.get(removeHtmlControlKey);
              map.removeControl(htmlControl);
              el._controls.delete(removeHtmlControlKey);
              console.log(`HTML control ${removeHtmlControlKey} removed successfully`);
            } else {
              console.warn(`HTML control ${removeHtmlControlKey} not found`);
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

                debugLog('Draw control added successfully with custom styles');
              } else {
                debugLog('MapboxDraw not available or already added');
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

          case 'exportGeomanData':
            // Export current Geoman features and sync to Python
            exportGeomanData();
            break;

          case 'collapseGeomanControl':
            // Collapse the Geoman control toolbar
            {
              const geomanInstance = map.gm || el._geomanInstance;
              if (geomanInstance) {
                requestAnimationFrame(() => {
                  applyGeomanCollapsedState(geomanInstance, true);
                });
              }
            }
            break;

          case 'expandGeomanControl':
            // Expand the Geoman control toolbar
            {
              const geomanInstance = map.gm || el._geomanInstance;
              if (geomanInstance) {
                requestAnimationFrame(() => {
                  applyGeomanCollapsedState(geomanInstance, false);
                  updateAndSyncGeomanStatus();
                });
              }
            }
            break;

          case 'toggleGeomanControl':
            // Toggle the Geoman control toolbar collapse state
            {
              const geomanInstance = map.gm || el._geomanInstance;
              if (geomanInstance && geomanInstance.control && geomanInstance.control.container) {
                requestAnimationFrame(() => {
                  const container = geomanInstance.control.container;
                  const isCollapsed = !container.querySelector('.gm-reactive-controls');
                  applyGeomanCollapsedState(geomanInstance, !isCollapsed);
                  updateAndSyncGeomanStatus();
                });
              }
            }
            break;

          case 'setUnionSelection':
            // Highlight selected Geoman features by IDs using a temporary GeoJSON source/layers
            {
              const selectedIds = Array.isArray(args[0]) ? args[0] : [];
              const data = model.get('geoman_data') || { type: 'FeatureCollection', features: [] };
              const selectedFeatures = (data.features || []).filter(f => selectedIds.includes(f.id));
              const fc = { type: 'FeatureCollection', features: selectedFeatures };

              const srcId = 'union-selection';
              const fillId = 'union-selection-fill';
              const lineId = 'union-selection-line';
              const pointId = 'union-selection-point';

              // Add or update source
              if (map.getSource(srcId)) {
                try {
                  map.getSource(srcId).setData(fc);
                } catch (e) {
                  console.warn('Failed to update union selection source, recreating:', e);
                  try {
                    map.removeLayer(fillId);
                    map.removeLayer(lineId);
                    map.removeLayer(pointId);
                  } catch (_err) {}
                  try {
                    map.removeSource(srcId);
                  } catch (_err2) {}
                  map.addSource(srcId, { type: 'geojson', data: fc });
                }
              } else {
                map.addSource(srcId, { type: 'geojson', data: fc });
              }

              // Ensure highlight layers exist
              if (!map.getLayer(fillId)) {
                try {
                  map.addLayer({
                    id: fillId,
                    type: 'fill',
                    source: srcId,
                    filter: ['==', ['geometry-type'], 'Polygon'],
                    paint: {
                      'fill-color': '#ffd54f',
                      'fill-opacity': 0.35
                    }
                  });
                } catch (e) {
                  console.warn('Failed to add union selection fill layer:', e);
                }
              }
              if (!map.getLayer(lineId)) {
                try {
                  map.addLayer({
                    id: lineId,
                    type: 'line',
                    source: srcId,
                    filter: ['==', ['geometry-type'], 'LineString'],
                    paint: {
                      'line-color': '#ffca28',
                      'line-width': 4
                    }
                  });
                } catch (e) {
                  console.warn('Failed to add union selection line layer:', e);
                }
              }
              if (!map.getLayer(pointId)) {
                try {
                  map.addLayer({
                    id: pointId,
                    type: 'circle',
                    source: srcId,
                    filter: ['==', ['geometry-type'], 'Point'],
                    paint: {
                      'circle-radius': 6,
                      'circle-color': '#ffb300',
                      'circle-stroke-color': '#ff6f00',
                      'circle-stroke-width': 2
                    }
                  });
                } catch (e) {
                  console.warn('Failed to add union selection point layer:', e);
                }
              }
            }
            break;

          case 'clearUnionSelection':
            // Clear highlight by setting empty FeatureCollection; keep layers for reuse
            {
              const srcId = 'union-selection';
              if (map.getSource(srcId)) {
                try {
                  map.getSource(srcId).setData({ type: 'FeatureCollection', features: [] });
                } catch (e) {
                  console.warn('Failed to clear union selection source:', e);
                }
              }
            }
            break;

          case 'getGeomanStatus':
            // Query and sync current Geoman toolbar status
            updateAndSyncGeomanStatus();
            break;

          case 'setGeomanInfoBoxEnabled':
            {
              const enabled = Boolean(args[0]);
              el._gmShowInfoBox = enabled;
              try {
                if (enabled) {
                  if (typeof el._gmEnsureInfoBox === 'function') el._gmEnsureInfoBox();
                } else {
                  if (typeof el._gmHideInfoBox === 'function') el._gmHideInfoBox();
                }
              } catch (_e) {}
            }
            break;

          case 'activateGeomanButton':
            // Programmatically click a Geoman toolbar button by (partial) name
            {
              const targetName = (args[0] || '').toString().toLowerCase();
              const geomanInstance = map.gm || el._geomanInstance;
              if (geomanInstance && geomanInstance.control && geomanInstance.control.container) {
                const container = geomanInstance.control.container;
                const buttons = Array.from(container.querySelectorAll('.gm-control-button'));
                let matched = false;
                for (const btn of buttons) {
                  const label = (btn.getAttribute('title')
                    || btn.getAttribute('aria-label')
                    || (btn.textContent ? btn.textContent.trim() : '')).toLowerCase();
                  if (label && (label === targetName || label.includes(targetName))) {
                    btn.click();
                    matched = true;
                    break;
                  }
                }
                if (!matched) {
                  console.warn('Geoman button not found for name:', targetName);
                }
                // Sync status after attempted activation
                requestAnimationFrame(() => updateAndSyncGeomanStatus());
              }
            }
            break;

          case 'deactivateGeomanButton':
            // Programmatically deactivate (toggle off) a Geoman toolbar button by (partial) name
            {
              const targetName = (args[0] || '').toString().toLowerCase();
              const geomanInstance = map.gm || el._geomanInstance;
              if (geomanInstance && geomanInstance.control && geomanInstance.control.container) {
                const container = geomanInstance.control.container;
                const buttons = Array.from(container.querySelectorAll('.gm-control-button'));
                let matched = false;
                for (const btn of buttons) {
                  const label = (btn.getAttribute('title')
                    || btn.getAttribute('aria-label')
                    || (btn.textContent ? btn.textContent.trim() : '')).toLowerCase();
                  const isActive = btn.getAttribute('aria-pressed') === 'true'
                    || btn.classList.contains('active')
                    || btn.classList.contains('gm-active');
                  if (label && (label === targetName || label.includes(targetName))) {
                    matched = true;
                    if (isActive) {
                      btn.click(); // toggle off
                    }
                    break;
                  }
                }
                if (!matched) {
                  console.warn('Geoman button not found for name:', targetName);
                }
                // Sync status after attempted deactivation
                requestAnimationFrame(() => updateAndSyncGeomanStatus());
              }
            }
            break;

          case 'loadOsmTransportToGeoman':
            // Fetch OSM transport features in bbox and import into Geoman
            {
              const opts = args[0] || {};
              // Reuse helper defined during Geoman initialization
              if (typeof loadOsmTransportToGeoman === 'function') {
                loadOsmTransportToGeoman(opts).catch((e) => {
                  console.warn('loadOsmTransportToGeoman failed:', e);
                });
              } else {
                // Fallback: compute bbox and try minimal inline fetch/import
                (async () => {
                  try {
                    const b = map.getBounds();
                    const bbox = Array.isArray(opts?.bbox) && opts.bbox.length === 4
                      ? opts.bbox
                      : [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
                    const keys = Array.isArray(opts?.keys) && opts.keys.length ? opts.keys : ['highway', 'railway'];
                    const [w, s, e, n] = bbox;
                    const bboxStr = `${s},${w},${n},${e}`;
                    const body = [
                      `[out:json][timeout:${opts?.timeout || 25}];`,
                      '(',
                      ...keys.flatMap((k) => [
                        `node["${k}"](${bboxStr});`,
                        `way["${k}"](${bboxStr});`,
                        `relation["${k}"](${bboxStr});`,
                      ]),
                      ');',
                      'out body geom;'
                    ].join('');
                    const url = 'https://overpass-api.de/api/interpreter';
                    const resp = await fetch(url, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
                      body: new URLSearchParams({ data: body }).toString(),
                    });
                    if (!resp.ok) throw new Error(`Overpass error ${resp.status}`);
                    const osmJson = await resp.json();
                    // Try to load converter
                    if (typeof window.osmtogeojson !== 'function') {
                      const s = document.createElement('script');
                      s.src = 'https://cdn.jsdelivr.net/npm/osmtogeojson@3.0.0/osmtogeojson.min.js';
                      await new Promise((resolve, reject) => {
                        s.onload = resolve;
                        s.onerror = reject;
                        document.head.appendChild(s);
                      });
                    }
                    let geojson = null;
                    if (typeof window.osmtogeojson === 'function') {
                      geojson = window.osmtogeojson(osmJson, { flatProperties: true });
                    } else if (typeof convertOsmTransportToGeoJsonLite === 'function') {
                      console.warn('osmtogeojson unavailable, using convertOsmTransportToGeoJsonLite fallback');
                      geojson = convertOsmTransportToGeoJsonLite(osmJson);
                    } else {
                      console.warn('Neither osmtogeojson nor convertOsmTransportToGeoJsonLite are available; cannot convert OSM data.');
                      return;
                    }
                    if (geojson && geojson.type === 'FeatureCollection') {
                      importGeomanData(geojson);
                    }
                  } catch (e) {
                    console.warn('Inline OSM transport import failed:', e);
                  }
                })();
              }
            }
            break;

          case 'initMapScene':
            // Initialize MapLibre Three Plugin scene
            if (window.MaplibreThreePlugin && window.THREE) {
              try {
                if (!el._mapScene) {
                  el._mapScene = new window.MaplibreThreePlugin.MapScene(map);
                  el._threeObjects = new Map(); // Store references to 3D objects
                  el._threeLights = new Map(); // Store references to lights
                  el._threeTilesets = new Map(); // Store references to 3D tilesets
                  console.log('MapScene initialized');
                }
              } catch (error) {
                console.error('Failed to initialize MapScene:', error);
              }
            } else {
              console.warn('MapLibre Three Plugin or Three.js not loaded');
            }
            break;

          case 'addThreeModel':
            // Add a 3D GLTF model to the scene
            if (el._mapScene && window.GLTFLoader) {
              try {
                const modelConfig = args[0] || {};
                const { id, url, coordinates, scale, rotation, options } = modelConfig;

                const loader = new window.GLTFLoader();
                loader.load(
                  url,
                  (gltf) => {
                    // Create RTC group for georeferencing
                    const rtcGroup = window.MaplibreThreePlugin.Creator.createRTCGroup(coordinates);

                    // Apply scale if provided
                    if (scale) {
                      if (Array.isArray(scale)) {
                        gltf.scene.scale.set(scale[0], scale[1], scale[2]);
                      } else {
                        gltf.scene.scale.set(scale, scale, scale);
                      }
                    }

                    // Apply rotation if provided
                    if (rotation) {
                      if (Array.isArray(rotation)) {
                        gltf.scene.rotation.set(rotation[0], rotation[1], rotation[2]);
                      }
                    }

                    rtcGroup.add(gltf.scene);
                    el._mapScene.addObject(rtcGroup);

                    // Store reference
                    el._threeObjects.set(id, { group: rtcGroup, model: gltf.scene });

                    console.log(`3D model "${id}" loaded successfully`);
                  },
                  (progress) => {
                    console.log(`Loading model "${id}": ${(progress.loaded / progress.total * 100).toFixed(2)}%`);
                  },
                  (error) => {
                    console.error(`Failed to load model "${id}":`, error);
                  }
                );
              } catch (error) {
                console.error('Failed to add 3D model:', error);
              }
            } else {
              console.warn('MapScene not initialized or GLTFLoader not available');
            }
            break;

          case 'addThreeLight': {
            // Add light to the Three.js scene
            if (el._mapScene && window.THREE) {
              try {
                const lightConfig = args[0] || {};
                const {
                  id,
                  type = 'ambient',
                  color = 0xffffff,
                  intensity = 1,
                  position,
                  target,
                  castShadow,
                  shadowOptions,
                  sunOptions,
                } = lightConfig;

                if (!el._threeLights) {
                  el._threeLights = new Map();
                }

                const lightId =
                  id ||
                  (window.crypto && window.crypto.randomUUID
                    ? `light-${window.crypto.randomUUID()}`
                    : `light-${Date.now()}-${Math.floor(Math.random() * 1e6)}`);

                let light;
                const colorInstance = new window.THREE.Color(color);

                switch (type) {
                  case 'ambient':
                    light = new window.THREE.AmbientLight(colorInstance, intensity);
                    break;
                  case 'directional': {
                    light = new window.THREE.DirectionalLight(colorInstance, intensity);
                    if (position && Array.isArray(position)) {
                      light.position.set(position[0], position[1], position[2]);
                    }
                    if (target && Array.isArray(target)) {
                      const targetObject = new window.THREE.Object3D();
                      targetObject.position.set(target[0], target[1], target[2]);
                      light.target = targetObject;
                      el._mapScene.scene.add(targetObject);
                    }
                    break;
                  }
                  case 'sun':
                    light = new window.MaplibreThreePlugin.Sun();
                    break;
                  default:
                    console.warn(`Unknown light type: ${type}`);
                    return;
                }

                if (!light) {
                  console.warn('Failed to instantiate light');
                  return;
                }

                light.userData = light.userData || {};
                light.userData.anymapLightId = lightId;
                light.userData.type = type;

                if (castShadow !== undefined) {
                  if (type === 'sun') {
                    light.castShadow = Boolean(castShadow);
                    if (light.sunLight) {
                      light.sunLight.castShadow = Boolean(castShadow);
                    }
                  } else if ('castShadow' in light) {
                    light.castShadow = Boolean(castShadow);
                  }
                }

                if (shadowOptions && light.shadow) {
                  const { radius, mapSize, topRight, bottomLeft, near, far } = shadowOptions;
                  if (radius !== undefined) {
                    light.shadow.radius = radius;
                  }
                  if (Array.isArray(mapSize) && mapSize.length === 2) {
                    light.shadow.mapSize.set(mapSize[0], mapSize[1]);
                  }
                  if (light.shadow.camera) {
                    if (topRight !== undefined) {
                      light.shadow.camera.top = topRight;
                      light.shadow.camera.right = topRight;
                    }
                    if (bottomLeft !== undefined) {
                      light.shadow.camera.bottom = bottomLeft;
                      light.shadow.camera.left = bottomLeft;
                    }
                    if (near !== undefined) {
                      light.shadow.camera.near = near;
                    }
                    if (far !== undefined) {
                      light.shadow.camera.far = far;
                    }
                    if (light.shadow.camera.updateProjectionMatrix) {
                      light.shadow.camera.updateProjectionMatrix();
                    }
                  }
                }

                if (type === 'sun' && sunOptions && typeof light.setShadow === 'function') {
                  if (sunOptions.shadow) {
                    light.setShadow(sunOptions.shadow);
                  }
                  if (sunOptions.castShadow !== undefined) {
                    light.castShadow = Boolean(sunOptions.castShadow);
                  }
                  if (sunOptions.currentTime !== undefined) {
                    light.currentTime = sunOptions.currentTime;
                  }
                }

                el._mapScene.addLight(light);
                el._threeLights.set(lightId, { id: lightId, type, light });
                el._mapScene.map.triggerRepaint();
                console.log(`Added ${type} light "${lightId}" to scene`);
              } catch (error) {
                console.error('Failed to add light:', error);
              }
            } else {
              console.warn('MapScene not initialized or Three.js not loaded');
            }
            break;
          }

          case 'updateThreeLight': {
            if (el._mapScene && el._threeLights && window.THREE) {
              try {
                const updateConfig = args[0] || {};
                const {
                  id,
                  color,
                  intensity,
                  position,
                  target,
                  castShadow,
                  shadowOptions,
                  sunOptions,
                } = updateConfig;

                if (!id || !el._threeLights.has(id)) {
                  console.warn(`Three.js light "${id}" not found for update`);
                  break;
                }

                const entry = el._threeLights.get(id);
                const storedLight = entry.light;
                const actualLight = storedLight.delegate || storedLight;

                if (color !== undefined && actualLight.color) {
                  actualLight.color = new window.THREE.Color(color);
                }
                if (intensity !== undefined && actualLight.intensity !== undefined) {
                  actualLight.intensity = intensity;
                }
                if (position && Array.isArray(position) && actualLight.position) {
                  actualLight.position.set(position[0], position[1], position[2]);
                }
                if (target && Array.isArray(target) && actualLight.target) {
                  actualLight.target.position.set(target[0], target[1], target[2]);
                  el._mapScene.scene.add(actualLight.target);
                }
                if (castShadow !== undefined && 'castShadow' in actualLight) {
                  actualLight.castShadow = Boolean(castShadow);
                }
                if (shadowOptions && actualLight.shadow) {
                  const { radius, mapSize, topRight, bottomLeft, near, far } = shadowOptions;
                  if (radius !== undefined) {
                    actualLight.shadow.radius = radius;
                  }
                  if (Array.isArray(mapSize) && mapSize.length === 2) {
                    actualLight.shadow.mapSize.set(mapSize[0], mapSize[1]);
                  }
                  if (actualLight.shadow.camera) {
                    if (topRight !== undefined) {
                      actualLight.shadow.camera.top = topRight;
                      actualLight.shadow.camera.right = topRight;
                    }
                    if (bottomLeft !== undefined) {
                      actualLight.shadow.camera.bottom = bottomLeft;
                      actualLight.shadow.camera.left = bottomLeft;
                    }
                    if (near !== undefined) {
                      actualLight.shadow.camera.near = near;
                    }
                    if (far !== undefined) {
                      actualLight.shadow.camera.far = far;
                    }
                    if (actualLight.shadow.camera.updateProjectionMatrix) {
                      actualLight.shadow.camera.updateProjectionMatrix();
                    }
                  }
                }

                if (entry.type === 'sun' && storedLight) {
                  if (sunOptions && typeof storedLight.setShadow === 'function') {
                    if (sunOptions.shadow) {
                      storedLight.setShadow(sunOptions.shadow);
                    }
                    if (sunOptions.castShadow !== undefined) {
                      storedLight.castShadow = Boolean(sunOptions.castShadow);
                    }
                    if (sunOptions.currentTime !== undefined) {
                      storedLight.currentTime = sunOptions.currentTime;
                    }
                  }
                }

                el._mapScene.map.triggerRepaint();
                console.log(`Updated light "${id}"`);
              } catch (error) {
                console.error('Failed to update light:', error);
              }
            }
            break;
          }

          case 'removeThreeLight': {
            if (el._mapScene && el._threeLights) {
              try {
                const lightId = args[0];
                if (!lightId || !el._threeLights.has(lightId)) {
                  console.warn(`Three.js light "${lightId}" not found for removal`);
                  break;
                }
                const entry = el._threeLights.get(lightId);
                const storedLight = entry.light;
                const actualLight = storedLight.delegate || storedLight;
                el._mapScene.removeLight(storedLight);
                if (actualLight && actualLight.target && actualLight.target.parent) {
                  actualLight.target.parent.remove(actualLight.target);
                }
                el._threeLights.delete(lightId);
                el._mapScene.map.triggerRepaint();
                console.log(`Removed light "${lightId}"`);
              } catch (error) {
                console.error('Failed to remove light:', error);
              }
            }
            break;
          }

          case 'addThreeTileset': {
            if (!el._mapScene) {
              console.warn('MapScene not initialized - call init_three_scene() before adding tilesets');
              break;
            }

            const config = args[0] || {};
            const {
              id,
              assetId = null,
              url = null,
              ionToken = null,
              autoRefreshToken = true,
              autoDisableRendererCulling = true,
              fetchOptions = null,
              lruCache = null,
              dracoDecoderPath = `https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/examples/jsm/libs/draco/`,
              ktx2TranscoderPath = `https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/examples/jsm/libs/basis/`,
              useDebug = false,
              useFade = false,
              useUnload = false,
              useUpdate = false,
              heightOffset = 0,
              flyTo = true,
            } = config;

            const source = assetId ?? url;
            if (!source) {
              console.warn('addThreeTileset requires either assetId or url');
              break;
            }

            if (!el._threeTilesets) {
              el._threeTilesets = new Map();
            }

            const tilesetId = id || createUniqueId('tileset');
            if (el._threeTilesets.has(tilesetId)) {
              console.warn(`Tileset "${tilesetId}" already exists`);
              break;
            }

            (async () => {
              try {
                const support = await ensureThreeTilesSupport(el._mapScene);
                const renderer = new support.TilesRenderer(source);
                renderer.autoDisableRendererCulling = autoDisableRendererCulling;

                if (fetchOptions && typeof fetchOptions === 'object') {
                  Object.assign(renderer.fetchOptions, fetchOptions);
                }

                if (lruCache && typeof lruCache === 'object') {
                  Object.assign(renderer.lruCache, lruCache);
                }

                const dracoLoader = new support.DRACOLoader();
                dracoLoader.setDecoderPath(dracoDecoderPath);

                const ktxLoader = new support.KTX2Loader();
                ktxLoader.setTranscoderPath(ktx2TranscoderPath);
                ktxLoader.detectSupport(el._mapScene.renderer);

                renderer.manager.addHandler(/\.ktx2$/i, ktxLoader);

                renderer.registerPlugin(
                  new support.GLTFExtensionsPlugin({
                    dracoLoader,
                    ktxLoader,
                  }),
                );

                if (ionToken) {
                  renderer.registerPlugin(
                    new support.CesiumIonAuthPlugin({
                      apiToken: ionToken,
                      assetId: typeof assetId === 'number' || typeof assetId === 'string' ? assetId : null,
                      autoRefreshToken,
                    }),
                  );
                }

                if (useDebug) {
                  renderer.registerPlugin(new support.DebugTilesPlugin());
                }
                if (useFade) {
                  renderer.registerPlugin(new support.TilesFadePlugin());
                }
                if (useUnload) {
                  renderer.registerPlugin(new support.UnloadTilesPlugin());
                }
                if (useUpdate) {
                  renderer.registerPlugin(new support.UpdateOnChangePlugin());
                }

                const group = new window.THREE.Group();
                group.name = `tileset-${tilesetId}`;

                const entry = {
                  id: tilesetId,
                  renderer,
                  group,
                  positionDegrees: null,
                  heightOffset,
                  isLoaded: false,
                  onPreRender: null,
                  onPostRender: null,
                  onInitialLoad: null,
                };

                entry.onInitialLoad = () => {
                  if (entry.isLoaded) {
                    return;
                  }

                  const geoResult = georeferenceTileset(renderer, group);
                  if (!geoResult) {
                    console.warn('Unable to georeference tileset');
                    return;
                  }

                  entry.isLoaded = true;
                  entry.positionDegrees = [geoResult.lng, geoResult.lat, geoResult.height];
                  entry.size = geoResult.size;

                  el._mapScene.addObject(group);

                  if (heightOffset) {
                    applyTilesetHeight(entry, heightOffset);
                  }

                  if (flyTo) {
                    try {
                      el._mapScene.flyTo(group);
                    } catch (flyError) {
                      console.warn('Failed to fly to tileset:', flyError);
                    }
                  }

                  el._mapScene.map.triggerRepaint();
                  console.log(`3D tileset "${tilesetId}" loaded`);

                  renderer.removeEventListener('load-tile-set', entry.onInitialLoad);
                };

                renderer.addEventListener('load-tile-set', entry.onInitialLoad);

                entry.onPreRender = (event) => {
                  try {
                    renderer.setCamera(event.frameState.camera);
                    renderer.setResolutionFromRenderer(
                      event.frameState.camera,
                      event.frameState.renderer,
                    );
                    renderer.update();
                  } catch (updateError) {
                    console.error('Failed to update tileset during preRender:', updateError);
                  }
                };

                entry.onPostRender = () => {
                  map.triggerRepaint();
                };

                el._mapScene.on('preRender', entry.onPreRender);
                el._mapScene.on('postRender', entry.onPostRender);

                el._threeTilesets.set(tilesetId, entry);
                console.log(`Started loading 3D tileset "${tilesetId}"`);
              } catch (error) {
                console.error('Failed to add 3D tileset:', error);
              }
            })();

            break;
          }

          case 'removeThreeTileset': {
            if (el._threeTilesets && el._mapScene) {
              try {
                const tilesetId = args[0];
                if (!tilesetId || !el._threeTilesets.has(tilesetId)) {
                  console.warn(`Tileset "${tilesetId}" not found`);
                  break;
                }

                const entry = el._threeTilesets.get(tilesetId);
                if (entry.onInitialLoad) {
                  entry.renderer.removeEventListener('load-tile-set', entry.onInitialLoad);
                }
                if (entry.onPreRender) {
                  el._mapScene.off('preRender', entry.onPreRender);
                }
                if (entry.onPostRender) {
                  el._mapScene.off('postRender', entry.onPostRender);
                }
                if (entry.group && entry.group.parent) {
                  entry.group.parent.remove(entry.group);
                }
                if (entry.renderer && typeof entry.renderer.dispose === 'function') {
                  entry.renderer.dispose();
                }

                el._threeTilesets.delete(tilesetId);
                el._mapScene.map.triggerRepaint();
                console.log(`Removed 3D tileset "${tilesetId}"`);
              } catch (error) {
                console.error('Failed to remove 3D tileset:', error);
              }
            }
            break;
          }

          case 'setThreeTilesetHeight': {
            if (el._threeTilesets) {
              try {
                const { id: tilesetId, height = 0 } = args[0] || {};
                if (!tilesetId || !el._threeTilesets.has(tilesetId)) {
                  console.warn(`Tileset "${tilesetId}" not found for height update`);
                  break;
                }
                const entry = el._threeTilesets.get(tilesetId);
                applyTilesetHeight(entry, height);
                el._mapScene.map.triggerRepaint();
              } catch (error) {
                console.error('Failed to update tileset height:', error);
              }
            }
            break;
          }

          case 'flyToThreeTileset': {
            if (el._mapScene && el._threeTilesets) {
              try {
                const tilesetId = args[0];
                if (!tilesetId || !el._threeTilesets.has(tilesetId)) {
                  console.warn(`Tileset "${tilesetId}" not found for flyTo`);
                  break;
                }
                const entry = el._threeTilesets.get(tilesetId);
                el._mapScene.flyTo(entry.group);
              } catch (error) {
                console.error('Failed to fly to tileset:', error);
              }
            }
            break;
          }

          case 'removeThreeModel':
            // Remove a 3D model from the scene
            if (el._mapScene && el._threeObjects) {
              try {
                const modelId = args[0];
                const obj = el._threeObjects.get(modelId);
                if (obj) {
                  el._mapScene.removeObject(obj.group);
                  el._threeObjects.delete(modelId);
                  console.log(`Removed 3D model "${modelId}"`);
                } else {
                  console.warn(`3D model "${modelId}" not found`);
                }
              } catch (error) {
                console.error('Failed to remove 3D model:', error);
              }
            }
            break;

          case 'updateThreeModel':
            // Update properties of a 3D model
            if (el._threeObjects) {
              try {
                const updateConfig = args[0] || {};
                const { id, position, scale, rotation } = updateConfig;

                const obj = el._threeObjects.get(id);
                if (obj) {
                  if (position && Array.isArray(position)) {
                    obj.group.position.set(position[0], position[1], position[2]);
                  }
                  if (scale) {
                    if (Array.isArray(scale)) {
                      obj.model.scale.set(scale[0], scale[1], scale[2]);
                    } else {
                      obj.model.scale.set(scale, scale, scale);
                    }
                  }
                  if (rotation && Array.isArray(rotation)) {
                    obj.model.rotation.set(rotation[0], rotation[1], rotation[2]);
                  }
                  console.log(`Updated 3D model "${id}"`);
                } else {
                  console.warn(`3D model "${id}" not found`);
                }
              } catch (error) {
                console.error('Failed to update 3D model:', error);
              }
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
      if (el._markerGroups) {
        el._markerGroups.forEach(markerGroup => {
          markerGroup.forEach(marker => marker.remove());
        });
        el._markerGroups.clear();
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

    })
    .catch((error) => {
      console.error('Failed to initialize MapLibre widget:', error);
    });
}

export default { render };
