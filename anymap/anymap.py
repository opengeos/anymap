"""Main module for anymap interactive mapping widgets."""

import pathlib
import anywidget
import traitlets
from typing import Dict, List, Any, Optional, Union
import json


class MapWidget(anywidget.AnyWidget):
    """Base class for interactive map widgets using anywidget."""

    # Widget traits for communication with JavaScript
    center = traitlets.List([0.0, 0.0]).tag(sync=True)
    zoom = traitlets.Float(2.0).tag(sync=True)
    width = traitlets.Unicode("100%").tag(sync=True)
    height = traitlets.Unicode("600px").tag(sync=True)
    style = traitlets.Unicode("").tag(sync=True)

    # Communication traits
    _js_calls = traitlets.List([]).tag(sync=True)
    _js_events = traitlets.List([]).tag(sync=True)

    # Internal state
    _layers = traitlets.Dict({}).tag(sync=True)
    _sources = traitlets.Dict({}).tag(sync=True)

    def __init__(self, **kwargs):
        """Initialize the map widget."""
        super().__init__(**kwargs)
        self._event_handlers = {}
        self._js_method_counter = 0

    def call_js_method(self, method_name: str, *args, **kwargs) -> None:
        """Call a JavaScript method on the map instance."""
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

    def on_map_event(self, event_type: str, callback):
        """Register a callback for map events."""
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

    def set_center(self, lat: float, lng: float) -> None:
        """Set the map center."""
        self.center = [lat, lng]

    def set_zoom(self, zoom: float) -> None:
        """Set the map zoom level."""
        self.zoom = zoom

    def fly_to(self, lat: float, lng: float, zoom: Optional[float] = None) -> None:
        """Fly to a specific location."""
        options = {"center": [lat, lng]}
        if zoom is not None:
            options["zoom"] = zoom
        self.call_js_method("flyTo", options)

    def add_layer(self, layer_id: str, layer_config: Dict[str, Any]) -> None:
        """Add a layer to the map."""
        # Store layer in local state for persistence
        current_layers = dict(self._layers)
        current_layers[layer_id] = layer_config
        self._layers = current_layers

        self.call_js_method("addLayer", layer_config, layer_id)

    def remove_layer(self, layer_id: str) -> None:
        """Remove a layer from the map."""
        # Remove from local state
        current_layers = dict(self._layers)
        if layer_id in current_layers:
            del current_layers[layer_id]
            self._layers = current_layers

        self.call_js_method("removeLayer", layer_id)

    def add_source(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Add a data source to the map."""
        # Store source in local state for persistence
        current_sources = dict(self._sources)
        current_sources[source_id] = source_config
        self._sources = current_sources

        self.call_js_method("addSource", source_id, source_config)

    def remove_source(self, source_id: str) -> None:
        """Remove a data source from the map."""
        # Remove from local state
        current_sources = dict(self._sources)
        if source_id in current_sources:
            del current_sources[source_id]
            self._sources = current_sources

        self.call_js_method("removeSource", source_id)


class MapLibreMap(MapWidget):
    """MapLibre GL JS implementation of the map widget."""

    # MapLibre-specific traits
    map_style = traitlets.Unicode("https://demotiles.maplibre.org/style.json").tag(
        sync=True
    )
    bearing = traitlets.Float(0.0).tag(sync=True)
    pitch = traitlets.Float(0.0).tag(sync=True)
    antialias = traitlets.Bool(True).tag(sync=True)

    # Define the JavaScript module path
    _esm = pathlib.Path(__file__).parent / "static" / "maplibre_widget.js"
    _css = pathlib.Path(__file__).parent / "static" / "maplibre_widget.css"

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        map_style: str = "https://demotiles.maplibre.org/style.json",
        width: str = "100%",
        height: str = "600px",
        bearing: float = 0.0,
        pitch: float = 0.0,
        **kwargs,
    ):
        """Initialize MapLibre map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level
            map_style: MapLibre style URL or style object
            width: Widget width
            height: Widget height
            bearing: Map bearing (rotation) in degrees
            pitch: Map pitch (tilt) in degrees
        """
        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            map_style=map_style,
            bearing=bearing,
            pitch=pitch,
            **kwargs,
        )

    def set_style(self, style: Union[str, Dict[str, Any]]) -> None:
        """Set the map style."""
        if isinstance(style, str):
            self.map_style = style
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

    def get_layers(self) -> Dict[str, Dict[str, Any]]:
        """Get all layers currently on the map."""
        return dict(self._layers)

    def get_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get all sources currently on the map."""
        return dict(self._sources)

    def clear_layers(self) -> None:
        """Remove all layers from the map."""
        for layer_id in list(self._layers.keys()):
            self.remove_layer(layer_id)

    def clear_sources(self) -> None:
        """Remove all sources from the map."""
        for source_id in list(self._sources.keys()):
            self.remove_source(source_id)

    def clear_all(self) -> None:
        """Clear all layers and sources from the map."""
        self.clear_layers()
        self.clear_sources()

    def add_raster_layer(
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
            source_id, {"type": "raster", "url": source_url, "tileSize": 256}
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


class MapboxMap(MapWidget):
    """Mapbox GL JS implementation of the map widget."""

    # Mapbox-specific traits
    map_style = traitlets.Unicode("mapbox://styles/mapbox/streets-v12").tag(sync=True)
    bearing = traitlets.Float(0.0).tag(sync=True)
    pitch = traitlets.Float(0.0).tag(sync=True)
    antialias = traitlets.Bool(True).tag(sync=True)
    access_token = traitlets.Unicode("").tag(sync=True)

    # Define the JavaScript module path
    _esm = pathlib.Path(__file__).parent / "static" / "mapbox_widget.js"
    _css = pathlib.Path(__file__).parent / "static" / "mapbox_widget.css"

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        map_style: str = "mapbox://styles/mapbox/streets-v12",
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
            map_style: Mapbox style URL or style object
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
            map_style=map_style,
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
            self.map_style = style
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

    def get_layers(self) -> Dict[str, Dict[str, Any]]:
        """Get all layers currently on the map."""
        return dict(self._layers)

    def get_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get all sources currently on the map."""
        return dict(self._sources)

    def clear_layers(self) -> None:
        """Remove all layers from the map."""
        for layer_id in list(self._layers.keys()):
            self.remove_layer(layer_id)

    def clear_sources(self) -> None:
        """Remove all sources from the map."""
        for source_id in list(self._sources.keys()):
            self.remove_source(source_id)

    def clear_all(self) -> None:
        """Clear all layers and sources from the map."""
        self.clear_layers()
        self.clear_sources()

    def add_raster_layer(
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
            source_id, {"type": "raster", "url": source_url, "tileSize": 256}
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


class CesiumMap(MapWidget):
    """Cesium ion implementation of the map widget for 3D globe visualization."""

    # Cesium-specific traits
    access_token = traitlets.Unicode("").tag(sync=True)
    camera_height = traitlets.Float(10000000.0).tag(sync=True)  # 10M meters default
    heading = traitlets.Float(0.0).tag(sync=True)
    pitch = traitlets.Float(-90.0).tag(sync=True)  # Looking down
    roll = traitlets.Float(0.0).tag(sync=True)

    # Cesium viewer options
    base_layer_picker = traitlets.Bool(True).tag(sync=True)
    fullscreen_button = traitlets.Bool(True).tag(sync=True)
    vr_button = traitlets.Bool(False).tag(sync=True)
    geocoder = traitlets.Bool(True).tag(sync=True)
    home_button = traitlets.Bool(True).tag(sync=True)
    info_box = traitlets.Bool(True).tag(sync=True)
    scene_mode_picker = traitlets.Bool(True).tag(sync=True)
    selection_indicator = traitlets.Bool(True).tag(sync=True)
    timeline = traitlets.Bool(False).tag(sync=True)
    navigation_help_button = traitlets.Bool(False).tag(
        sync=True
    )  # Disabled by default to prevent arrows
    animation = traitlets.Bool(False).tag(sync=True)
    should_animate = traitlets.Bool(False).tag(sync=True)

    # Define the JavaScript module path
    _esm = pathlib.Path(__file__).parent / "static" / "cesium_widget.js"
    _css = pathlib.Path(__file__).parent / "static" / "cesium_widget.css"

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        width: str = "100%",
        height: str = "600px",
        camera_height: float = 10000000.0,
        heading: float = 0.0,
        pitch: float = -90.0,
        roll: float = 0.0,
        access_token: str = "",
        base_layer_picker: bool = True,
        fullscreen_button: bool = True,
        vr_button: bool = False,
        geocoder: bool = True,
        home_button: bool = True,
        info_box: bool = True,
        scene_mode_picker: bool = True,
        selection_indicator: bool = True,
        timeline: bool = False,
        navigation_help_button: bool = False,
        animation: bool = False,
        should_animate: bool = False,
        **kwargs,
    ):
        """Initialize Cesium map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level (used for camera height calculation)
            width: Widget width
            height: Widget height
            camera_height: Camera height above ground in meters
            heading: Camera heading in degrees (0 = north, 90 = east)
            pitch: Camera pitch in degrees (-90 = looking down, 0 = horizon)
            roll: Camera roll in degrees
            access_token: Cesium ion access token (required for Cesium services).
                         Get a free token at https://cesium.com/ion/signup
                         Can also be set via CESIUM_TOKEN environment variable.
            base_layer_picker: Show base layer picker widget
            fullscreen_button: Show fullscreen button
            vr_button: Show VR button
            geocoder: Show geocoder search widget
            home_button: Show home button
            info_box: Show info box when clicking entities
            scene_mode_picker: Show 3D/2D/Columbus view picker
            selection_indicator: Show selection indicator
            timeline: Show timeline widget
            navigation_help_button: Show navigation help button
            animation: Show animation widget
            should_animate: Enable automatic animation
        """
        # Set default access token if not provided
        if not access_token:
            access_token = self._get_default_access_token()

        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            camera_height=camera_height,
            heading=heading,
            pitch=pitch,
            roll=roll,
            access_token=access_token,
            base_layer_picker=base_layer_picker,
            fullscreen_button=fullscreen_button,
            vr_button=vr_button,
            geocoder=geocoder,
            home_button=home_button,
            info_box=info_box,
            scene_mode_picker=scene_mode_picker,
            selection_indicator=selection_indicator,
            timeline=timeline,
            navigation_help_button=navigation_help_button,
            animation=animation,
            should_animate=should_animate,
            **kwargs,
        )

    @staticmethod
    def _get_default_access_token() -> str:
        """Get default Cesium access token from environment."""
        import os

        # Try to get from environment variable
        token = os.environ.get("CESIUM_TOKEN") or os.environ.get("CESIUM_ACCESS_TOKEN")

        # If no token found, return empty string - user must provide their own token
        if not token:
            import warnings

            warnings.warn(
                "No Cesium access token found. Please set CESIUM_TOKEN environment variable "
                "or pass access_token parameter. Get a free token at https://cesium.com/ion/signup",
                UserWarning,
            )
            token = ""

        return token

    def set_access_token(self, token: str) -> None:
        """Set the Cesium ion access token."""
        self.access_token = token

    def fly_to(
        self,
        latitude: float,
        longitude: float,
        height: Optional[float] = None,
        heading: Optional[float] = None,
        pitch: Optional[float] = None,
        roll: Optional[float] = None,
        duration: float = 3.0,
    ) -> None:
        """Fly the camera to a specific location."""
        options = {"latitude": latitude, "longitude": longitude, "duration": duration}
        if height is not None:
            options["height"] = height
        if heading is not None:
            options["heading"] = heading
        if pitch is not None:
            options["pitch"] = pitch
        if roll is not None:
            options["roll"] = roll

        self.call_js_method("flyTo", options)

    def set_camera_position(
        self,
        latitude: float,
        longitude: float,
        height: float,
        heading: float = 0.0,
        pitch: float = -90.0,
        roll: float = 0.0,
    ) -> None:
        """Set camera position immediately."""
        self.center = [latitude, longitude]
        self.camera_height = height
        self.heading = heading
        self.pitch = pitch
        self.roll = roll

    def add_entity(self, entity_config: Dict[str, Any]) -> None:
        """Add an entity to the globe."""
        self.call_js_method("addEntity", entity_config)

    def remove_entity(self, entity_id: str) -> None:
        """Remove an entity from the globe."""
        self.call_js_method("removeEntity", entity_id)

    def add_point(
        self,
        latitude: float,
        longitude: float,
        height: float = 0.0,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: str = "#ffff00",
        pixel_size: int = 10,
        entity_id: Optional[str] = None,
    ) -> str:
        """Add a point to the globe."""
        if entity_id is None:
            entity_id = f"point_{len(self._layers)}"

        entity_config = {
            "id": entity_id,
            "position": {
                "longitude": longitude,
                "latitude": latitude,
                "height": height,
            },
            "point": {
                "pixelSize": pixel_size,
                "color": color,
                "outlineColor": "#000000",
                "outlineWidth": 2,
                "heightReference": "CLAMP_TO_GROUND" if height == 0 else "NONE",
            },
        }

        if name:
            entity_config["name"] = name
        if description:
            entity_config["description"] = description

        self.add_entity(entity_config)
        return entity_id

    def add_billboard(
        self,
        latitude: float,
        longitude: float,
        image_url: str,
        height: float = 0.0,
        scale: float = 1.0,
        name: Optional[str] = None,
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> str:
        """Add a billboard (image marker) to the globe."""
        if entity_id is None:
            entity_id = f"billboard_{len(self._layers)}"

        entity_config = {
            "id": entity_id,
            "position": {
                "longitude": longitude,
                "latitude": latitude,
                "height": height,
            },
            "billboard": {
                "image": image_url,
                "scale": scale,
                "heightReference": "CLAMP_TO_GROUND" if height == 0 else "NONE",
            },
        }

        if name:
            entity_config["name"] = name
        if description:
            entity_config["description"] = description

        self.add_entity(entity_config)
        return entity_id

    def add_polyline(
        self,
        coordinates: List[List[float]],
        color: str = "#ff0000",
        width: int = 2,
        clamp_to_ground: bool = True,
        name: Optional[str] = None,
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> str:
        """Add a polyline to the globe."""
        if entity_id is None:
            entity_id = f"polyline_{len(self._layers)}"

        # Convert coordinates to Cesium format
        positions = []
        for coord in coordinates:
            if len(coord) >= 2:
                positions.extend(
                    [coord[1], coord[0], coord[2] if len(coord) > 2 else 0]
                )

        entity_config = {
            "id": entity_id,
            "polyline": {
                "positions": positions,
                "width": width,
                "material": color,
                "clampToGround": clamp_to_ground,
            },
        }

        if name:
            entity_config["name"] = name
        if description:
            entity_config["description"] = description

        self.add_entity(entity_config)
        return entity_id

    def add_polygon(
        self,
        coordinates: List[List[float]],
        color: str = "#0000ff",
        outline_color: str = "#000000",
        height: float = 0.0,
        extrude_height: Optional[float] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> str:
        """Add a polygon to the globe."""
        if entity_id is None:
            entity_id = f"polygon_{len(self._layers)}"

        # Convert coordinates to Cesium format
        positions = []
        for coord in coordinates:
            if len(coord) >= 2:
                positions.extend([coord[1], coord[0]])

        entity_config = {
            "id": entity_id,
            "polygon": {
                "hierarchy": positions,
                "material": color,
                "outline": True,
                "outlineColor": outline_color,
                "height": height,
            },
        }

        if extrude_height is not None:
            entity_config["polygon"]["extrudedHeight"] = extrude_height

        if name:
            entity_config["name"] = name
        if description:
            entity_config["description"] = description

        self.add_entity(entity_config)
        return entity_id

    def add_data_source(
        self,
        source_type: str,
        data: Union[str, Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a data source (GeoJSON, KML, CZML) to the globe."""
        config = {"data": data, "options": options or {}}
        self.call_js_method("addDataSource", source_type, config)

    def add_geojson(
        self, geojson_data: Dict[str, Any], options: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add GeoJSON data to the globe."""
        self.add_data_source("geojson", geojson_data, options)

    def add_kml(self, kml_url: str, options: Optional[Dict[str, Any]] = None) -> None:
        """Add KML data to the globe."""
        self.add_data_source("kml", kml_url, options)

    def add_czml(
        self, czml_data: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add CZML data to the globe."""
        self.add_data_source("czml", czml_data, options)

    def set_terrain(self, terrain_config: Optional[Dict[str, Any]] = None) -> None:
        """Set terrain provider for the globe."""
        self.call_js_method("setTerrain", terrain_config)

    def set_cesium_world_terrain(
        self, request_water_mask: bool = False, request_vertex_normals: bool = False
    ) -> None:
        """Set Cesium World Terrain as the terrain provider."""
        terrain_config = {
            "type": "cesium-world-terrain",
            "requestWaterMask": request_water_mask,
            "requestVertexNormals": request_vertex_normals,
        }
        self.set_terrain(terrain_config)

    def set_imagery(self, imagery_config: Dict[str, Any]) -> None:
        """Set imagery provider for the globe."""
        self.call_js_method("setImagery", imagery_config)

    def set_scene_mode_3d(self) -> None:
        """Set scene to 3D mode."""
        self.call_js_method("setScene3D")

    def set_scene_mode_2d(self) -> None:
        """Set scene to 2D mode."""
        self.call_js_method("setScene2D")

    def set_scene_mode_columbus(self) -> None:
        """Set scene to Columbus view (2.5D)."""
        self.call_js_method("setSceneColumbusView")

    def enable_lighting(self, enabled: bool = True) -> None:
        """Enable or disable globe lighting effects."""
        self.call_js_method("enableLighting", enabled)

    def enable_fog(self, enabled: bool = True) -> None:
        """Enable or disable atmospheric fog."""
        self.call_js_method("enableFog", enabled)

    def zoom_to_entity(self, entity_id: str) -> None:
        """Zoom the camera to focus on a specific entity."""
        self.call_js_method("zoomToEntity", entity_id)

    def home(self) -> None:
        """Reset camera to home position."""
        self.call_js_method("home")

    def get_layers(self) -> Dict[str, Dict[str, Any]]:
        """Get all layers currently on the map."""
        return dict(self._layers)

    def get_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get all sources currently on the map."""
        return dict(self._sources)

    def clear_entities(self) -> None:
        """Clear all entities from the globe."""
        # This would require tracking entities, for now use clear_layers
        self.clear_layers()

    def clear_layers(self) -> None:
        """Remove all layers from the map."""
        for layer_id in list(self._layers.keys()):
            self.remove_layer(layer_id)

    def clear_sources(self) -> None:
        """Remove all sources from the map."""
        for source_id in list(self._sources.keys()):
            self.remove_source(source_id)

    def clear_all(self) -> None:
        """Clear all layers and sources from the map."""
        self.clear_layers()
        self.clear_sources()
