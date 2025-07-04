"""Cesium ion implementation of the map widget for 3D globe visualization."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union

from .base import MapWidget

# Load Cesium-specific js and css
with open(pathlib.Path(__file__).parent / "static" / "cesium_widget.js", "r") as f:
    _esm_cesium = f.read()

with open(pathlib.Path(__file__).parent / "static" / "cesium_widget.css", "r") as f:
    _css_cesium = f.read()


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
    _esm = _esm_cesium
    _css = _css_cesium

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
