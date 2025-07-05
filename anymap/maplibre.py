"""MapLibre GL JS implementation of the map widget.

This module provides the MapLibreMap class which implements an interactive map
widget using the MapLibre GL JS library. MapLibre GL JS is an open-source fork
of Mapbox GL JS, providing fast vector map rendering with WebGL.

Classes:
    MapLibreMap: Main map widget class for MapLibre GL JS.

Example:
    Basic usage of MapLibreMap:

    >>> from anymap.maplibre import MapLibreMap
    >>> m = MapLibreMap(center=[40.7, -74.0], zoom=10)
    >>> m.add_basemap("OpenStreetMap.Mapnik")
    >>> m
"""

import pathlib
import requests
import traitlets
from typing import Dict, List, Any, Optional, Union
import json

from .base import MapWidget
from .utils import (
    construct_maplibre_style,
)


# Load MapLibre-specific js and css
with open(pathlib.Path(__file__).parent / "static" / "maplibre_widget.js", "r") as f:
    _esm_maplibre = f.read()

with open(pathlib.Path(__file__).parent / "static" / "maplibre_widget.css", "r") as f:
    _css_maplibre = f.read()


class MapLibreMap(MapWidget):
    """MapLibre GL JS implementation of the map widget.

    This class provides an interactive map widget using MapLibre GL JS,
    an open-source WebGL-based vector map renderer. It supports various
    data sources, custom styling, and interactive features.

    Attributes:
        style: Map style configuration (URL string or style object).
        bearing: Map rotation in degrees (0-360).
        pitch: Map tilt in degrees (0-60).
        antialias: Whether to enable antialiasing for better rendering quality.

    Example:
        Creating a basic MapLibre map:

        >>> m = MapLibreMap(
        ...     center=[40.7749, -122.4194],
        ...     zoom=12,
        ...     style="3d-satellite"
        ... )
        >>> m.add_basemap("OpenStreetMap.Mapnik")
    """

    # MapLibre-specific traits
    style = traitlets.Union(
        [traitlets.Unicode(), traitlets.Dict()],
        default_value="dark-matter",
    ).tag(sync=True)
    bearing = traitlets.Float(0.0).tag(sync=True)
    pitch = traitlets.Float(0.0).tag(sync=True)
    antialias = traitlets.Bool(True).tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_maplibre
    _css = _css_maplibre

    def __init__(
        self,
        center: List[float] = [0.0, 20],
        zoom: float = 1.0,
        style: Union[str, Dict[str, Any]] = "dark-matter",
        width: str = "100%",
        height: str = "600px",
        bearing: float = 0.0,
        pitch: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """Initialize MapLibre map widget.

        Args:
            center: Map center coordinates as [latitude, longitude].
            zoom: Initial zoom level (typically 0-20).
            style: MapLibre style URL string or style object dictionary.
            width: Widget width as CSS string (e.g., "100%", "800px").
            height: Widget height as CSS string (e.g., "600px", "50vh").
            bearing: Map bearing (rotation) in degrees (0-360).
            pitch: Map pitch (tilt) in degrees (0-60).
            **kwargs: Additional keyword arguments passed to parent class.
        """

        if isinstance(style, str):
            style = construct_maplibre_style(style)

        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            style=style,
            bearing=bearing,
            pitch=pitch,
            **kwargs,
        )

    def set_style(self, style: Union[str, Dict[str, Any]]) -> None:
        """Set the map style.

        Args:
            style: Map style as URL string or style object dictionary.
        """
        if isinstance(style, str):
            self.style = style
        else:
            self.call_js_method("setStyle", style)

    def set_bearing(self, bearing: float) -> None:
        """Set the map bearing (rotation).

        Args:
            bearing: Map rotation in degrees (0-360).
        """
        self.bearing = bearing

    def set_pitch(self, pitch: float) -> None:
        """Set the map pitch (tilt).

        Args:
            pitch: Map tilt in degrees (0-60).
        """
        self.pitch = pitch

    def set_layout_property(self, layer_id: str, name: str, value: Any) -> None:
        """Set a layout property for a layer.

        Args:
            layer_id: Unique identifier of the layer.
            name: Name of the layout property to set.
            value: Value to set for the property.
        """
        self.call_js_method("setLayoutProperty", layer_id, name, value)

    def set_paint_property(self, layer_id: str, name: str, value: Any) -> None:
        """Set a paint property for a layer.

        Args:
            layer_id: Unique identifier of the layer.
            name: Name of the paint property to set.
            value: Value to set for the property.
        """
        self.call_js_method("setPaintProperty", layer_id, name, value)

    def set_layer_visibility(self, layer_id: str, visible: bool) -> None:
        """Set the visibility of a layer.

        Args:
            layer_id: Unique identifier of the layer.
            visible: Whether the layer should be visible.
        """
        if visible:
            visibility = "visible"
        else:
            visibility = "none"
        self.set_layout_property(layer_id, "visibility", visibility)

    def set_layer_opacity(self, layer_id: str, opacity: float) -> None:
        """Set the opacity of a layer.

        Args:
            layer_id: Unique identifier of the layer.
            opacity: Opacity value between 0.0 (transparent) and 1.0 (opaque).
        """
        layer_type = self.get_layer_type(layer_id)

        if layer_type != "symbol":
            self.set_paint_property(layer_id, f"{layer_type}-opacity", opacity)
        else:
            self.set_paint_property(layer_id, "icon-opacity", opacity)
            self.set_paint_property(layer_id, "text-opacity", opacity)

    def get_layer_type(self, layer_id: str) -> Optional[str]:
        """Get the type of a layer.

        Args:
            layer_id: Unique identifier of the layer.

        Returns:
            Layer type string, or None if layer doesn't exist.
        """
        if layer_id in self._layers:
            return self._layers[layer_id]["type"]
        else:
            return None

    def add_layer(
        self,
        layer_id: str,
        layer_config: Dict[str, Any],
        before_id: Optional[str] = None,
    ) -> None:
        """Add a layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            layer_config: Layer configuration dictionary containing
                         properties like type, source, paint, and layout.
            before_id: Optional layer ID to insert this layer before.
                      If None, layer is added on top.
        """
        # Store layer in local state for persistence
        current_layers = dict(self._layers)
        current_layers[layer_id] = layer_config
        self._layers = current_layers

        # Call JavaScript method with before_id if provided
        if before_id:
            self.call_js_method("addLayer", layer_config, before_id)
        else:
            self.call_js_method("addLayer", layer_config, layer_id)

    def add_geojson_layer(
        self,
        layer_id: str,
        geojson_data: Dict[str, Any],
        layer_type: str = "fill",
        paint: Optional[Dict[str, Any]] = None,
        before_id: Optional[str] = None,
    ) -> None:
        """Add a GeoJSON layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            geojson_data: GeoJSON data as a dictionary.
            layer_type: Type of layer (e.g., 'fill', 'line', 'circle', 'symbol').
            paint: Optional paint properties for styling the layer.
            before_id: Optional layer ID to insert this layer before.
        """
        source_id = f"{layer_id}_source"

        # Add source
        self.add_source(source_id, {"type": "geojson", "data": geojson_data})

        # Add layer
        layer_config = {"id": layer_id, "type": layer_type, "source": source_id}

        if paint:
            layer_config["paint"] = paint

        self.add_layer(layer_id, layer_config, before_id)

    def add_marker(self, lat: float, lng: float, popup: Optional[str] = None) -> None:
        """Add a marker to the map.

        Args:
            lat: Latitude coordinate for the marker.
            lng: Longitude coordinate for the marker.
            popup: Optional popup text to display when marker is clicked.
        """
        marker_data = {"coordinates": [lng, lat], "popup": popup}
        self.call_js_method("addMarker", marker_data)

    def fit_bounds(self, bounds: List[List[float]], padding: int = 50) -> None:
        """Fit the map to given bounds.

        Args:
            bounds: Bounding box as [[south, west], [north, east]].
            padding: Padding around the bounds in pixels.
        """
        self.call_js_method("fitBounds", bounds, {"padding": padding})

    def add_tile_layer(
        self,
        layer_id: str,
        source_url: str,
        attribution: Optional[str] = None,
        opacity: Optional[float] = 1.0,
        visible: Optional[bool] = True,
        minzoom: Optional[int] = None,
        maxzoom: Optional[int] = None,
        paint: Optional[Dict[str, Any]] = None,
        layout: Optional[Dict[str, Any]] = None,
        before_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Add a raster tile layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            source_url: URL template for the tile source (e.g., 'https://example.com/{z}/{x}/{y}.png').
            attribution: Optional attribution text for the tile source.
            opacity: Layer opacity between 0.0 and 1.0.
            visible: Whether the layer should be visible initially.
            minzoom: Minimum zoom level for the layer.
            maxzoom: Maximum zoom level for the layer.
            paint: Optional paint properties for the layer.
            layout: Optional layout properties for the layer.
            before_id: Optional layer ID to insert this layer before.
            **kwargs: Additional source configuration options.
        """
        source_id = f"{layer_id}_source"

        # Add raster source
        self.add_source(
            source_id,
            {"type": "raster", "tiles": [source_url], "tileSize": 256, **kwargs},
        )

        # Add raster layer
        layer_config = {"id": layer_id, "type": "raster", "source": source_id}

        if paint:
            layer_config["paint"] = paint
        if layout:
            layer_config["layout"] = layout

        self.add_layer(layer_id, layer_config, before_id)

    def add_vector_layer(
        self,
        layer_id: str,
        source_url: str,
        source_layer: str,
        layer_type: str = "fill",
        paint: Optional[Dict[str, Any]] = None,
        layout: Optional[Dict[str, Any]] = None,
        before_id: Optional[str] = None,
    ) -> None:
        """Add a vector tile layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            source_url: URL for the vector tile source.
            source_layer: Name of the source layer within the vector tiles.
            layer_type: Type of layer (e.g., 'fill', 'line', 'circle', 'symbol').
            paint: Optional paint properties for styling the layer.
            layout: Optional layout properties for the layer.
            before_id: Optional layer ID to insert this layer before.
        """
        source_id = f"{layer_id}_source"

        # Add vector source
        self.add_source(source_id, {"type": "vector", "url": source_url})

        # Add vector layer
        layer_config = {
            "id": layer_id,
            "type": layer_type,
            "source": source_id,
            "source-layer": source_layer,
        }

        if paint:
            layer_config["paint"] = paint
        if layout:
            layer_config["layout"] = layout

        self.add_layer(layer_id, layer_config, before_id)

    def add_image_layer(
        self,
        layer_id: str,
        image_url: str,
        coordinates: List[List[float]],
        paint: Optional[Dict[str, Any]] = None,
        before_id: Optional[str] = None,
    ) -> None:
        """Add an image layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            image_url: URL of the image to display.
            coordinates: Corner coordinates of the image as [[top-left], [top-right], [bottom-right], [bottom-left]].
                        Each coordinate should be [longitude, latitude].
            paint: Optional paint properties for the image layer.
            before_id: Optional layer ID to insert this layer before.
        """
        source_id = f"{layer_id}_source"

        # Add image source
        self.add_source(
            source_id, {"type": "image", "url": image_url, "coordinates": coordinates}
        )

        # Add raster layer for the image
        layer_config = {"id": layer_id, "type": "raster", "source": source_id}

        if paint:
            layer_config["paint"] = paint

        self.add_layer(layer_id, layer_config, before_id)

    def add_basemap(
        self,
        basemap: str,
        layer_id: Optional[str] = None,
        before_id: Optional[str] = None,
    ) -> None:
        """Add a basemap to the map using xyzservices providers.

        Args:
            basemap: Name of the basemap from xyzservices (e.g., "Esri.WorldImagery").
                    Use available_basemaps to see all available options.
            layer_id: Optional ID for the basemap layer. If None, uses basemap name.
            before_id: Optional layer ID to insert this layer before.
                      If None, layer is added on top.

        Raises:
            ValueError: If the specified basemap is not available.
        """
        from .basemaps import available_basemaps

        if basemap not in available_basemaps:
            available_names = list(available_basemaps.keys())
            raise ValueError(
                f"Basemap '{basemap}' not found. Available basemaps: {available_names}"
            )

        basemap_config = available_basemaps[basemap]

        # Convert xyzservices URL template to tile URL
        tile_url = basemap_config.build_url()

        # Get attribution if available
        attribution = basemap_config.get("attribution", "")
        if layer_id is None:
            layer_id = basemap

        # Add as raster layer
        self.add_tile_layer(
            layer_id=layer_id,
            source_url=tile_url,
            paint={"raster-opacity": 1.0},
            before_id=before_id,
        )

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs: Any
    ) -> str:
        """Generate HTML template for MapLibre GL JS.

        Args:
            map_state: Dictionary containing the current map state including
                      center, zoom, style, layers, and sources.
            title: Title for the HTML page.
            **kwargs: Additional arguments for template customization.

        Returns:
            Complete HTML string for a standalone MapLibre GL JS map.
        """
        # Serialize map state for JavaScript
        map_state_json = json.dumps(map_state, indent=2)

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js"></script>
    <link href="https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css" rel="stylesheet">
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
        }}
        #map {{
            width: {map_state['width']};
            height: {map_state['height']};
            border: 1px solid #ccc;
        }}
        h1 {{
            margin-top: 0;
            color: #333;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div id="map"></div>

    <script>
        // Map state from Python
        const mapState = {map_state_json};

        // Initialize MapLibre map
        const map = new maplibregl.Map({{
            container: 'map',
            style: mapState.style || 'https://demotiles.maplibre.org/style.json',
            center: [mapState.center[1], mapState.center[0]], // Convert [lat, lng] to [lng, lat]
            zoom: mapState.zoom || 2,
            bearing: mapState.bearing || 0,
            pitch: mapState.pitch || 0,
            antialias: mapState.antialias !== undefined ? mapState.antialias : true
        }});

        // Restore layers and sources after map loads
        map.on('load', function() {{
            // Add sources first
            const sources = mapState._sources || {{}};
            Object.entries(sources).forEach(([sourceId, sourceConfig]) => {{
                try {{
                    map.addSource(sourceId, sourceConfig);
                }} catch (error) {{
                    console.warn(`Failed to add source ${{sourceId}}:`, error);
                }}
            }});

            // Then add layers
            const layers = mapState._layers || {{}};
            Object.entries(layers).forEach(([layerId, layerConfig]) => {{
                try {{
                    map.addLayer(layerConfig);
                }} catch (error) {{
                    console.warn(`Failed to add layer ${{layerId}}:`, error);
                }}
            }});
        }});

        // Add navigation controls
        map.addControl(new maplibregl.NavigationControl());

        // Add scale control
        map.addControl(new maplibregl.ScaleControl());

        // Log map events for debugging
        map.on('click', function(e) {{
            console.log('Map clicked at:', e.lngLat);
        }});

        map.on('load', function() {{
            console.log('Map loaded successfully');
        }});

        map.on('error', function(e) {{
            console.error('Map error:', e);
        }});
    </script>
</body>
</html>"""

        return html_template
