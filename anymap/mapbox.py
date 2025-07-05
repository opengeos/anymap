"""Mapbox GL JS implementation of the map widget.

This module provides the MapboxMap class which implements an interactive map
widget using the Mapbox GL JS library. Mapbox GL JS provides fast vector map
rendering with WebGL and requires an access token for Mapbox services.

Classes:
    MapboxMap: Main map widget class for Mapbox GL JS.

Note:
    Mapbox services require an access token. You can get a free token at
    https://account.mapbox.com/access-tokens/

Example:
    Basic usage of MapboxMap:

    >>> from anymap.mapbox import MapboxMap
    >>> m = MapboxMap(
    ...     center=[40.7, -74.0],
    ...     zoom=10,
    ...     access_token="your_mapbox_token"
    ... )
    >>> m.add_basemap("OpenStreetMap.Mapnik")
    >>> m
"""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union
import json

from .base import MapWidget
from .basemaps import available_basemaps

# Load Mapbox-specific js and css
with open(pathlib.Path(__file__).parent / "static" / "mapbox_widget.js", "r") as f:
    _esm_mapbox = f.read()

with open(pathlib.Path(__file__).parent / "static" / "mapbox_widget.css", "r") as f:
    _css_mapbox = f.read()


class MapboxMap(MapWidget):
    """Mapbox GL JS implementation of the map widget."""

    # Mapbox-specific traits
    style = traitlets.Unicode("mapbox://styles/mapbox/streets-v12").tag(sync=True)
    bearing = traitlets.Float(0.0).tag(sync=True)
    pitch = traitlets.Float(0.0).tag(sync=True)
    antialias = traitlets.Bool(True).tag(sync=True)
    access_token = traitlets.Unicode("").tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_mapbox
    _css = _css_mapbox

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        style: str = "mapbox://styles/mapbox/streets-v12",
        width: str = "100%",
        height: str = "600px",
        bearing: float = 0.0,
        pitch: float = 0.0,
        access_token: str = "",
        **kwargs,
    ):
        """Initialize Mapbox map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level
            style: Mapbox style URL or style object
            width: Widget width
            height: Widget height
            bearing: Map bearing (rotation) in degrees
            pitch: Map pitch (tilt) in degrees
            access_token: Mapbox access token (required for Mapbox services).
                         Get a free token at https://account.mapbox.com/access-tokens/
                         Can also be set via MAPBOX_TOKEN environment variable.
        """
        # Set default access token if not provided
        if not access_token:
            access_token = self._get_default_access_token()

        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            style=style,
            bearing=bearing,
            pitch=pitch,
            access_token=access_token,
            **kwargs,
        )

    @staticmethod
    def _get_default_access_token() -> str:
        """Get default Mapbox access token from environment or return demo token."""
        import os

        # Try to get from environment variable
        token = os.environ.get("MAPBOX_TOKEN") or os.environ.get("MAPBOX_ACCESS_TOKEN")

        # If no token found, return empty string - user must provide their own token
        if not token:
            import warnings

            warnings.warn(
                "No Mapbox access token found. Please set MAPBOX_ACCESS_TOKEN environment variable "
                "or pass access_token parameter. Get a free token at https://account.mapbox.com/access-tokens/",
                UserWarning,
            )
            token = ""

        return token

    def set_access_token(self, token: str) -> None:
        """Set the Mapbox access token."""
        self.access_token = token

    def set_style(self, style: Union[str, Dict[str, Any]]) -> None:
        """Set the map style."""
        if isinstance(style, str):
            self.style = style
        else:
            self.call_js_method("setStyle", style)

    def set_bearing(self, bearing: float) -> None:
        """Set the map bearing (rotation)."""
        self.bearing = bearing

    def set_pitch(self, pitch: float) -> None:
        """Set the map pitch (tilt)."""
        self.pitch = pitch

    def add_geojson_layer(
        self,
        layer_id: str,
        geojson_data: Dict[str, Any],
        layer_type: str = "fill",
        paint: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a GeoJSON layer to the map."""
        source_id = f"{layer_id}_source"

        # Add source
        self.add_source(source_id, {"type": "geojson", "data": geojson_data})

        # Add layer
        layer_config = {"id": layer_id, "type": layer_type, "source": source_id}

        if paint:
            layer_config["paint"] = paint

        self.add_layer(layer_id, layer_config)

    def add_marker(self, lat: float, lng: float, popup: Optional[str] = None) -> None:
        """Add a marker to the map."""
        marker_data = {"coordinates": [lng, lat], "popup": popup}
        self.call_js_method("addMarker", marker_data)

    def fit_bounds(self, bounds: List[List[float]], padding: int = 50) -> None:
        """Fit the map to given bounds."""
        self.call_js_method("fitBounds", bounds, {"padding": padding})

    def add_tile_layer(
        self,
        layer_id: str,
        source_url: str,
        paint: Optional[Dict[str, Any]] = None,
        layout: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a raster layer to the map."""
        source_id = f"{layer_id}_source"

        # Add raster source
        self.add_source(
            source_id, {"type": "raster", "tiles": [source_url], "tileSize": 256}
        )

        # Add raster layer
        layer_config = {"id": layer_id, "type": "raster", "source": source_id}

        if paint:
            layer_config["paint"] = paint
        if layout:
            layer_config["layout"] = layout

        self.add_layer(layer_id, layer_config)

    def add_vector_layer(
        self,
        layer_id: str,
        source_url: str,
        source_layer: str,
        layer_type: str = "fill",
        paint: Optional[Dict[str, Any]] = None,
        layout: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a vector tile layer to the map."""
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

        self.add_layer(layer_id, layer_config)

    def add_image_layer(
        self,
        layer_id: str,
        image_url: str,
        coordinates: List[List[float]],
        paint: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an image layer to the map."""
        source_id = f"{layer_id}_source"

        # Add image source
        self.add_source(
            source_id, {"type": "image", "url": image_url, "coordinates": coordinates}
        )

        # Add raster layer for the image
        layer_config = {"id": layer_id, "type": "raster", "source": source_id}

        if paint:
            layer_config["paint"] = paint

        self.add_layer(layer_id, layer_config)

    def add_control(
        self,
        control_type: str,
        position: str = "top-right",
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a control to the map.

        Args:
            control_type: Type of control ('navigation', 'scale', 'fullscreen', 'geolocate')
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            options: Additional options for the control
        """
        control_options = options or {}
        control_options["position"] = position
        self.call_js_method("addControl", control_type, control_options)

    def set_terrain(self, terrain_config: Optional[Dict[str, Any]] = None) -> None:
        """Set 3D terrain on the map.

        Args:
            terrain_config: Terrain configuration dict, or None to remove terrain
        """
        self.call_js_method("setTerrain", terrain_config)

    def set_fog(self, fog_config: Optional[Dict[str, Any]] = None) -> None:
        """Set atmospheric fog on the map.

        Args:
            fog_config: Fog configuration dict, or None to remove fog
        """
        self.call_js_method("setFog", fog_config)

    def add_3d_buildings(self, layer_id: str = "3d-buildings") -> None:
        """Add 3D buildings layer to the map."""
        # Add the layer for 3D buildings
        layer_config = {
            "id": layer_id,
            "source": "composite",
            "source-layer": "building",
            "filter": ["==", "extrude", "true"],
            "type": "fill-extrusion",
            "minzoom": 15,
            "paint": {
                "fill-extrusion-color": "#aaa",
                "fill-extrusion-height": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    15,
                    0,
                    15.05,
                    ["get", "height"],
                ],
                "fill-extrusion-base": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    15,
                    0,
                    15.05,
                    ["get", "min_height"],
                ],
                "fill-extrusion-opacity": 0.6,
            },
        }
        self.add_layer(layer_id, layer_config)

    def add_basemap(self, basemap: str, layer_id: str = "basemap") -> None:
        """Add a basemap to the map using xyzservices providers.

        Args:
            basemap: Name of the basemap from xyzservices (e.g., "Esri.WorldImagery")
            layer_id: ID for the basemap layer (default: "basemap")
        """
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

        # Add as raster layer
        self.add_tile_layer(
            layer_id=layer_id, source_url=tile_url, paint={"raster-opacity": 1.0}
        )

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs
    ) -> str:
        """Generate HTML template for Mapbox GL JS."""
        # Serialize map state for JavaScript
        map_state_json = json.dumps(map_state, indent=2)

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.13.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.13.0/mapbox-gl.css" rel="stylesheet">
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
        .access-token-warning {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {"<div class='access-token-warning'>Warning: This map requires a Mapbox access token. Please add your token to the mapboxgl.accessToken property.</div>" if not map_state.get('access_token') else ""}
    <div id="map"></div>

    <script>
        // Map state from Python
        const mapState = {map_state_json};

        // Set Mapbox access token
        mapboxgl.accessToken = mapState.access_token || '';

        // Initialize Mapbox map
        const map = new mapboxgl.Map({{
            container: 'map',
            style: mapState.style || 'mapbox://styles/mapbox/streets-v12',
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
        map.addControl(new mapboxgl.NavigationControl());

        // Add scale control
        map.addControl(new mapboxgl.ScaleControl());

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
