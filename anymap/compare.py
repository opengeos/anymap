"""Map comparison widget for side-by-side comparison of two maps."""

import pathlib
import anywidget
import traitlets
from typing import Dict, Any, Optional
import json


class MapCompare(anywidget.AnyWidget):
    """Map comparison widget for side-by-side comparison of two maps."""

    # Map configuration traits
    left_map_config = traitlets.Dict({}).tag(sync=True)
    right_map_config = traitlets.Dict({}).tag(sync=True)

    # Widget dimensions
    width = traitlets.Unicode("100%").tag(sync=True)
    height = traitlets.Unicode("600px").tag(sync=True)

    # Comparison options
    orientation = traitlets.Unicode("vertical").tag(
        sync=True
    )  # "vertical" or "horizontal"
    mousemove = traitlets.Bool(False).tag(sync=True)  # Enable swipe on mouse move
    slider_position = traitlets.Float(0.5).tag(sync=True)  # Slider position (0-1)

    # Backend type
    backend = traitlets.Unicode("maplibre").tag(sync=True)  # "maplibre" or "mapbox"

    # Synchronization options
    sync_center = traitlets.Bool(True).tag(sync=True)
    sync_zoom = traitlets.Bool(True).tag(sync=True)
    sync_bearing = traitlets.Bool(True).tag(sync=True)
    sync_pitch = traitlets.Bool(True).tag(sync=True)

    # Communication traits
    _js_calls = traitlets.List([]).tag(sync=True)
    _js_events = traitlets.List([]).tag(sync=True)

    def __init__(
        self,
        left_map: Optional[Dict[str, Any]] = None,
        right_map: Optional[Dict[str, Any]] = None,
        backend: str = "maplibre",
        orientation: str = "vertical",
        mousemove: bool = False,
        width: str = "100%",
        height: str = "600px",
        sync_center: bool = True,
        sync_zoom: bool = True,
        sync_bearing: bool = True,
        sync_pitch: bool = True,
        **kwargs,
    ):
        """Initialize MapCompare widget.

        Args:
            left_map: Configuration for the left/before map
            right_map: Configuration for the right/after map
            backend: Map backend to use ("maplibre" or "mapbox")
            orientation: Comparison orientation ("vertical" or "horizontal")
            mousemove: Enable swipe on mouse move
            width: Widget width
            height: Widget height
            sync_center: Synchronize map center
            sync_zoom: Synchronize map zoom
            sync_bearing: Synchronize map bearing
            sync_pitch: Synchronize map pitch
        """
        # Set default map configurations
        if left_map is None:
            left_map = {
                "center": [0.0, 0.0],
                "zoom": 2.0,
                "style": (
                    "https://demotiles.maplibre.org/style.json"
                    if backend == "maplibre"
                    else "mapbox://styles/mapbox/streets-v12"
                ),
            }
        if right_map is None:
            right_map = {
                "center": [0.0, 0.0],
                "zoom": 2.0,
                "style": (
                    "https://demotiles.maplibre.org/style.json"
                    if backend == "maplibre"
                    else "mapbox://styles/mapbox/satellite-v9"
                ),
            }

        super().__init__(
            left_map_config=left_map,
            right_map_config=right_map,
            backend=backend,
            orientation=orientation,
            mousemove=mousemove,
            width=width,
            height=height,
            sync_center=sync_center,
            sync_zoom=sync_zoom,
            sync_bearing=sync_bearing,
            sync_pitch=sync_pitch,
            **kwargs,
        )

        self._event_handlers = {}
        self._js_method_counter = 0

        # Set JavaScript and CSS based on backend
        if backend == "maplibre":
            self._esm = self._load_maplibre_compare_js()
            self._css = self._load_maplibre_compare_css()
        else:  # mapbox
            self._esm = self._load_mapbox_compare_js()
            self._css = self._load_mapbox_compare_css()

    def _load_maplibre_compare_js(self) -> str:
        """Load MapLibre comparison JavaScript code."""
        # This will be implemented when we create the JS file
        try:
            with open(
                pathlib.Path(__file__).parent / "static" / "maplibre_compare_widget.js",
                "r",
            ) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _load_maplibre_compare_css(self) -> str:
        """Load MapLibre comparison CSS styles."""
        try:
            with open(
                pathlib.Path(__file__).parent
                / "static"
                / "maplibre_compare_widget.css",
                "r",
            ) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _load_mapbox_compare_js(self) -> str:
        """Load Mapbox comparison JavaScript code."""
        try:
            with open(
                pathlib.Path(__file__).parent / "static" / "mapbox_compare_widget.js",
                "r",
            ) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _load_mapbox_compare_css(self) -> str:
        """Load Mapbox comparison CSS styles."""
        try:
            with open(
                pathlib.Path(__file__).parent / "static" / "mapbox_compare_widget.css",
                "r",
            ) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def call_js_method(self, method_name: str, *args, **kwargs) -> None:
        """Call a JavaScript method on the compare instance."""
        call_data = {
            "id": self._js_method_counter,
            "method": method_name,
            "args": args,
            "kwargs": kwargs,
        }
        self._js_method_counter += 1

        # Trigger sync by creating new list
        current_calls = list(self._js_calls)
        current_calls.append(call_data)
        self._js_calls = current_calls

    def on_event(self, event_type: str, callback):
        """Register a callback for comparison events."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(callback)

    @traitlets.observe("_js_events")
    def _handle_js_events(self, change):
        """Handle events from JavaScript."""
        events = change["new"]
        for event in events:
            event_type = event.get("type")
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    handler(event)

    def set_slider_position(self, position: float) -> None:
        """Set the slider position.

        Args:
            position: Slider position (0.0 to 1.0)
        """
        if not 0.0 <= position <= 1.0:
            raise ValueError("Position must be between 0.0 and 1.0")
        self.slider_position = position
        self.call_js_method("setSlider", position)

    def set_orientation(self, orientation: str) -> None:
        """Set the comparison orientation.

        Args:
            orientation: "vertical" or "horizontal"
        """
        if orientation not in ["vertical", "horizontal"]:
            raise ValueError("Orientation must be 'vertical' or 'horizontal'")
        self.orientation = orientation
        self.call_js_method("setOrientation", orientation)

    def enable_mousemove(self, enabled: bool = True) -> None:
        """Enable or disable swipe on mouse move.

        Args:
            enabled: Whether to enable mousemove
        """
        self.mousemove = enabled
        self.call_js_method("setMousemove", enabled)

    def set_sync_options(
        self,
        center: Optional[bool] = None,
        zoom: Optional[bool] = None,
        bearing: Optional[bool] = None,
        pitch: Optional[bool] = None,
    ) -> None:
        """Set synchronization options.

        Args:
            center: Synchronize map center
            zoom: Synchronize map zoom
            bearing: Synchronize map bearing
            pitch: Synchronize map pitch
        """
        if center is not None:
            self.sync_center = center
        if zoom is not None:
            self.sync_zoom = zoom
        if bearing is not None:
            self.sync_bearing = bearing
        if pitch is not None:
            self.sync_pitch = pitch

        sync_options = {
            "center": self.sync_center,
            "zoom": self.sync_zoom,
            "bearing": self.sync_bearing,
            "pitch": self.sync_pitch,
        }
        self.call_js_method("setSyncOptions", sync_options)

    def update_left_map(self, config: Dict[str, Any]) -> None:
        """Update the left map configuration.

        Args:
            config: New configuration for the left map
        """
        self.left_map_config = config
        self.call_js_method("updateLeftMap", config)

    def update_right_map(self, config: Dict[str, Any]) -> None:
        """Update the right map configuration.

        Args:
            config: New configuration for the right map
        """
        self.right_map_config = config
        self.call_js_method("updateRightMap", config)

    def fly_to(self, lat: float, lng: float, zoom: Optional[float] = None) -> None:
        """Fly both maps to a specific location.

        Args:
            lat: Latitude
            lng: Longitude
            zoom: Zoom level (optional)
        """
        options = {"center": [lat, lng]}
        if zoom is not None:
            options["zoom"] = zoom
        self.call_js_method("flyTo", options)

    def to_html(
        self,
        filename: Optional[str] = None,
        title: str = "Map Comparison",
        **kwargs,
    ) -> str:
        """Export the comparison widget to a standalone HTML file.

        Args:
            filename: Optional filename to save the HTML. If None, returns HTML string.
            title: Title for the HTML page
            **kwargs: Additional arguments passed to the HTML template

        Returns:
            HTML string content
        """
        # Get the current widget state
        widget_state = {
            "left_map_config": dict(self.left_map_config),
            "right_map_config": dict(self.right_map_config),
            "backend": self.backend,
            "orientation": self.orientation,
            "mousemove": self.mousemove,
            "slider_position": self.slider_position,
            "sync_center": self.sync_center,
            "sync_zoom": self.sync_zoom,
            "sync_bearing": self.sync_bearing,
            "sync_pitch": self.sync_pitch,
            "width": self.width,
            "height": self.height,
        }

        # Generate HTML content
        html_content = self._generate_html_template(widget_state, title, **kwargs)

        # Save to file if filename is provided
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content

    def _generate_html_template(
        self, widget_state: Dict[str, Any], title: str, **kwargs
    ) -> str:
        """Generate the HTML template for map comparison."""
        # Serialize widget state for JavaScript
        widget_state_json = json.dumps(widget_state, indent=2)

        # Choose CDN URLs based on backend
        if widget_state["backend"] == "maplibre":
            map_js_url = "https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js"
            map_css_url = "https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css"
            global_var = "maplibregl"
        else:  # mapbox
            map_js_url = "https://api.mapbox.com/mapbox-gl-js/v3.13.0/mapbox-gl.js"
            map_css_url = "https://api.mapbox.com/mapbox-gl-js/v3.13.0/mapbox-gl.css"
            global_var = "mapboxgl"

        # Generate access token warning for Mapbox
        access_token_warning = ""
        if widget_state["backend"] == "mapbox":
            left_token = widget_state["left_map_config"].get("access_token", "")
            right_token = widget_state["right_map_config"].get("access_token", "")
            if not left_token and not right_token:
                access_token_warning = """
                    <div class="access-token-warning">
                        <strong>Warning:</strong> This map requires a Mapbox access token.
                        Get a free token at <a href="https://account.mapbox.com/access-tokens/" target="_blank">Mapbox</a>
                        and set it in the JavaScript code below.
                    </div>
                """

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="{map_js_url}"></script>
    <link href="{map_css_url}" rel="stylesheet">
    <script src="https://unpkg.com/@maplibre/maplibre-gl-compare@0.5.0/dist/maplibre-gl-compare.js"></script>
    <link href="https://unpkg.com/@maplibre/maplibre-gl-compare@0.5.0/dist/maplibre-gl-compare.css" rel="stylesheet">
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            padding: 20px;
            background-color: #fff;
            border-bottom: 1px solid #eee;
        }}
        h1 {{
            margin: 0;
            color: #333;
            font-size: 24px;
        }}
        .map-container {{
            position: relative;
            width: {widget_state['width']};
            height: {widget_state['height']};
            margin: 20px;
        }}
        #comparison-container {{
            position: relative;
            width: 100%;
            height: 100%;
            overflow: hidden;
            border: 1px solid #ccc;
            border-radius: 4px;
        }}
        #before, #after {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
            height: 100%;
        }}
        .access-token-warning {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            margin: 20px;
            border-radius: 4px;
        }}
        .access-token-warning a {{
            color: #856404;
            text-decoration: underline;
        }}
        .controls {{
            padding: 20px;
            background-color: #f8f9fa;
            border-top: 1px solid #eee;
        }}
        .control-group {{
            margin-bottom: 15px;
        }}
        .control-group label {{
            display: inline-block;
            width: 120px;
            font-weight: bold;
            color: #333;
        }}
        .control-group input, .control-group select {{
            padding: 5px 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
        }}
        .control-group button {{
            padding: 8px 16px;
            background-color: #007cba;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .control-group button:hover {{
            background-color: #005a8b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p>Interactive map comparison powered by anymap</p>
        </div>

        {access_token_warning}

        <div class="map-container">
            <div id="comparison-container">
                <div id="before"></div>
                <div id="after"></div>
            </div>
        </div>

        <div class="controls">
            <div class="control-group">
                <label>Note:</label>
                <span>Use the slider on the map to adjust position</span>
            </div>

            <div class="control-group">
                <label for="orientation">Orientation:</label>
                <select id="orientation">
                    <option value="vertical" {"selected" if widget_state['orientation'] == 'vertical' else ""}>Vertical</option>
                    <option value="horizontal" {"selected" if widget_state['orientation'] == 'horizontal' else ""}>Horizontal</option>
                </select>
            </div>

            <div class="control-group">
                <label for="mousemove">Mouse Move:</label>
                <input type="checkbox" id="mousemove" {"checked" if widget_state['mousemove'] else ""}>
                <span>Enable swipe on mouse move</span>
            </div>

            <div class="control-group">
                <button onclick="flyToSanFrancisco()">Fly to San Francisco</button>
                <button onclick="flyToNewYork()">Fly to New York</button>
                <button onclick="flyToLondon()">Fly to London</button>
                <button onclick="flyToTokyo()">Fly to Tokyo</button>
            </div>
        </div>
    </div>

    <script>
        // Widget state from Python
        const widgetState = {widget_state_json};

        // Set access token for Mapbox if needed
        if (widgetState.backend === 'mapbox') {{
            const accessToken = widgetState.left_map_config.access_token || widgetState.right_map_config.access_token || '';
            if (accessToken) {{
                {global_var}.accessToken = accessToken;
            }}
        }}

        // Initialize maps
        let beforeMap, afterMap, compare;

        function initializeMaps() {{
            const leftConfig = widgetState.left_map_config;
            const rightConfig = widgetState.right_map_config;

            // Create before map
            beforeMap = new {global_var}.Map({{
                container: 'before',
                style: leftConfig.style,
                center: leftConfig.center ? [leftConfig.center[1], leftConfig.center[0]] : [0, 0],
                zoom: leftConfig.zoom || 2,
                bearing: leftConfig.bearing || 0,
                pitch: leftConfig.pitch || 0,
                antialias: leftConfig.antialias !== undefined ? leftConfig.antialias : true
            }});

            // Create after map
            afterMap = new {global_var}.Map({{
                container: 'after',
                style: rightConfig.style,
                center: rightConfig.center ? [rightConfig.center[1], rightConfig.center[0]] : [0, 0],
                zoom: rightConfig.zoom || 2,
                bearing: rightConfig.bearing || 0,
                pitch: rightConfig.pitch || 0,
                antialias: rightConfig.antialias !== undefined ? rightConfig.antialias : true
            }});

            // Wait for both maps to load
            Promise.all([
                new Promise(resolve => beforeMap.on('load', resolve)),
                new Promise(resolve => afterMap.on('load', resolve))
            ]).then(() => {{
                createComparison();
                setupEventListeners();
                // Note: MapLibre Compare plugin handles synchronization internally
                // Custom synchronization disabled to prevent conflicts and improve performance
            }});
        }}

        function createComparison() {{
            if (compare) {{
                compare.remove();
            }}

            compare = new {global_var}.Compare(beforeMap, afterMap, "#comparison-container", {{
                orientation: widgetState.orientation,
                mousemove: widgetState.mousemove
            }});

            console.log('Compare widget created successfully');
            console.log('Before map scrollZoom enabled:', beforeMap.scrollZoom.isEnabled());
            console.log('After map scrollZoom enabled:', afterMap.scrollZoom.isEnabled());
        }}

        function setupSynchronization() {{
            if (widgetState.sync_center || widgetState.sync_zoom || widgetState.sync_bearing || widgetState.sync_pitch) {{
                let isSync = false;

                function syncMaps(sourceMap, targetMap) {{
                    if (isSync) return; // Prevent infinite loops
                    isSync = true;

                    try {{
                        if (widgetState.sync_center) {{
                            targetMap.setCenter(sourceMap.getCenter());
                        }}
                        if (widgetState.sync_zoom) {{
                            targetMap.setZoom(sourceMap.getZoom());
                        }}
                        if (widgetState.sync_bearing) {{
                            targetMap.setBearing(sourceMap.getBearing());
                        }}
                        if (widgetState.sync_pitch) {{
                            targetMap.setPitch(sourceMap.getPitch());
                        }}
                    }} finally {{
                        // Use requestAnimationFrame to reset flag after current event loop
                        requestAnimationFrame(() => {{
                            isSync = false;
                        }});
                    }}
                }}

                // Use 'moveend' instead of 'move' to avoid interfering with scroll zoom
                beforeMap.on('moveend', () => syncMaps(beforeMap, afterMap));
                afterMap.on('moveend', () => syncMaps(afterMap, beforeMap));
            }}
        }}

        function setupEventListeners() {{
            // Orientation control
            document.getElementById('orientation').addEventListener('change', function(e) {{
                widgetState.orientation = e.target.value;
                createComparison();
            }});

            // Mousemove control
            document.getElementById('mousemove').addEventListener('change', function(e) {{
                widgetState.mousemove = e.target.checked;
                createComparison();
            }});
        }}

        // Navigation functions
        function flyToSanFrancisco() {{
            const center = [-122.4194, 37.7749];
            const zoom = 12;
            beforeMap.flyTo({{ center: center, zoom: zoom, essential: true }});
            afterMap.flyTo({{ center: center, zoom: zoom, essential: true }});
        }}

        function flyToNewYork() {{
            const center = [-74.0060, 40.7128];
            const zoom = 12;
            beforeMap.flyTo({{ center: center, zoom: zoom, essential: true }});
            afterMap.flyTo({{ center: center, zoom: zoom, essential: true }});
        }}

        function flyToLondon() {{
            const center = [-0.1278, 51.5074];
            const zoom = 12;
            beforeMap.flyTo({{ center: center, zoom: zoom, essential: true }});
            afterMap.flyTo({{ center: center, zoom: zoom, essential: true }});
        }}

        function flyToTokyo() {{
            const center = [139.6917, 35.6895];
            const zoom = 12;
            beforeMap.flyTo({{ center: center, zoom: zoom, essential: true }});
            afterMap.flyTo({{ center: center, zoom: zoom, essential: true }});
        }}

        // Initialize the comparison
        initializeMaps();

        // Log successful initialization
        console.log('Map comparison initialized successfully');
    </script>
</body>
</html>"""

        return html_template
