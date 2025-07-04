// Load Mapbox GL JS and Compare library
let mapboxLoaded = false;
let compareLoaded = false;

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

function loadCSS(href) {
    return new Promise((resolve, reject) => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.onload = resolve;
        link.onerror = reject;
        document.head.appendChild(link);
    });
}

// Load dependencies if not already loaded
async function loadDependencies() {
    if (!window.mapboxgl && !mapboxLoaded) {
        await Promise.all([
            loadScript('https://api.mapbox.com/mapbox-gl-js/v3.13.0/mapbox-gl.js'),
            loadCSS('https://api.mapbox.com/mapbox-gl-js/v3.13.0/mapbox-gl.css')
        ]);
        mapboxLoaded = true;
    }

    if (!window.maplibregl?.Compare && !compareLoaded) {
        await Promise.all([
            loadScript('https://unpkg.com/@maplibre/maplibre-gl-compare@0.5.0/dist/maplibre-gl-compare.js'),
            loadCSS('https://unpkg.com/@maplibre/maplibre-gl-compare@0.5.0/dist/maplibre-gl-compare.css')
        ]);
        compareLoaded = true;
    }
}

async function render({ model, el }) {
    // Load dependencies first
    await loadDependencies();
    // Clear any existing content
    el.innerHTML = '';

    // Create container structure
    const container = document.createElement('div');
    container.style.width = model.get('width');
    container.style.height = model.get('height');
    container.style.position = 'relative';
    container.id = 'comparison-container-' + Math.random().toString(36).substr(2, 9);

    const beforeContainer = document.createElement('div');
    beforeContainer.id = 'before-' + Math.random().toString(36).substr(2, 9);
    beforeContainer.style.position = 'absolute';
    beforeContainer.style.top = '0';
    beforeContainer.style.bottom = '0';
    beforeContainer.style.width = '100%';
    beforeContainer.style.height = '100%';

    const afterContainer = document.createElement('div');
    afterContainer.id = 'after-' + Math.random().toString(36).substr(2, 9);
    afterContainer.style.position = 'absolute';
    afterContainer.style.top = '0';
    afterContainer.style.bottom = '0';
    afterContainer.style.width = '100%';
    afterContainer.style.height = '100%';

    container.appendChild(beforeContainer);
    container.appendChild(afterContainer);
    el.appendChild(container);

    // Initialize maps
    let beforeMap, afterMap, compare;
    let isSettingSliderProgrammatically = false;

    function initializeMaps() {
        const leftMapConfig = model.get('left_map_config');
        const rightMapConfig = model.get('right_map_config');

        // Set Mapbox access token if available
        const accessToken = leftMapConfig.access_token || rightMapConfig.access_token || '';
        if (accessToken) {
            mapboxgl.accessToken = accessToken;
        }

        // Create before map
        beforeMap = new mapboxgl.Map({
            container: beforeContainer.id,
            style: leftMapConfig.style || 'mapbox://styles/mapbox/streets-v12',
            center: leftMapConfig.center ? [leftMapConfig.center[1], leftMapConfig.center[0]] : [0, 0],
            zoom: leftMapConfig.zoom || 2,
            bearing: leftMapConfig.bearing || 0,
            pitch: leftMapConfig.pitch || 0,
            antialias: leftMapConfig.antialias !== undefined ? leftMapConfig.antialias : true
        });

        // Create after map
        afterMap = new mapboxgl.Map({
            container: afterContainer.id,
            style: rightMapConfig.style || 'mapbox://styles/mapbox/satellite-v9',
            center: rightMapConfig.center ? [rightMapConfig.center[1], rightMapConfig.center[0]] : [0, 0],
            zoom: rightMapConfig.zoom || 2,
            bearing: rightMapConfig.bearing || 0,
            pitch: rightMapConfig.pitch || 0,
            antialias: rightMapConfig.antialias !== undefined ? rightMapConfig.antialias : true
        });

        // Wait for both maps to load
        Promise.all([
            new Promise(resolve => beforeMap.on('load', resolve)),
            new Promise(resolve => afterMap.on('load', resolve))
        ]).then(() => {
            // Initialize comparison using the maplibre-gl-compare plugin (works with Mapbox too)
            compare = new maplibregl.Compare(beforeMap, afterMap, '#' + container.id, {
                orientation: model.get('orientation') || 'vertical',
                mousemove: model.get('mousemove') || false
            });

            // Wait for the compare widget to be fully rendered before setting slider position
            const sliderPosition = model.get('slider_position');
            if (sliderPosition !== undefined && sliderPosition !== 0.5) {
                isSettingSliderProgrammatically = true;

                // Convert percentage to pixels
                const containerRect = container.getBoundingClientRect();
                const isVertical = (model.get('orientation') || 'vertical') === 'vertical';
                const containerSize = isVertical ? containerRect.width : containerRect.height;
                const pixelPosition = sliderPosition * containerSize;

                // Set slider position with retry logic
                setTimeout(() => {
                    compare.setSlider(pixelPosition);
                    setTimeout(() => {
                        isSettingSliderProgrammatically = false;
                    }, 100);
                }, 100);
            } else {
                setTimeout(() => {
                    isSettingSliderProgrammatically = false;
                }, 100);
            }

            // Set up event listeners
            compare.on('slideend', function(event) {
                if (!isSettingSliderProgrammatically) {
                    // Convert pixels to percentage
                    const containerRect = container.getBoundingClientRect();
                    const isVertical = (model.get('orientation') || 'vertical') === 'vertical';
                    const containerSize = isVertical ? containerRect.width : containerRect.height;
                    const percentagePosition = containerSize > 0 ? event.currentPosition / containerSize : 0.5;

                    model.set('slider_position', percentagePosition);
                    const events = model.get('_js_events') || [];
                    events.push({
                        type: 'slideend',
                        position: percentagePosition
                    });
                    model.set('_js_events', events);
                    model.save_changes();
                }
            });

            // Set up JavaScript method handlers
            setupMethodHandlers();

            // Note: MapLibre Compare plugin handles synchronization internally
            // Custom synchronization disabled to prevent conflicts and improve performance
        });
    }

    function setupSynchronization() {
        const syncCenter = model.get('sync_center');
        const syncZoom = model.get('sync_zoom');
        const syncBearing = model.get('sync_bearing');
        const syncPitch = model.get('sync_pitch');

        if (syncCenter || syncZoom || syncBearing || syncPitch) {
            let isSync = false;

            function syncMaps(sourceMap, targetMap) {
                if (isSync) return; // Prevent infinite loops
                isSync = true;

                try {
                    if (syncCenter) {
                        targetMap.setCenter(sourceMap.getCenter());
                    }
                    if (syncZoom) {
                        targetMap.setZoom(sourceMap.getZoom());
                    }
                    if (syncBearing) {
                        targetMap.setBearing(sourceMap.getBearing());
                    }
                    if (syncPitch) {
                        targetMap.setPitch(sourceMap.getPitch());
                    }
                } finally {
                    // Use requestAnimationFrame to reset flag after current event loop
                    requestAnimationFrame(() => {
                        isSync = false;
                    });
                }
            }

            // Use 'moveend' instead of 'move' to avoid interfering with scroll zoom
            beforeMap.on('moveend', () => syncMaps(beforeMap, afterMap));
            afterMap.on('moveend', () => syncMaps(afterMap, beforeMap));
        }
    }

    function setupMethodHandlers() {
        // Handle JavaScript method calls from Python
        model.on('change:_js_calls', function() {
            const calls = model.get('_js_calls') || [];
            calls.forEach(call => {
                handleJavaScriptCall(call);
            });
        });
    }

    function handleJavaScriptCall(call) {
        const { method, args, kwargs } = call;

        try {
            switch (method) {
                case 'setSlider':
                    if (compare) {
                        const position = args[0]; // This is a percentage (0-1)
                        isSettingSliderProgrammatically = true;

                        // Convert percentage to pixels
                        const containerRect = container.getBoundingClientRect();
                        const isVertical = (model.get('orientation') || 'vertical') === 'vertical';
                        const containerSize = isVertical ? containerRect.width : containerRect.height;
                        const pixelPosition = position * containerSize;

                        setTimeout(() => {
                            compare.setSlider(pixelPosition);
                            setTimeout(() => {
                                isSettingSliderProgrammatically = false;
                            }, 100);
                        }, 50);
                        model.set('slider_position', position);
                    }
                    break;

                case 'setOrientation':
                    if (compare) {
                        const orientation = args[0];
                        model.set('orientation', orientation);
                        recreateComparison();
                    }
                    break;

                case 'setMousemove':
                    if (compare) {
                        const mousemove = args[0];
                        model.set('mousemove', mousemove);
                        recreateComparison();
                    }
                    break;

                case 'setSyncOptions':
                    const syncOptions = args[0];
                    if (syncOptions) {
                        model.set('sync_center', syncOptions.center);
                        model.set('sync_zoom', syncOptions.zoom);
                        model.set('sync_bearing', syncOptions.bearing);
                        model.set('sync_pitch', syncOptions.pitch);
                        setupSynchronization();
                    }
                    break;

                case 'updateLeftMap':
                    const leftConfig = args[0];
                    if (beforeMap && leftConfig) {
                        if (leftConfig.style) {
                            beforeMap.setStyle(leftConfig.style);
                        }
                        if (leftConfig.center) {
                            beforeMap.setCenter([leftConfig.center[1], leftConfig.center[0]]);
                        }
                        if (leftConfig.zoom !== undefined) {
                            beforeMap.setZoom(leftConfig.zoom);
                        }
                        if (leftConfig.bearing !== undefined) {
                            beforeMap.setBearing(leftConfig.bearing);
                        }
                        if (leftConfig.pitch !== undefined) {
                            beforeMap.setPitch(leftConfig.pitch);
                        }
                        model.set('left_map_config', leftConfig);
                    }
                    break;

                case 'updateRightMap':
                    const rightConfig = args[0];
                    if (afterMap && rightConfig) {
                        if (rightConfig.style) {
                            afterMap.setStyle(rightConfig.style);
                        }
                        if (rightConfig.center) {
                            afterMap.setCenter([rightConfig.center[1], rightConfig.center[0]]);
                        }
                        if (rightConfig.zoom !== undefined) {
                            afterMap.setZoom(rightConfig.zoom);
                        }
                        if (rightConfig.bearing !== undefined) {
                            afterMap.setBearing(rightConfig.bearing);
                        }
                        if (rightConfig.pitch !== undefined) {
                            afterMap.setPitch(rightConfig.pitch);
                        }
                        model.set('right_map_config', rightConfig);
                    }
                    break;

                case 'flyTo':
                    const options = args[0];
                    if (beforeMap && afterMap && options) {
                        const flyToOptions = {
                            center: [options.center[1], options.center[0]],
                            zoom: options.zoom,
                            bearing: options.bearing,
                            pitch: options.pitch,
                            essential: true
                        };
                        beforeMap.flyTo(flyToOptions);
                        afterMap.flyTo(flyToOptions);
                    }
                    break;

                default:
                    console.warn(`Unknown method: ${method}`);
            }
        } catch (error) {
            console.error(`Error executing method ${method}:`, error);
        }
    }

    function recreateComparison() {
        if (compare) {
            compare.remove();
        }

        // Recreate comparison with new options
        compare = new maplibregl.Compare(beforeMap, afterMap, '#' + container.id, {
            orientation: model.get('orientation') || 'vertical',
            mousemove: model.get('mousemove') || false
        });

        // Restore slider position with delay
        const sliderPosition = model.get('slider_position');
        if (sliderPosition !== undefined) {
            isSettingSliderProgrammatically = true;
            setTimeout(() => {
                compare.setSlider(sliderPosition);
                setTimeout(() => {
                    isSettingSliderProgrammatically = false;
                }, 100);
            }, 100);
        }

        // Re-setup event listeners
        compare.on('slideend', function(event) {
            if (!isSettingSliderProgrammatically) {
                model.set('slider_position', event.currentPosition);
                const events = model.get('_js_events') || [];
                events.push({
                    type: 'slideend',
                    position: event.currentPosition
                });
                model.set('_js_events', events);
                model.save_changes();
            }
        });
    }

    // Handle model changes
    model.on('change:width', function() {
        container.style.width = model.get('width');
    });

    model.on('change:height', function() {
        container.style.height = model.get('height');
    });

    model.on('change:left_map_config', function() {
        const leftConfig = model.get('left_map_config');
        if (beforeMap && leftConfig) {
            if (leftConfig.style) {
                beforeMap.setStyle(leftConfig.style);
            }
            if (leftConfig.center) {
                beforeMap.setCenter([leftConfig.center[1], leftConfig.center[0]]);
            }
            if (leftConfig.zoom !== undefined) {
                beforeMap.setZoom(leftConfig.zoom);
            }
        }
    });

    model.on('change:right_map_config', function() {
        const rightConfig = model.get('right_map_config');
        if (afterMap && rightConfig) {
            if (rightConfig.style) {
                afterMap.setStyle(rightConfig.style);
            }
            if (rightConfig.center) {
                afterMap.setCenter([rightConfig.center[1], rightConfig.center[0]]);
            }
            if (rightConfig.zoom !== undefined) {
                afterMap.setZoom(rightConfig.zoom);
            }
        }
    });

    model.on('change:slider_position', function() {
        if (compare && !isSettingSliderProgrammatically) {
            const position = model.get('slider_position');
            isSettingSliderProgrammatically = true;
            setTimeout(() => {
                compare.setSlider(position);
                setTimeout(() => {
                    isSettingSliderProgrammatically = false;
                }, 100);
            }, 50);
        }
    });

    model.on('change:orientation', function() {
        recreateComparison();
    });

    model.on('change:mousemove', function() {
        recreateComparison();
    });

    // Initialize the maps
    initializeMaps();

    // Cleanup function
    return () => {
        if (compare) {
            compare.remove();
        }
        if (beforeMap) {
            beforeMap.remove();
        }
        if (afterMap) {
            afterMap.remove();
        }
    };
}

export default { render };