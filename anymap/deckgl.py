"""DeckGL implementation of the map widget for high-performance data visualization."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union

from .base import MapWidget

# Load DeckGL-specific js and css
with open(pathlib.Path(__file__).parent / "static" / "deck_widget.js", "r") as f:
    _esm_deck = f.read()

with open(pathlib.Path(__file__).parent / "static" / "deck_widget.css", "r") as f:
    _css_deck = f.read()


class DeckGLMap(MapWidget):
    """DeckGL implementation of the map widget for high-performance data visualization."""

    # DeckGL-specific traits
    controller = traitlets.Bool(True).tag(sync=True)
    bearing = traitlets.Float(0.0).tag(sync=True)
    pitch = traitlets.Float(0.0).tag(sync=True)
    max_zoom = traitlets.Float(20.0).tag(sync=True)
    min_zoom = traitlets.Float(0.0).tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_deck
    _css = _css_deck

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        width: str = "100%",
        height: str = "600px",
        bearing: float = 0.0,
        pitch: float = 0.0,
        controller: bool = True,
        max_zoom: float = 20.0,
        min_zoom: float = 0.0,
        **kwargs,
    ):
        """Initialize DeckGL map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level
            width: Widget width
            height: Widget height
            bearing: Map bearing (rotation) in degrees
            pitch: Map pitch (tilt) in degrees
            controller: Enable map controls (pan, zoom, rotate)
            max_zoom: Maximum zoom level
            min_zoom: Minimum zoom level
        """
        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            bearing=bearing,
            pitch=pitch,
            controller=controller,
            max_zoom=max_zoom,
            min_zoom=min_zoom,
            **kwargs,
        )

    def set_bearing(self, bearing: float) -> None:
        """Set the map bearing (rotation)."""
        self.bearing = bearing

    def set_pitch(self, pitch: float) -> None:
        """Set the map pitch (tilt)."""
        self.pitch = pitch

    def set_view_state(
        self,
        longitude: Optional[float] = None,
        latitude: Optional[float] = None,
        zoom: Optional[float] = None,
        bearing: Optional[float] = None,
        pitch: Optional[float] = None,
    ) -> None:
        """Set the view state of the map."""
        view_state = {}
        if longitude is not None:
            view_state["longitude"] = longitude
        if latitude is not None:
            view_state["latitude"] = latitude
        if zoom is not None:
            view_state["zoom"] = zoom
        if bearing is not None:
            view_state["bearing"] = bearing
        if pitch is not None:
            view_state["pitch"] = pitch

        self.call_js_method("setViewState", view_state)

    def add_scatterplot_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_radius: Union[str, int, float] = 100,
        get_color: Union[str, List[int]] = [255, 0, 0, 255],
        radius_scale: float = 1.0,
        radius_min_pixels: int = 1,
        radius_max_pixels: int = 100,
        **kwargs,
    ) -> None:
        """Add a scatterplot layer to the map."""
        layer_config = {
            "type": "ScatterplotLayer",
            "data": data,
            "getPosition": get_position,
            "getRadius": get_radius,
            "getFillColor": get_color,
            "radiusScale": radius_scale,
            "radiusMinPixels": radius_min_pixels,
            "radiusMaxPixels": radius_max_pixels,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_line_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_source_position: str = "sourcePosition",
        get_target_position: str = "targetPosition",
        get_color: Union[str, List[int]] = [0, 255, 0, 255],
        get_width: Union[str, int, float] = 1,
        width_scale: float = 1.0,
        width_min_pixels: int = 1,
        width_max_pixels: int = 10,
        **kwargs,
    ) -> None:
        """Add a line layer to the map."""
        layer_config = {
            "type": "LineLayer",
            "data": data,
            "getSourcePosition": get_source_position,
            "getTargetPosition": get_target_position,
            "getColor": get_color,
            "getWidth": get_width,
            "widthScale": width_scale,
            "widthMinPixels": width_min_pixels,
            "widthMaxPixels": width_max_pixels,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_arc_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_source_position: str = "sourcePosition",
        get_target_position: str = "targetPosition",
        get_source_color: Union[str, List[int]] = [255, 0, 0, 255],
        get_target_color: Union[str, List[int]] = [0, 255, 0, 255],
        get_width: Union[str, int, float] = 1,
        width_scale: float = 1.0,
        width_min_pixels: int = 1,
        width_max_pixels: int = 10,
        **kwargs,
    ) -> None:
        """Add an arc layer to the map."""
        layer_config = {
            "type": "ArcLayer",
            "data": data,
            "getSourcePosition": get_source_position,
            "getTargetPosition": get_target_position,
            "getSourceColor": get_source_color,
            "getTargetColor": get_target_color,
            "getWidth": get_width,
            "widthScale": width_scale,
            "widthMinPixels": width_min_pixels,
            "widthMaxPixels": width_max_pixels,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_path_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_path: str = "path",
        get_color: Union[str, List[int]] = [255, 0, 0, 255],
        get_width: Union[str, int, float] = 1,
        width_scale: float = 1.0,
        width_min_pixels: int = 1,
        width_max_pixels: int = 10,
        **kwargs,
    ) -> None:
        """Add a path layer to the map."""
        layer_config = {
            "type": "PathLayer",
            "data": data,
            "getPath": get_path,
            "getColor": get_color,
            "getWidth": get_width,
            "widthScale": width_scale,
            "widthMinPixels": width_min_pixels,
            "widthMaxPixels": width_max_pixels,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_polygon_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_polygon: str = "polygon",
        get_fill_color: Union[str, List[int]] = [255, 0, 0, 128],
        get_line_color: Union[str, List[int]] = [0, 0, 0, 255],
        get_line_width: Union[str, int, float] = 1,
        filled: bool = True,
        stroked: bool = True,
        **kwargs,
    ) -> None:
        """Add a polygon layer to the map."""
        layer_config = {
            "type": "PolygonLayer",
            "data": data,
            "getPolygon": get_polygon,
            "getFillColor": get_fill_color,
            "getLineColor": get_line_color,
            "getLineWidth": get_line_width,
            "filled": filled,
            "stroked": stroked,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_geojson_layer(
        self,
        layer_id: str,
        data: Dict[str, Any],
        get_fill_color: Union[str, List[int]] = [255, 0, 0, 128],
        get_line_color: Union[str, List[int]] = [0, 0, 0, 255],
        get_line_width: Union[str, int, float] = 1,
        get_radius: Union[str, int, float] = 100,
        filled: bool = True,
        stroked: bool = True,
        **kwargs,
    ) -> None:
        """Add a GeoJSON layer to the map."""
        layer_config = {
            "type": "GeoJsonLayer",
            "data": data,
            "getFillColor": get_fill_color,
            "getLineColor": get_line_color,
            "getLineWidth": get_line_width,
            "getRadius": get_radius,
            "filled": filled,
            "stroked": stroked,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_hexagon_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_weight: Union[str, int, float] = 1,
        radius: int = 1000,
        elevation_scale: float = 4,
        elevation_range: List[int] = [0, 1000],
        coverage: float = 1.0,
        color_range: Optional[List[List[int]]] = None,
        **kwargs,
    ) -> None:
        """Add a hexagon layer to the map."""
        if color_range is None:
            color_range = [
                [1, 152, 189],
                [73, 227, 206],
                [216, 254, 181],
                [254, 237, 177],
                [254, 173, 84],
                [209, 55, 78],
            ]

        layer_config = {
            "type": "HexagonLayer",
            "data": data,
            "getPosition": get_position,
            "getWeight": get_weight,
            "radius": radius,
            "elevationScale": elevation_scale,
            "elevationRange": elevation_range,
            "coverage": coverage,
            "colorRange": color_range,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_grid_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_weight: Union[str, int, float] = 1,
        cell_size: int = 200,
        elevation_scale: float = 4,
        elevation_range: List[int] = [0, 1000],
        coverage: float = 1.0,
        color_range: Optional[List[List[int]]] = None,
        **kwargs,
    ) -> None:
        """Add a grid layer to the map."""
        if color_range is None:
            color_range = [
                [1, 152, 189],
                [73, 227, 206],
                [216, 254, 181],
                [254, 237, 177],
                [254, 173, 84],
                [209, 55, 78],
            ]

        layer_config = {
            "type": "GridLayer",
            "data": data,
            "getPosition": get_position,
            "getWeight": get_weight,
            "cellSize": cell_size,
            "elevationScale": elevation_scale,
            "elevationRange": elevation_range,
            "coverage": coverage,
            "colorRange": color_range,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_heatmap_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_weight: Union[str, int, float] = 1,
        radius_pixels: int = 60,
        intensity: float = 1.0,
        threshold: float = 0.05,
        color_range: Optional[List[List[int]]] = None,
        **kwargs,
    ) -> None:
        """Add a heatmap layer to the map."""
        if color_range is None:
            color_range = [
                [255, 255, 178],
                [254, 204, 92],
                [253, 141, 60],
                [240, 59, 32],
                [189, 0, 38],
            ]

        layer_config = {
            "type": "HeatmapLayer",
            "data": data,
            "getPosition": get_position,
            "getWeight": get_weight,
            "radiusPixels": radius_pixels,
            "intensity": intensity,
            "threshold": threshold,
            "colorRange": color_range,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_column_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_elevation: Union[str, int, float] = 0,
        get_fill_color: Union[str, List[int]] = [255, 0, 0, 255],
        get_line_color: Union[str, List[int]] = [0, 0, 0, 255],
        radius: int = 1000,
        elevation_scale: float = 1.0,
        filled: bool = True,
        stroked: bool = False,
        **kwargs,
    ) -> None:
        """Add a column layer to the map."""
        layer_config = {
            "type": "ColumnLayer",
            "data": data,
            "getPosition": get_position,
            "getElevation": get_elevation,
            "getFillColor": get_fill_color,
            "getLineColor": get_line_color,
            "radius": radius,
            "elevationScale": elevation_scale,
            "filled": filled,
            "stroked": stroked,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_text_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_text: str = "text",
        get_color: Union[str, List[int]] = [0, 0, 0, 255],
        get_size: Union[str, int, float] = 32,
        get_angle: Union[str, int, float] = 0,
        font_family: str = "Monaco, monospace",
        **kwargs,
    ) -> None:
        """Add a text layer to the map."""
        layer_config = {
            "type": "TextLayer",
            "data": data,
            "getPosition": get_position,
            "getText": get_text,
            "getColor": get_color,
            "getSize": get_size,
            "getAngle": get_angle,
            "fontFamily": font_family,
            **kwargs,
        }
        self.add_layer(layer_id, layer_config)

    def add_icon_layer(
        self,
        layer_id: str,
        data: List[Dict[str, Any]],
        get_position: str = "position",
        get_icon: str = "icon",
        get_color: Union[str, List[int]] = [255, 255, 255, 255],
        get_size: Union[str, int, float] = 1,
        size_scale: float = 1.0,
        icon_atlas: Optional[str] = None,
        icon_mapping: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Add an icon layer to the map."""
        layer_config = {
            "type": "IconLayer",
            "data": data,
            "getPosition": get_position,
            "getIcon": get_icon,
            "getColor": get_color,
            "getSize": get_size,
            "sizeScale": size_scale,
            **kwargs,
        }

        if icon_atlas:
            layer_config["iconAtlas"] = icon_atlas
        if icon_mapping:
            layer_config["iconMapping"] = icon_mapping

        self.add_layer(layer_id, layer_config)

    def update_layer(self, layer_id: str, **props) -> None:
        """Update properties of an existing layer."""
        self.call_js_method("updateLayer", layer_id, props)

    def fit_bounds(
        self,
        bounds: List[List[float]],
        padding: Union[int, Dict[str, int]] = 20,
        max_zoom: Optional[float] = None,
    ) -> None:
        """Fit the map to given bounds.

        Args:
            bounds: Bounds in format [[minLng, minLat], [maxLng, maxLat]]
            padding: Padding around bounds in pixels
            max_zoom: Maximum zoom level when fitting
        """
        options = {"padding": padding}
        if max_zoom is not None:
            options["maxZoom"] = max_zoom

        self.call_js_method("fitBounds", bounds, options)

    def clear_layers(self) -> None:
        """Remove all layers from the map."""
        for layer_id in list(self._layers.keys()):
            self.remove_layer(layer_id)

    def clear_all(self) -> None:
        """Clear all layers from the map."""
        self.clear_layers()

    def enable_controller(self, enabled: bool = True) -> None:
        """Enable or disable map controls."""
        self.controller = enabled

    def set_zoom_range(self, min_zoom: float, max_zoom: float) -> None:
        """Set the zoom range for the map."""
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
