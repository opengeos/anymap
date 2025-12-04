"""Map comparison widget for side-by-side comparison of two maps."""

import pathlib
import anywidget
import traitlets
from typing import Dict, Any, Optional, Union, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from .base import MapWidget


class MapCompare(anywidget.AnyWidget):
    """Map comparison widget for side-by-side comparison of two maps.

    This widget allows comparing two maps side by side with a swipe interface.
    You can pass either configuration dictionaries or existing MapWidget instances.

    Example:
        Using configuration dictionaries:

        >>> compare = MapCompare(
        ...     left_map={"style": "streets", "center": [0, 0], "zoom": 2},
        ...     right_map={"style": "satellite", "center": [0, 0], "zoom": 2}
        ... )

        Using existing map objects:

        >>> from anymap import MapLibreMap
        >>> left = MapLibreMap(center=[40.7, -74.0], zoom=10)
        >>> left.add_layer("my-layer", {"type": "circle", ...})
        >>> right = MapLibreMap(center=[40.7, -74.0], zoom=10)
        >>> right.add_layer("another-layer", {"type": "fill", ...})
        >>> compare = MapCompare(left_map=left, right_map=right)

        Adding layers to comparison maps:

        >>> compare.add_left_source("my-source", {"type": "geojson", "data": ...})
        >>> compare.add_left_layer("my-layer", {"source": "my-source", ...})
    """

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
        left_map: Optional[Union[Dict[str, Any], "MapWidget"]] = None,
        right_map: Optional[Union[Dict[str, Any], "MapWidget"]] = None,
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
            left_map: Configuration for the left/before map. Can be either:
                - A dictionary with map configuration (style, center, zoom, etc.)
                - An existing MapWidget instance (MapLibreMap, MapboxMap, etc.)
                  whose full state including sources and layers will be extracted.
            right_map: Configuration for the right/after map. Same format as left_map.
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
        # Extract configuration from map objects if provided
        left_config = self._extract_map_config(left_map, backend, "left")
        right_config = self._extract_map_config(right_map, backend, "right")

        # Store references to original map objects for potential future sync
        self._left_map_obj = left_map if self._is_map_widget(left_map) else None
        self._right_map_obj = right_map if self._is_map_widget(right_map) else None

        # Track sources and layers added to each map
        self._left_sources: Dict[str, Any] = {}
        self._left_layers: Dict[str, Any] = {}
        self._right_sources: Dict[str, Any] = {}
        self._right_layers: Dict[str, Any] = {}

        super().__init__(
            left_map_config=left_config,
            right_map_config=right_config,
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

    def _is_map_widget(self, obj: Any) -> bool:
        """Check if an object is a MapWidget instance.

        Args:
            obj: Object to check.

        Returns:
            True if obj is a MapWidget instance, False otherwise.
        """
        if obj is None:
            return False
        # Check for MapWidget base class or common traits
        return (
            hasattr(obj, "_layers")
            and hasattr(obj, "_sources")
            and hasattr(obj, "center")
        )

    def _extract_map_config(
        self,
        map_input: Optional[Union[Dict[str, Any], "MapWidget"]],
        backend: str,
        side: str,
    ) -> Dict[str, Any]:
        """Extract map configuration from a map object or return the dict as-is.

        Args:
            map_input: Either a dict config or a MapWidget instance.
            backend: The backend type ("maplibre" or "mapbox").
            side: Which side this is for ("left" or "right"), used for defaults.

        Returns:
            A dictionary containing the full map configuration.
        """
        if map_input is None:
            # Return default configuration
            if side == "left":
                return {
                    "center": [0.0, 0.0],
                    "zoom": 2.0,
                    "style": (
                        "https://demotiles.maplibre.org/style.json"
                        if backend == "maplibre"
                        else "mapbox://styles/mapbox/streets-v12"
                    ),
                    "sources": {},
                    "layers": [],
                }
            else:
                return {
                    "center": [0.0, 0.0],
                    "zoom": 2.0,
                    "style": (
                        "https://demotiles.maplibre.org/style.json"
                        if backend == "maplibre"
                        else "mapbox://styles/mapbox/satellite-v9"
                    ),
                    "sources": {},
                    "layers": [],
                }

        if isinstance(map_input, dict):
            # It's already a config dict, ensure it has sources and layers
            config = dict(map_input)
            if "sources" not in config:
                config["sources"] = {}
            if "layers" not in config:
                config["layers"] = []
            return config

        # It's a MapWidget instance - extract its full state
        if self._is_map_widget(map_input):
            # MapLibreMap stores center as [lng, lat], but MapCompare JS expects [lat, lng]
            # so we swap the coordinates here
            center = (
                list(map_input.center) if hasattr(map_input, "center") else [0.0, 0.0]
            )
            # Convert from [lng, lat] to [lat, lng] for MapCompare convention
            center = [center[1], center[0]] if len(center) >= 2 else center

            config = {
                "center": center,
                "zoom": map_input.zoom if hasattr(map_input, "zoom") else 2.0,
                "sources": (
                    dict(map_input._sources) if hasattr(map_input, "_sources") else {}
                ),
                "layers": (
                    list(map_input._layers.values())
                    if hasattr(map_input, "_layers")
                    else []
                ),
            }

            # Extract style
            if hasattr(map_input, "style"):
                config["style"] = map_input.style
            elif hasattr(map_input, "_style"):
                config["style"] = map_input._style

            # Extract bearing, pitch, antialias if available
            if hasattr(map_input, "bearing"):
                config["bearing"] = map_input.bearing
            if hasattr(map_input, "pitch"):
                config["pitch"] = map_input.pitch
            if hasattr(map_input, "antialias"):
                config["antialias"] = map_input.antialias

            # Extract access token for Mapbox
            if hasattr(map_input, "access_token"):
                config["access_token"] = map_input.access_token

            # Extract terrain if available
            if hasattr(map_input, "_terrain") and map_input._terrain:
                config["terrain"] = dict(map_input._terrain)

            return config

        # Fallback: treat as dict
        return dict(map_input) if map_input else {}

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

    # =========================================================================
    # Methods for adding sources and layers to left/right maps
    # =========================================================================

    def add_left_source(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Add a data source to the left (before) map.

        Args:
            source_id: Unique identifier for the data source.
            source_config: Dictionary containing source configuration.

        Example:
            >>> compare.add_left_source("my-geojson", {
            ...     "type": "geojson",
            ...     "data": {"type": "FeatureCollection", "features": [...]}
            ... })
        """
        self._left_sources[source_id] = source_config
        self.call_js_method("addLeftSource", source_id, source_config)

    def add_right_source(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Add a data source to the right (after) map.

        Args:
            source_id: Unique identifier for the data source.
            source_config: Dictionary containing source configuration.

        Example:
            >>> compare.add_right_source("my-geojson", {
            ...     "type": "geojson",
            ...     "data": {"type": "FeatureCollection", "features": [...]}
            ... })
        """
        self._right_sources[source_id] = source_config
        self.call_js_method("addRightSource", source_id, source_config)

    def add_left_layer(
        self,
        layer_id: str,
        layer_config: Dict[str, Any],
        before_id: Optional[str] = None,
    ) -> None:
        """Add a layer to the left (before) map.

        Args:
            layer_id: Unique identifier for the layer.
            layer_config: Dictionary containing layer configuration.
            before_id: Optional ID of an existing layer to insert the new layer before.

        Example:
            >>> compare.add_left_layer("my-circles", {
            ...     "type": "circle",
            ...     "source": "my-geojson",
            ...     "paint": {"circle-radius": 5, "circle-color": "#ff0000"}
            ... })
        """
        config = dict(layer_config)
        config["id"] = layer_id
        self._left_layers[layer_id] = config
        self.call_js_method("addLeftLayer", config, before_id)

    def add_right_layer(
        self,
        layer_id: str,
        layer_config: Dict[str, Any],
        before_id: Optional[str] = None,
    ) -> None:
        """Add a layer to the right (after) map.

        Args:
            layer_id: Unique identifier for the layer.
            layer_config: Dictionary containing layer configuration.
            before_id: Optional ID of an existing layer to insert the new layer before.

        Example:
            >>> compare.add_right_layer("my-fills", {
            ...     "type": "fill",
            ...     "source": "my-geojson",
            ...     "paint": {"fill-color": "#00ff00", "fill-opacity": 0.5}
            ... })
        """
        config = dict(layer_config)
        config["id"] = layer_id
        self._right_layers[layer_id] = config
        self.call_js_method("addRightLayer", config, before_id)

    def remove_left_layer(self, layer_id: str) -> None:
        """Remove a layer from the left (before) map.

        Args:
            layer_id: Unique identifier of the layer to remove.
        """
        if layer_id in self._left_layers:
            del self._left_layers[layer_id]
        self.call_js_method("removeLeftLayer", layer_id)

    def remove_right_layer(self, layer_id: str) -> None:
        """Remove a layer from the right (after) map.

        Args:
            layer_id: Unique identifier of the layer to remove.
        """
        if layer_id in self._right_layers:
            del self._right_layers[layer_id]
        self.call_js_method("removeRightLayer", layer_id)

    def remove_left_source(self, source_id: str) -> None:
        """Remove a data source from the left (before) map.

        Args:
            source_id: Unique identifier of the source to remove.
        """
        if source_id in self._left_sources:
            del self._left_sources[source_id]
        self.call_js_method("removeLeftSource", source_id)

    def remove_right_source(self, source_id: str) -> None:
        """Remove a data source from the right (after) map.

        Args:
            source_id: Unique identifier of the source to remove.
        """
        if source_id in self._right_sources:
            del self._right_sources[source_id]
        self.call_js_method("removeRightSource", source_id)

    def get_left_layers(self) -> Dict[str, Any]:
        """Get all layers added to the left (before) map.

        Returns:
            Dictionary mapping layer IDs to their configurations.
        """
        return dict(self._left_layers)

    def get_right_layers(self) -> Dict[str, Any]:
        """Get all layers added to the right (after) map.

        Returns:
            Dictionary mapping layer IDs to their configurations.
        """
        return dict(self._right_layers)

    def get_left_sources(self) -> Dict[str, Any]:
        """Get all sources added to the left (before) map.

        Returns:
            Dictionary mapping source IDs to their configurations.
        """
        return dict(self._left_sources)

    def get_right_sources(self) -> Dict[str, Any]:
        """Get all sources added to the right (after) map.

        Returns:
            Dictionary mapping source IDs to their configurations.
        """
        return dict(self._right_sources)

    @property
    def left_map(self) -> Optional["MapWidget"]:
        """Get the original left map object if one was provided.

        Returns:
            The MapWidget instance used for the left map, or None if a config dict was used.

        Note:
            Changes to the returned map object will NOT automatically sync to the
            comparison widget. Use add_left_layer(), add_left_source(), etc. to
            modify the comparison maps.
        """
        return self._left_map_obj

    @property
    def right_map(self) -> Optional["MapWidget"]:
        """Get the original right map object if one was provided.

        Returns:
            The MapWidget instance used for the right map, or None if a config dict was used.

        Note:
            Changes to the returned map object will NOT automatically sync to the
            comparison widget. Use add_right_layer(), add_right_source(), etc. to
            modify the comparison maps.
        """
        return self._right_map_obj

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
        left_config = dict(self.left_map_config)
        right_config = dict(self.right_map_config)

        # Merge dynamically added sources and layers into configs
        # Ensure sources dict exists
        if "sources" not in left_config:
            left_config["sources"] = {}
        if "sources" not in right_config:
            right_config["sources"] = {}

        # Merge dynamically added sources
        left_config["sources"].update(self._left_sources)
        right_config["sources"].update(self._right_sources)

        # Ensure layers list exists
        if "layers" not in left_config:
            left_config["layers"] = []
        if "layers" not in right_config:
            right_config["layers"] = []

        # Merge dynamically added layers (avoid duplicates by id)
        existing_left_ids = {
            layer.get("id") for layer in left_config["layers"] if layer.get("id")
        }
        for layer_id, layer_config in self._left_layers.items():
            if layer_id not in existing_left_ids:
                left_config["layers"].append(layer_config)

        existing_right_ids = {
            layer.get("id") for layer in right_config["layers"] if layer.get("id")
        }
        for layer_id, layer_config in self._right_layers.items():
            if layer_id not in existing_right_ids:
                right_config["layers"].append(layer_config)

        widget_state = {
            "left_map_config": left_config,
            "right_map_config": right_config,
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
            map_js_url = "https://unpkg.com/maplibre-gl@5.10.0/dist/maplibre-gl.js"
            map_css_url = "https://unpkg.com/maplibre-gl@5.10.0/dist/maplibre-gl.css"
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
                // Add sources and layers from config
                addSourcesAndLayersFromConfig(beforeMap, leftConfig);
                addSourcesAndLayersFromConfig(afterMap, rightConfig);

                createComparison();
                setupEventListeners();
                // Note: MapLibre Compare plugin handles synchronization internally
                // Custom synchronization disabled to prevent conflicts and improve performance
            }});
        }}

        // Helper function to add sources and layers from config
        function addSourcesAndLayersFromConfig(map, config) {{
            if (!config) return;

            // Add sources first
            const sources = config.sources || {{}};
            for (const [sourceId, sourceConfig] of Object.entries(sources)) {{
                try {{
                    if (!map.getSource(sourceId)) {{
                        map.addSource(sourceId, sourceConfig);
                    }}
                }} catch (error) {{
                    console.warn(`Failed to add source ${{sourceId}}:`, error);
                }}
            }}

            // Add layers
            const layers = config.layers || [];
            for (const layerConfig of layers) {{
                try {{
                    if (layerConfig && layerConfig.id && !map.getLayer(layerConfig.id)) {{
                        map.addLayer(layerConfig);
                    }}
                }} catch (error) {{
                    console.warn(`Failed to add layer ${{layerConfig?.id}}:`, error);
                }}
            }}

            // Add terrain if configured
            if (config.terrain) {{
                try {{
                    map.setTerrain(config.terrain);
                }} catch (error) {{
                    console.warn('Failed to set terrain:', error);
                }}
            }}
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
