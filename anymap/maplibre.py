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

import json
import os
import pathlib
import requests
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import geopandas as gpd
import ipyvuetify as v
import ipywidgets as widgets
import pandas as pd
import traitlets
from IPython.display import display

from .base import MapWidget
from .utils import construct_maplibre_style

# Load MapLibre-specific js and css
with open(
    pathlib.Path(__file__).parent / "static" / "maplibre_widget.js",
    "r",
    encoding="utf-8",
) as f:
    _esm_maplibre = f.read()

with open(
    pathlib.Path(__file__).parent / "static" / "maplibre_widget.css",
    "r",
    encoding="utf-8",
) as f:
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
    _draw_data = traitlets.Dict().tag(sync=True)
    _terra_draw_data = traitlets.Dict().tag(sync=True)
    _terra_draw_enabled = traitlets.Bool(False).tag(sync=True)
    _layer_dict = traitlets.Dict().tag(sync=True)

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
        controls: Dict[str, str] = {
            "navigation": "top-right",
            "fullscreen": "top-right",
            "scale": "bottom-left",
            "globe": "top-right",
        },
        projection: str = "mercator",
        add_sidebar: bool = True,
        sidebar_visible: bool = False,
        sidebar_width: int = 360,
        sidebar_args: Optional[Dict] = None,
        layer_manager_expanded: bool = True,
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

        self.controls = {}
        for control, position in controls.items():
            self.add_control(control, position)
            self.controls[control] = position

        self.layer_dict = {}
        self.layer_dict["Background"] = {
            "layer": {
                "id": "Background",
                "type": "background",
            },
            "opacity": 1.0,
            "visible": True,
            "type": "background",
            "color": None,
        }

        # Initialize the _layer_dict trait with the layer_dict content
        self._layer_dict = dict(self.layer_dict)

        self._style = style
        self.style_dict = {}
        for layer in self.get_style_layers():
            self.style_dict[layer["id"]] = layer
        self.source_dict = {}

        if projection.lower() == "globe":
            self.set_projection(
                {
                    "type": [
                        "interpolate",
                        ["linear"],
                        ["zoom"],
                        10,
                        "vertical-perspective",
                        12,
                        "mercator",
                    ]
                }
            )

        if sidebar_args is None:
            sidebar_args = {}
        if "sidebar_visible" not in sidebar_args:
            sidebar_args["sidebar_visible"] = sidebar_visible
        if "sidebar_width" not in sidebar_args:
            if isinstance(sidebar_width, str):
                sidebar_width = int(sidebar_width.replace("px", ""))
            sidebar_args["min_width"] = sidebar_width
            sidebar_args["max_width"] = sidebar_width
        if "expanded" not in sidebar_args:
            sidebar_args["expanded"] = layer_manager_expanded
        self.sidebar_args = sidebar_args
        self.layer_manager = None
        self.container = None
        if add_sidebar:
            self._ipython_display_ = self._patched_display

    def show(
        self,
        sidebar_visible: bool = False,
        min_width: int = 360,
        max_width: int = 360,
        sidebar_content: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Displays the map with an optional sidebar.

        Args:
            sidebar_visible (bool): Whether the sidebar is visible. Defaults to False.
            min_width (int): Minimum width of the sidebar in pixels. Defaults to 250.
            max_width (int): Maximum width of the sidebar in pixels. Defaults to 300.
            sidebar_content (Optional[Any]): Content to display in the sidebar. Defaults to None.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            None
        """
        return Container(
            self,
            sidebar_visible=sidebar_visible,
            min_width=min_width,
            max_width=max_width,
            sidebar_content=sidebar_content,
            **kwargs,
        )

    def create_container(
        self,
        sidebar_visible: bool = None,
        min_width: int = None,
        max_width: int = None,
        expanded: bool = None,
        **kwargs: Any,
    ):
        """
        Creates a container widget for the map with an optional sidebar.

        This method initializes a `LayerManagerWidget` and a `Container` widget to display the map
        alongside a sidebar. The sidebar can be customized with visibility, width, and additional content.

        Args:
            sidebar_visible (bool): Whether the sidebar is visible. Defaults to False.
            min_width (int): Minimum width of the sidebar in pixels. Defaults to 360.
            max_width (int): Maximum width of the sidebar in pixels. Defaults to 360.
            expanded (bool): Whether the `LayerManagerWidget` is expanded by default. Defaults to True.
            **kwargs (Any): Additional keyword arguments passed to the `Container` widget.

        Returns:
            Container: The created container widget with the map and sidebar.
        """

        if sidebar_visible is None:
            sidebar_visible = self.sidebar_args.get("sidebar_visible", False)
        if min_width is None:
            min_width = self.sidebar_args.get("min_width", 360)
        if max_width is None:
            max_width = self.sidebar_args.get("max_width", 360)
        if expanded is None:
            expanded = self.sidebar_args.get("expanded", True)
        if self.layer_manager is None:
            self.layer_manager = LayerManagerWidget(self, expanded=expanded)

        container = Container(
            host_map=self,
            sidebar_visible=sidebar_visible,
            min_width=min_width,
            max_width=max_width,
            sidebar_content=[self.layer_manager],
            **kwargs,
        )
        self.container = container
        self.container.sidebar_widgets["Layers"] = self.layer_manager
        return container

    def _repr_html_(self, **kwargs: Any) -> None:
        """
        Displays the map in an IPython environment.

        Args:
            **kwargs (Any): Additional keyword arguments.

        Returns:
            None
        """

        filename = os.environ.get("MAPLIBRE_OUTPUT", None)
        replace_key = os.environ.get("MAPTILER_REPLACE_KEY", False)
        if filename is not None:
            self.to_html(filename, replace_key=replace_key)

    def _patched_display(
        self,
        **kwargs: Any,
    ) -> None:
        """
        Displays the map in an IPython environment with a patched display method.

        Args:
            **kwargs (Any): Additional keyword arguments.

        Returns:
            None
        """

        if self.container is not None:
            container = self.container
        else:
            sidebar_visible = self.sidebar_args.get("sidebar_visible", False)
            min_width = self.sidebar_args.get("min_width", 360)
            max_width = self.sidebar_args.get("max_width", 360)
            expanded = self.sidebar_args.get("expanded", True)
            if self.layer_manager is None:
                self.layer_manager = LayerManagerWidget(self, expanded=expanded)
            container = Container(
                host_map=self,
                sidebar_visible=sidebar_visible,
                min_width=min_width,
                max_width=max_width,
                sidebar_content=[self.layer_manager],
                **kwargs,
            )
            container.sidebar_widgets["Layers"] = self.layer_manager
            self.container = container

        if "google.colab" in sys.modules:
            import ipyvue as vue

            display(vue.Html(children=[]), container)
        else:
            display(container)

    def add_layer_manager(
        self,
        expanded: bool = True,
        height: str = "40px",
        layer_icon: str = "mdi-layers",
        close_icon: str = "mdi-close",
        label="Layers",
        background_color: str = "#f5f5f5",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self.layer_manager is None:
            self.layer_manager = LayerManagerWidget(
                self,
                expanded=expanded,
                height=height,
                layer_icon=layer_icon,
                close_icon=close_icon,
                label=label,
                background_color=background_color,
                *args,
                **kwargs,
            )

    def set_sidebar_content(
        self, content: Union[widgets.VBox, List[widgets.Widget]]
    ) -> None:
        """
        Replaces all content in the sidebar (except the toggle button).

        Args:
            content (Union[widgets.VBox, List[widgets.Widget]]): The new content for the sidebar.
        """

        if self.container is not None:
            self.container.set_sidebar_content(content)

    def add_to_sidebar(
        self,
        widget: widgets.Widget,
        add_header: bool = True,
        widget_icon: str = "mdi-tools",
        close_icon: str = "mdi-close",
        label: str = "My Tools",
        background_color: str = "#f5f5f5",
        height: str = "40px",
        expanded: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Appends a widget to the sidebar content.

        Args:
            widget (Optional[Union[widgets.Widget, List[widgets.Widget]]]): Initial widget(s) to display in the content box.
            widget_icon (str): Icon for the header. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            close_icon (str): Icon for the close button. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            background_color (str): Background color of the header. Defaults to "#f5f5f5".
            label (str): Text label for the header. Defaults to "My Tools".
            height (str): Height of the header. Defaults to "40px".
            expanded (bool): Whether the panel is expanded by default. Defaults to True.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        if self.container is None:
            self.create_container(**self.sidebar_args)
        self.container.add_to_sidebar(
            widget,
            add_header=add_header,
            widget_icon=widget_icon,
            close_icon=close_icon,
            label=label,
            background_color=background_color,
            height=height,
            expanded=expanded,
            host_map=self,
            **kwargs,
        )

    def remove_from_sidebar(
        self, widget: widgets.Widget = None, name: str = None
    ) -> None:
        """
        Removes a widget from the sidebar content.

        Args:
            widget (widgets.Widget): The widget to remove from the sidebar.
            name (str): The name of the widget to remove from the sidebar.
        """
        if self.container is not None:
            self.container.remove_from_sidebar(widget, name)

    def set_sidebar_width(self, min_width: int = None, max_width: int = None) -> None:
        """
        Dynamically updates the sidebar's minimum and maximum width.

        Args:
            min_width (int, optional): New minimum width in pixels. If None, keep current.
            max_width (int, optional): New maximum width in pixels. If None, keep current.
        """
        if self.container is None:
            self.create_container()
        self.container.set_sidebar_width(min_width, max_width)

    @property
    def sidebar_widgets(self) -> Dict[str, widgets.Widget]:
        """
        Returns a dictionary of widgets currently in the sidebar.

        Returns:
            Dict[str, widgets.Widget]: A dictionary where keys are the labels of the widgets and values are the widgets themselves.
        """
        return self.container.sidebar_widgets

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

    def set_visibility(self, layer_id: str, visible: bool) -> None:
        """Set the visibility of a layer.

        Args:
            layer_id: Unique identifier of the layer.
            visible: Whether the layer should be visible.
        """
        if visible:
            visibility = "visible"
        else:
            visibility = "none"

        if layer_id == "Background":
            for layer in self.get_style_layers():
                self.set_layout_property(layer["id"], "visibility", visibility)
        else:
            self.set_layout_property(layer_id, "visibility", visibility)
        if layer_id in self.layer_dict:
            self.layer_dict[layer_id]["visible"] = visible
            self._update_layer_controls()

    def set_opacity(self, layer_id: str, opacity: float) -> None:
        """Set the opacity of a layer.

        Args:
            layer_id: Unique identifier of the layer.
            opacity: Opacity value between 0.0 (transparent) and 1.0 (opaque).
        """
        layer_type = self.get_layer_type(layer_id)

        if layer_id == "Background":
            for layer in self.get_style_layers():
                layer_type = layer.get("type")
                if layer_type != "symbol":
                    self.set_paint_property(
                        layer["id"], f"{layer_type}-opacity", opacity
                    )
                else:
                    self.set_paint_property(layer["id"], "icon-opacity", opacity)
                    self.set_paint_property(layer["id"], "text-opacity", opacity)
            return

        if layer_id in self.layer_dict:
            layer_type = self.layer_dict[layer_id]["layer"]["type"]
            prop_name = f"{layer_type}-opacity"
            self.layer_dict[layer_id]["opacity"] = opacity
            self._update_layer_controls()
        elif layer_id in self.style_dict:
            layer = self.style_dict[layer_id]
            layer_type = layer.get("type")
            prop_name = f"{layer_type}-opacity"
            if "paint" in layer:
                layer["paint"][prop_name] = opacity

        if layer_type != "symbol":
            self.set_paint_property(layer_id, f"{layer_type}-opacity", opacity)
        else:
            self.set_paint_property(layer_id, "icon-opacity", opacity)
            self.set_paint_property(layer_id, "text-opacity", opacity)

    def set_projection(self, projection: Dict[str, Any]) -> None:
        """Set the map projection.

        Args:
            projection: Projection configuration dictionary.
        """
        # Store projection in persistent state
        self._projection = projection
        self.call_js_method("setProjection", projection)

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

    def get_style(self):
        """
        Get the style of the map.

        Returns:
            Dict: The style of the map.
        """
        if self._style is not None:
            if isinstance(self._style, str):
                response = requests.get(self._style, timeout=10)
                style = response.json()
            elif isinstance(self._style, dict):
                style = self._style
            else:
                style = {}
            return style
        else:
            return {}

    def get_style_layers(self, return_ids=False, sorted=True) -> List[str]:
        """
        Get the names of the basemap layers.

        Returns:
            List[str]: The names of the basemap layers.
        """
        style = self.get_style()
        if "layers" in style:
            layers = style["layers"]
            if return_ids:
                ids = [layer["id"] for layer in layers]
                if sorted:
                    ids.sort()

                return ids
            else:
                return layers
        else:
            return []

    def add_layer(
        self,
        layer_id: str,
        layer: Dict[str, Any],
        before_id: Optional[str] = None,
        opacity: Optional[float] = 1.0,
        visible: Optional[bool] = True,
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
        current_layers[layer_id] = layer
        self._layers = current_layers

        # Call JavaScript method with before_id if provided
        if before_id:
            self.call_js_method("addLayer", layer, before_id)
        else:
            self.call_js_method("addLayer", layer, layer_id)

        self.set_visibility(layer_id, visible)
        self.set_opacity(layer_id, opacity)
        self.layer_dict[layer_id] = {
            "layer": layer,
            "opacity": opacity,
            "visible": visible,
            "type": layer["type"],
            # "color": color,
        }

        # Update the _layer_dict trait to trigger JavaScript sync
        self._layer_dict = dict(self.layer_dict)

        if self.layer_manager is not None:
            self.layer_manager.refresh()

        # Update layer controls if they exist
        self._update_layer_controls()

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

    def add_control(
        self,
        control_type: str,
        position: str = "top-right",
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a control to the map.

        Args:
            control_type: Type of control ('navigation', 'scale', 'fullscreen', 'geolocate', 'attribution', 'globe')
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            options: Additional options for the control
        """
        control_options = options or {}
        control_options["position"] = position

        # Store control in persistent state
        control_key = f"{control_type}_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": control_type,
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self.call_js_method("addControl", control_type, control_options)

    def remove_control(
        self,
        control_type: str,
        position: str = "top-right",
    ) -> None:
        """Remove a control from the map.

        Args:
            control_type: Type of control to remove ('navigation', 'scale', 'fullscreen', 'geolocate', 'attribution', 'globe')
            position: Position where the control was added ('top-left', 'top-right', 'bottom-left', 'bottom-right')
        """
        # Remove control from persistent state
        control_key = f"{control_type}_{position}"
        current_controls = dict(self._controls)
        if control_key in current_controls:
            del current_controls[control_key]
            self._controls = current_controls

        self.call_js_method("removeControl", control_type, position)

    def add_layer_control(
        self,
        position: str = "top-right",
        collapsed: bool = True,
        layers: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a collapsible layer control panel to the map.

        The layer control is a collapsible panel that allows users to toggle
        visibility and adjust opacity of map layers. It displays as an icon
        similar to other controls, and expands when clicked.

        Args:
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            collapsed: Whether the control starts collapsed
            layers: List of layer IDs to include. If None, includes all layers
            options: Additional options for the control
        """
        control_options = options or {}
        control_options.update(
            {
                "position": position,
                "collapsed": collapsed,
                "layers": layers,
            }
        )

        # Get current layer states for initialization
        layer_states = {}
        target_layers = layers if layers is not None else list(self.layer_dict.keys())

        # Always include Background layer for controlling map style layers
        if layers is None or "Background" in layers:
            layer_states["Background"] = {
                "visible": True,
                "opacity": 1.0,
                "name": "Background",
            }

        for layer_id in target_layers:
            if layer_id in self.layer_dict and layer_id != "Background":
                layer_info = self.layer_dict[layer_id]
                layer_states[layer_id] = {
                    "visible": layer_info.get("visible", True),
                    "opacity": layer_info.get("opacity", 1.0),
                    "name": layer_id,  # Use layer_id as display name by default
                }

        control_options["layerStates"] = layer_states

        # Store control in persistent state
        control_key = f"layer_control_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "layer_control",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self.call_js_method("addControl", "layer_control", control_options)

    def _update_layer_controls(self) -> None:
        """Update all existing layer controls with the current layer state."""
        # Find all layer controls in the _controls dictionary
        for control_key, control_config in self._controls.items():
            if control_config.get("type") == "layer_control":
                # Update the layerStates in the control options
                control_options = control_config.get("options", {})
                layers_filter = control_options.get("layers")

                # Get current layer states for this control
                layer_states = {}
                target_layers = (
                    layers_filter
                    if layers_filter is not None
                    else list(self.layer_dict.keys())
                )

                # Always include Background layer for controlling map style layers
                if layers_filter is None or "Background" in layers_filter:
                    layer_states["Background"] = {
                        "visible": True,
                        "opacity": 1.0,
                        "name": "Background",
                    }

                for layer_id in target_layers:
                    if layer_id in self.layer_dict and layer_id != "Background":
                        layer_info = self.layer_dict[layer_id]
                        layer_states[layer_id] = {
                            "visible": layer_info.get("visible", True),
                            "opacity": layer_info.get("opacity", 1.0),
                            "name": layer_id,
                        }

                # Update the control options with new layer states
                control_options["layerStates"] = layer_states

                # Update the control configuration
                control_config["options"] = control_options

        # Trigger the JavaScript layer control to check for new layers
        # by updating the _layer_dict trait that the JS listens to
        self._layer_dict = dict(self.layer_dict)

    def remove_layer(self, layer_id: str) -> None:
        """Remove a layer from the map.

        Args:
            layer_id: Unique identifier for the layer to remove.
        """
        # Remove from JavaScript map
        self.call_js_method("removeLayer", layer_id)

        # Remove from local state
        if layer_id in self._layers:
            current_layers = dict(self._layers)
            del current_layers[layer_id]
            self._layers = current_layers

        # Remove from layer_dict
        if layer_id in self.layer_dict:
            del self.layer_dict[layer_id]

        # Update layer controls if they exist
        self._update_layer_controls()

    def add_cog_layer(
        self,
        layer_id: str,
        cog_url: str,
        opacity: Optional[float] = 1.0,
        visible: Optional[bool] = True,
        paint: Optional[Dict[str, Any]] = None,
        before_id: Optional[str] = None,
    ) -> None:
        """Add a Cloud Optimized GeoTIFF (COG) layer to the map.

        Args:
            layer_id: Unique identifier for the COG layer.
            cog_url: URL to the COG file.
            opacity: Layer opacity between 0.0 and 1.0.
            visible: Whether the layer should be visible initially.
            paint: Optional paint properties for the layer.
            before_id: Optional layer ID to insert this layer before.
        """
        source_id = f"{layer_id}_source"

        # Add COG source using cog:// protocol
        cog_source_url = f"cog://{cog_url}"

        self.add_source(
            source_id,
            {
                "type": "raster",
                "url": cog_source_url,
                "tileSize": 256,
            },
        )

        # Add raster layer
        layer_config = {"id": layer_id, "type": "raster", "source": source_id}

        if paint:
            layer_config["paint"] = paint

        self.add_layer(
            layer_id, layer_config, before_id, opacity=opacity, visible=visible
        )

    def add_pmtiles(
        self,
        pmtiles_url: str,
        layer_id: Optional[str] = None,
        layers: Optional[List[Dict[str, Any]]] = None,
        opacity: Optional[float] = 1.0,
        visible: Optional[bool] = True,
        before_id: Optional[str] = None,
    ) -> None:
        """Add PMTiles vector tiles to the map.

        Args:
            pmtiles_url: URL to the PMTiles file.
            layer_id: Optional unique identifier for the layer. If None, uses filename.
            layers: Optional list of layer configurations for rendering. If None, creates default layers.
            opacity: Layer opacity between 0.0 and 1.0.
            visible: Whether the layer should be visible initially.
            before_id: Optional layer ID to insert this layer before.
        """
        if layer_id is None:
            layer_id = pmtiles_url.split("/")[-1].replace(".pmtiles", "")

        source_id = f"{layer_id}_source"

        # Add PMTiles source using pmtiles:// protocol
        pmtiles_source_url = f"pmtiles://{pmtiles_url}"

        self.add_source(
            source_id,
            {
                "type": "vector",
                "url": pmtiles_source_url,
                "attribution": "PMTiles",
            },
        )

        # Add default layers if none provided
        if layers is None:
            layers = [
                {
                    "id": f"{layer_id}_landuse",
                    "source": source_id,
                    "source-layer": "landuse",
                    "type": "fill",
                    "paint": {"fill-color": "steelblue", "fill-opacity": 0.5},
                },
                {
                    "id": f"{layer_id}_roads",
                    "source": source_id,
                    "source-layer": "roads",
                    "type": "line",
                    "paint": {"line-color": "black", "line-width": 1},
                },
                {
                    "id": f"{layer_id}_buildings",
                    "source": source_id,
                    "source-layer": "buildings",
                    "type": "fill",
                    "paint": {"fill-color": "gray", "fill-opacity": 0.7},
                },
                {
                    "id": f"{layer_id}_water",
                    "source": source_id,
                    "source-layer": "water",
                    "type": "fill",
                    "paint": {"fill-color": "lightblue", "fill-opacity": 0.8},
                },
            ]

        # Add all layers
        for layer_config in layers:
            self.add_layer(
                layer_config["id"],
                layer_config,
                before_id,
                opacity=opacity,
                visible=visible,
            )

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

    def add_draw_control(
        self,
        position: str = "top-left",
        controls: Optional[Dict[str, bool]] = None,
        default_mode: str = "simple_select",
        keybindings: bool = True,
        touch_enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        """Add a draw control to the map for drawing and editing geometries.

        Args:
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            controls: Dictionary specifying which drawing tools to show.
                     Defaults to {'point': True, 'line_string': True, 'polygon': True, 'trash': True}
            default_mode: Initial interaction mode ('simple_select', 'direct_select', 'draw_point', etc.)
            keybindings: Whether to enable keyboard shortcuts
            touch_enabled: Whether to enable touch interactions
            **kwargs: Additional options to pass to MapboxDraw constructor
        """
        if controls is None:
            controls = {
                "point": True,
                "line_string": True,
                "polygon": True,
                "trash": True,
            }

        draw_options = {
            "displayControlsDefault": False,
            "controls": controls,
            "defaultMode": default_mode,
            "keybindings": keybindings,
            "touchEnabled": touch_enabled,
            "position": position,
            **kwargs,
        }

        # Store draw control configuration
        current_controls = dict(self._controls)
        draw_key = f"draw_{position}"
        current_controls[draw_key] = {
            "type": "draw",
            "position": position,
            "options": draw_options,
        }
        self._controls = current_controls

        self.call_js_method("addDrawControl", draw_options)

    def load_draw_data(self, geojson_data: Union[Dict[str, Any], str]) -> None:
        """Load GeoJSON data into the draw control.

        Args:
            geojson_data: GeoJSON data as dictionary or JSON string
        """
        if isinstance(geojson_data, str):
            geojson_data = json.loads(geojson_data)

        # Update the trait immediately to ensure consistency
        self._draw_data = geojson_data

        # Send to JavaScript
        self.call_js_method("loadDrawData", geojson_data)

    def get_draw_data(self) -> Dict[str, Any]:
        """Get all drawn features as GeoJSON.

        Returns:
            Dict containing GeoJSON FeatureCollection with drawn features
        """
        # Try to get current data first
        if self._draw_data:
            return self._draw_data

        # If no data in trait, call JavaScript to get fresh data
        self.call_js_method("getDrawData")
        # Give JavaScript time to execute and sync data
        import time

        time.sleep(0.2)

        # Return the synced data or empty FeatureCollection if nothing
        return (
            self._draw_data
            if self._draw_data
            else {"type": "FeatureCollection", "features": []}
        )

    def clear_draw_data(self) -> None:
        """Clear all drawn features from the draw control."""
        # Clear the trait data immediately
        self._draw_data = {"type": "FeatureCollection", "features": []}

        # Clear in JavaScript
        self.call_js_method("clearDrawData")

    def delete_draw_features(self, feature_ids: List[str]) -> None:
        """Delete specific features from the draw control.

        Args:
            feature_ids: List of feature IDs to delete
        """
        self.call_js_method("deleteDrawFeatures", feature_ids)

    def set_draw_mode(self, mode: str) -> None:
        """Set the draw control mode.

        Args:
            mode: Draw mode ('simple_select', 'direct_select', 'draw_point',
                 'draw_line_string', 'draw_polygon', 'static')
        """
        self.call_js_method("setDrawMode", mode)

    def add_terra_draw(
        self,
        position: str = "top-left",
        modes: Optional[List[str]] = None,
        open: bool = True,
        **kwargs: Any,
    ) -> None:
        """Add a Terra Draw control to the map for drawing and editing geometries.

        Args:
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            modes: List of drawing modes to enable. Available modes:
                  ['render', 'point', 'linestring', 'polygon', 'rectangle', 'circle',
                   'freehand', 'angled-rectangle', 'sensor', 'sector', 'select',
                   'delete-selection', 'delete', 'download']
                  Defaults to all modes except 'render'
            open: Whether the draw control panel should be open by default
            **kwargs: Additional options to pass to Terra Draw constructor
        """
        if modes is None:
            modes = [
                # 'render',  # Commented out to always show drawing tool
                "point",
                "linestring",
                "polygon",
                "rectangle",
                "circle",
                "freehand",
                "angled-rectangle",
                "sensor",
                "sector",
                "select",
                "delete-selection",
                "delete",
                "download",
            ]

        terra_draw_options = {
            "modes": modes,
            "open": open,
            "position": position,
            **kwargs,
        }

        # Mark that Terra Draw is enabled
        self._terra_draw_enabled = True

        # Store Terra Draw control configuration
        current_controls = dict(self._controls)
        terra_draw_key = f"terra_draw_{position}"
        current_controls[terra_draw_key] = {
            "type": "terra_draw",
            "position": position,
            "options": terra_draw_options,
        }
        self._controls = current_controls

        self.call_js_method("addTerraDrawControl", terra_draw_options)

    def get_terra_draw_data(self) -> Dict[str, Any]:
        """Get all Terra Draw features as GeoJSON.

        Returns:
            Dict containing GeoJSON FeatureCollection with drawn features
        """
        # Try to get current data first
        if self._terra_draw_data:
            return self._terra_draw_data

        # If no data in trait, call JavaScript to get fresh data
        self.call_js_method("getTerraDrawData")
        # Give JavaScript time to execute and sync data
        import time

        time.sleep(0.2)

        # Return the synced data or empty FeatureCollection if nothing
        return (
            self._terra_draw_data
            if self._terra_draw_data
            else {"type": "FeatureCollection", "features": []}
        )

    def clear_terra_draw_data(self) -> None:
        """Clear all Terra Draw features from the draw control."""
        # Clear the trait data immediately
        self._terra_draw_data = {"type": "FeatureCollection", "features": []}

        # Clear in JavaScript
        self.call_js_method("clearTerraDrawData")

    def load_terra_draw_data(self, geojson_data: Union[Dict[str, Any], str]) -> None:
        """Load GeoJSON data into the Terra Draw control.

        Args:
            geojson_data: GeoJSON data as dictionary or JSON string
        """
        if isinstance(geojson_data, str):
            geojson_data = json.loads(geojson_data)

        # Update the trait immediately to ensure consistency
        self._terra_draw_data = geojson_data

        # Send to JavaScript
        self.call_js_method("loadTerraDrawData", geojson_data)

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

        /* Force default cursor for all map interactions */
        .maplibregl-canvas {{
            cursor: default !important;
        }}

        .maplibregl-map {{
            cursor: default !important;
        }}

        .maplibregl-ctrl-group button {{
            cursor: default !important;
        }}

        .maplibregl-ctrl button {{
            cursor: default !important;
        }}

        .maplibregl-ctrl-draw {{
            cursor: default !important;
        }}

        .maplibregl-ctrl-draw button {{
            cursor: default !important;
        }}

        .maplibregl-popup-anchor {{
            cursor: default !important;
        }}

        .maplibregl-marker {{
            cursor: default !important;
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

    <script src="https://unpkg.com/@geomatico/maplibre-cog-protocol@0.4.0/dist/index.js"></script>
    <script src="https://unpkg.com/pmtiles@3.2.0/dist/pmtiles.js"></script>
    <script src="https://www.unpkg.com/@mapbox/mapbox-gl-draw@1.5.0/dist/mapbox-gl-draw.js"></script>
    <link rel="stylesheet" href="https://www.unpkg.com/@mapbox/mapbox-gl-draw@1.5.0/dist/mapbox-gl-draw.css">
    <!-- Terra Draw libraries -->
    <script src="https://cdn.jsdelivr.net/npm/@watergis/maplibre-gl-terradraw@1.0.1/dist/maplibre-gl-terradraw.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@watergis/maplibre-gl-terradraw@1.0.1/dist/maplibre-gl-terradraw.css">
    <script>
        // Register COG protocol
        maplibregl.addProtocol("cog", MaplibreCOGProtocol.cogProtocol);

        // Register PMTiles protocol
        const pmtilesProtocol = new pmtiles.Protocol();
        maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);

        // Configure MapboxDraw for MapLibre compatibility
        if (typeof MapboxDraw !== 'undefined') {{
            MapboxDraw.constants.classes.CANVAS = 'maplibregl-canvas';
            MapboxDraw.constants.classes.CONTROL_BASE = 'maplibregl-ctrl';
            MapboxDraw.constants.classes.CONTROL_PREFIX = 'maplibregl-ctrl-';
            MapboxDraw.constants.classes.CONTROL_GROUP = 'maplibregl-ctrl-group';
            MapboxDraw.constants.classes.ATTRIBUTION = 'maplibregl-ctrl-attrib';

            // Create custom styles for MapLibre compatibility
            window.MapLibreDrawStyles = [
                // Point styles
                {{
                    "id": "gl-draw-point-point-stroke-inactive",
                    "type": "circle",
                    "filter": ["all", ["==", "active", "false"], ["==", "$type", "Point"], ["==", "meta", "feature"], ["!=", "mode", "static"]],
                    "paint": {{
                        "circle-radius": 5,
                        "circle-opacity": 1,
                        "circle-color": "#000"
                    }}
                }},
                {{
                    "id": "gl-draw-point-inactive",
                    "type": "circle",
                    "filter": ["all", ["==", "active", "false"], ["==", "$type", "Point"], ["==", "meta", "feature"], ["!=", "mode", "static"]],
                    "paint": {{
                        "circle-radius": 3,
                        "circle-color": "#3bb2d0"
                    }}
                }},
                {{
                    "id": "gl-draw-point-stroke-active",
                    "type": "circle",
                    "filter": ["all", ["==", "active", "true"], ["!=", "meta", "midpoint"], ["==", "$type", "Point"]],
                    "paint": {{
                        "circle-radius": 7,
                        "circle-color": "#000"
                    }}
                }},
                {{
                    "id": "gl-draw-point-active",
                    "type": "circle",
                    "filter": ["all", ["==", "active", "true"], ["!=", "meta", "midpoint"], ["==", "$type", "Point"]],
                    "paint": {{
                        "circle-radius": 5,
                        "circle-color": "#fbb03b"
                    }}
                }},
                // Line styles - fixed for MapLibre
                {{
                    "id": "gl-draw-line-inactive",
                    "type": "line",
                    "filter": ["all", ["==", "active", "false"], ["==", "$type", "LineString"], ["!=", "mode", "static"]],
                    "layout": {{
                        "line-cap": "round",
                        "line-join": "round"
                    }},
                    "paint": {{
                        "line-color": "#3bb2d0",
                        "line-width": 2
                    }}
                }},
                {{
                    "id": "gl-draw-line-active",
                    "type": "line",
                    "filter": ["all", ["==", "active", "true"], ["==", "$type", "LineString"]],
                    "layout": {{
                        "line-cap": "round",
                        "line-join": "round"
                    }},
                    "paint": {{
                        "line-color": "#fbb03b",
                        "line-width": 2,
                        "line-dasharray": ["literal", [0.2, 2]]
                    }}
                }},
                // Polygon fill
                {{
                    "id": "gl-draw-polygon-fill-inactive",
                    "type": "fill",
                    "filter": ["all", ["==", "active", "false"], ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
                    "paint": {{
                        "fill-color": "#3bb2d0",
                        "fill-outline-color": "#3bb2d0",
                        "fill-opacity": 0.1
                    }}
                }},
                {{
                    "id": "gl-draw-polygon-fill-active",
                    "type": "fill",
                    "filter": ["all", ["==", "active", "true"], ["==", "$type", "Polygon"]],
                    "paint": {{
                        "fill-color": "#fbb03b",
                        "fill-outline-color": "#fbb03b",
                        "fill-opacity": 0.1
                    }}
                }},
                // Polygon stroke
                {{
                    "id": "gl-draw-polygon-stroke-inactive",
                    "type": "line",
                    "filter": ["all", ["==", "active", "false"], ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
                    "layout": {{
                        "line-cap": "round",
                        "line-join": "round"
                    }},
                    "paint": {{
                        "line-color": "#3bb2d0",
                        "line-width": 2
                    }}
                }},
                {{
                    "id": "gl-draw-polygon-stroke-active",
                    "type": "line",
                    "filter": ["all", ["==", "active", "true"], ["==", "$type", "Polygon"]],
                    "layout": {{
                        "line-cap": "round",
                        "line-join": "round"
                    }},
                    "paint": {{
                        "line-color": "#fbb03b",
                        "line-width": 2,
                        "line-dasharray": ["literal", [0.2, 2]]
                    }}
                }},
                // Vertices (corner points) for editing
                {{
                    "id": "gl-draw-polygon-and-line-vertex-stroke-inactive",
                    "type": "circle",
                    "filter": ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
                    "paint": {{
                        "circle-radius": 5,
                        "circle-color": "#fff"
                    }}
                }},
                {{
                    "id": "gl-draw-polygon-and-line-vertex-inactive",
                    "type": "circle",
                    "filter": ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
                    "paint": {{
                        "circle-radius": 3,
                        "circle-color": "#fbb03b"
                    }}
                }},
                // Midpoint
                {{
                    "id": "gl-draw-polygon-midpoint",
                    "type": "circle",
                    "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "midpoint"]],
                    "paint": {{
                        "circle-radius": 3,
                        "circle-color": "#fbb03b"
                    }}
                }},
                // Active line vertex styles
                {{
                    "id": "gl-draw-line-vertex-stroke-active",
                    "type": "circle",
                    "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
                    "paint": {{
                        "circle-radius": 7,
                        "circle-color": "#fff"
                    }}
                }},
                {{
                    "id": "gl-draw-line-vertex-active",
                    "type": "circle",
                    "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
                    "paint": {{
                        "circle-radius": 5,
                        "circle-color": "#fbb03b"
                    }}
                }},
                // Polygon vertex styles for direct select mode
                {{
                    "id": "gl-draw-polygon-vertex-stroke-active",
                    "type": "circle",
                    "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
                    "paint": {{
                        "circle-radius": 7,
                        "circle-color": "#fff"
                    }}
                }},
                {{
                    "id": "gl-draw-polygon-vertex-active",
                    "type": "circle",
                    "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"], ["!=", "meta", "midpoint"]],
                    "paint": {{
                        "circle-radius": 5,
                        "circle-color": "#fbb03b"
                    }}
                }}
            ];

            console.log('MapboxDraw configured for MapLibre compatibility with custom styles');
        }}

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

        // Force default cursor for all map interactions
        map.on('load', function() {{
            const canvas = map.getCanvas();
            canvas.style.cursor = 'default';
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

        // Add controls from map state
        const controls = mapState._controls || {{}};
        Object.entries(controls).forEach(([controlKey, controlConfig]) => {{
            try {{
                const {{ type: controlType, position, options: controlOptions }} = controlConfig;
                let control;

                switch (controlType) {{
                    case 'navigation':
                        control = new maplibregl.NavigationControl(controlOptions || {{}});
                        break;
                    case 'scale':
                        control = new maplibregl.ScaleControl(controlOptions || {{}});
                        break;
                    case 'fullscreen':
                        control = new maplibregl.FullscreenControl(controlOptions || {{}});
                        break;
                    case 'geolocate':
                        control = new maplibregl.GeolocateControl(controlOptions || {{}});
                        break;
                    case 'attribution':
                        control = new maplibregl.AttributionControl(controlOptions || {{}});
                        break;
                    case 'globe':
                        control = new maplibregl.GlobeControl(controlOptions || {{}});
                        break;
                    case 'draw':
                        // Handle draw control restoration
                        if (typeof MapboxDraw !== 'undefined') {{
                            // Use custom styles for MapLibre compatibility
                            const drawOptions = {{
                                ...controlOptions,
                                styles: window.MapLibreDrawStyles || undefined
                            }};
                            control = new MapboxDraw(drawOptions);

                            // Store reference for data loading
                            window.drawControl = control;

                            // Set up draw event handlers
                            map.on('draw.create', function(e) {{
                                console.log('Draw created:', e.features);
                            }});
                            map.on('draw.update', function(e) {{
                                console.log('Draw updated:', e.features);
                            }});
                            map.on('draw.delete', function(e) {{
                                console.log('Draw deleted:', e.features);
                            }});
                            map.on('draw.selectionchange', function(e) {{
                                console.log('Draw selection changed:', e.features);
                            }});

                            console.log('Draw control restored successfully with custom styles');

                            // Load saved draw data if it exists
                            const savedDrawData = mapState._draw_data;
                            if (savedDrawData && savedDrawData.features && savedDrawData.features.length > 0) {{
                                try {{
                                    control.set(savedDrawData);
                                    console.log('Saved draw data loaded successfully:', savedDrawData);
                                }} catch (error) {{
                                    console.error('Failed to load saved draw data:', error);
                                }}
                            }}
                        }} else {{
                            console.warn('MapboxDraw not available during restore');
                            return;
                        }}
                        break;
                    case 'terra_draw':
                        // Handle Terra Draw control restoration
                        if (typeof MaplibreTerradrawControl !== 'undefined') {{
                            const terraDrawOptions = {{
                                ...controlOptions
                            }};
                            control = new MaplibreTerradrawControl.MaplibreTerradrawControl(terraDrawOptions);

                            // Store reference for data operations
                            window.terraDrawControl = control;

                            console.log('Terra Draw control restored successfully');

                            // Load saved Terra Draw data if it exists
                            const savedTerraDrawData = mapState._terra_draw_data;
                            if (savedTerraDrawData && savedTerraDrawData.features && savedTerraDrawData.features.length > 0) {{
                                try {{
                                    // Terra Draw data loading would need to be implemented based on the library's API
                                    console.log('Saved Terra Draw data found:', savedTerraDrawData);
                                }} catch (error) {{
                                    console.error('Failed to load saved Terra Draw data:', error);
                                }}
                            }}
                        }} else {{
                            console.warn('MaplibreTerradrawControl not available during restore');
                            return;
                        }}
                        break;
                    default:
                        console.warn(`Unknown control type during restore: ${{controlType}}`);
                        return;
                }}

                map.addControl(control, position);
            }} catch (error) {{
                console.warn(`Failed to add control ${{controlKey}}:`, error);
            }}
        }});

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


class LayerManagerWidget(v.ExpansionPanels):
    """
    A widget for managing map layers.

    This widget provides controls for toggling the visibility, adjusting the opacity,
    and removing layers from a map. It also includes a master toggle to turn all layers
    on or off.

    Attributes:
        m (Map): The map object to manage layers for.
        layer_items (Dict[str, Dict[str, widgets.Widget]]): A dictionary mapping layer names
            to their corresponding control widgets (checkbox and slider).
        _building (bool): A flag indicating whether the widget is currently being built.
        master_toggle (widgets.Checkbox): A checkbox to toggle all layers on or off.
        layers_box (widgets.VBox): A container for individual layer controls.
    """

    def __init__(
        self,
        m: Any,
        expanded: bool = True,
        height: str = "40px",
        layer_icon: str = "mdi-layers",
        close_icon: str = "mdi-close",
        label="Layers",
        background_color: str = "#f5f5f5",
        groups: dict = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the LayerManagerWidget.

        Args:
            m (Any): The map object to manage layers for.
            expanded (bool): Whether the expansion panel should be expanded by default. Defaults to True.
            height (str): The height of the header. Defaults to "40px".
            layer_icon (str): The icon for the layer manager. Defaults to "mdi-layers".
            close_icon (str): The icon for the close button. Defaults to "mdi-close".
            label (str): The label for the layer manager. Defaults to "Layers".
            background_color (str): The background color of the header. Defaults to "#f5f5f5".
            groups (dict): A dictionary of layer groups, such as {"Group 1": ["layer1", "layer2"],
                "Group 2": ["layer3", "layer4"]}. A group layer toggle will be created for each group.
                Defaults to None.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        self.m = m
        self.layer_items = {}
        self.groups = groups
        self._building = False

        # Master toggle
        style = {"description_width": "initial"}
        self.master_toggle = widgets.Checkbox(
            value=True, description="All layers on/off", style=style
        )
        self.master_toggle.observe(self.toggle_all_layers, names="value")

        self.group_toggles = widgets.VBox()
        if isinstance(groups, dict):
            for group_name, group_layers in groups.items():
                group_toggle = widgets.Checkbox(
                    value=True,
                    description=f"{group_name} group layers on/off",
                    style=style,
                )
                group_toggle.observe(self.toggle_group_layers, names="value")
                self.group_toggles.children += (group_toggle,)

        # Build individual layer rows
        self.layers_box = widgets.VBox()
        self.build_layer_controls()

        # Close icon button
        close_btn = v.Btn(
            icon=True,
            small=True,
            class_="ma-0",
            style_="min-width: 24px; width: 24px;",
            children=[v.Icon(children=[close_icon])],
        )
        close_btn.on_event("click", self._handle_close)

        header = v.ExpansionPanelHeader(
            style_=f"height: {height}; min-height: {height}; background-color: {background_color};",
            children=[
                v.Row(
                    align="center",
                    class_="d-flex flex-grow-1 align-center",
                    children=[
                        v.Icon(children=[layer_icon], class_="ml-1"),
                        v.Spacer(),  # push title to center
                        v.Html(tag="span", children=[label], class_="text-subtitle-2"),
                        v.Spacer(),  # push close to right
                        close_btn,
                        v.Spacer(),
                    ],
                )
            ],
        )

        panel = v.ExpansionPanel(
            children=[
                header,
                v.ExpansionPanelContent(
                    children=[
                        widgets.VBox(
                            [self.master_toggle, self.group_toggles, self.layers_box]
                        )
                    ]
                ),
            ]
        )

        if expanded:
            super().__init__(
                children=[panel], v_model=[0], multiple=True, *args, **kwargs
            )
        else:
            super().__init__(children=[panel], multiple=True, *args, **kwargs)

    def _handle_close(self, widget=None, event=None, data=None):
        """Calls the on_close callback if provided."""

        self.m.remove_from_sidebar(self)
        # self.close()

    def build_layer_controls(self) -> None:
        """
        Builds the controls for individual layers.

        This method creates checkboxes for toggling visibility, sliders for adjusting opacity,
        and buttons for removing layers.
        """
        self._building = True
        self.layer_items.clear()
        rows = []

        style = {"description_width": "initial"}
        padding = "0px 5px 0px 5px"

        for name, info in list(self.m.layer_dict.items()):
            # if name == "Background":
            #     continue

            visible = info.get("visible", True)
            opacity = info.get("opacity", 1.0)

            checkbox = widgets.Checkbox(value=visible, description=name, style=style)
            checkbox.layout.max_width = "150px"

            slider = widgets.FloatSlider(
                value=opacity,
                min=0,
                max=1,
                step=0.01,
                readout=False,
                tooltip="Change layer opacity",
                layout=widgets.Layout(width="150px", padding=padding),
            )

            settings = widgets.Button(
                icon="gear",
                tooltip="Change layer style",
                layout=widgets.Layout(width="38px", height="25px", padding=padding),
            )

            remove = widgets.Button(
                icon="times",
                tooltip="Remove layer",
                layout=widgets.Layout(width="38px", height="25px", padding=padding),
            )

            def on_visibility_change(change, layer_name=name):
                self.set_layer_visibility(layer_name, change["new"])

            def on_opacity_change(change, layer_name=name):
                self.set_layer_opacity(layer_name, change["new"])

            def on_remove_clicked(btn, layer_name=name, row_ref=None):
                if layer_name == "Background":
                    for layer in self.m.get_style_layers():
                        self.m.add_call("removeLayer", layer["id"])
                else:
                    self.m.remove_layer(layer_name)
                if row_ref in self.layers_box.children:
                    self.layers_box.children = tuple(
                        c for c in self.layers_box.children if c != row_ref
                    )
                self.layer_items.pop(layer_name, None)
                if f"Style {layer_name}" in self.m.sidebar_widgets:
                    self.m.remove_from_sidebar(name=f"Style {layer_name}")

            def on_settings_clicked(btn, layer_name=name):
                style_widget = LayerStyleWidget(self.m.layer_dict[layer_name], self.m)
                self.m.add_to_sidebar(
                    style_widget,
                    widget_icon="mdi-palette",
                    label=f"Style {layer_name}",
                )

            checkbox.observe(on_visibility_change, names="value")
            slider.observe(on_opacity_change, names="value")

            row = widgets.HBox(
                [checkbox, slider, settings, remove], layout=widgets.Layout()
            )

            remove.on_click(
                lambda btn, r=row, n=name: on_remove_clicked(
                    btn, layer_name=n, row_ref=r
                )
            )

            settings.on_click(
                lambda btn, n=name: on_settings_clicked(btn, layer_name=n)
            )

            rows.append(row)
            self.layer_items[name] = {"checkbox": checkbox, "slider": slider}

        self.layers_box.children = rows
        self._building = False

    def toggle_all_layers(self, change: Dict[str, Any]) -> None:
        """
        Toggles the visibility of all layers.

        Args:
            change (Dict[str, Any]): The change event from the master toggle checkbox.
        """
        if self._building:
            return
        for name, controls in self.layer_items.items():
            controls["checkbox"].value = change["new"]

        for widget in self.group_toggles.children:
            widget.value = change["new"]

    def toggle_group_layers(self, change: Dict[str, Any]) -> None:
        """
        Toggles the visibility of a group of layers.
        """
        if self._building:
            return
        group_name = change["owner"].description.split(" ")[0]
        group_layers = self.groups[group_name]
        for layer_name in group_layers:
            self.set_layer_visibility(layer_name, change["new"])
        self.refresh()

    def set_layer_visibility(self, name: str, visible: bool) -> None:
        """
        Sets the visibility of a specific layer.

        Args:
            name (str): The name of the layer.
            visible (bool): Whether the layer should be visible.
        """
        self.m.set_visibility(name, visible)

    def set_layer_opacity(self, name: str, opacity: float) -> None:
        """
        Sets the opacity of a specific layer.

        Args:
            name (str): The name of the layer.
            opacity (float): The opacity value (0 to 1).
        """
        self.m.set_opacity(name, opacity)

    def refresh(self) -> None:
        """
        Rebuilds the UI to reflect the current layers in the map.
        """
        """Rebuild the UI to reflect current layers in the map."""
        self.build_layer_controls()


class CustomWidget(v.ExpansionPanels):
    """
    A custom expansion panel widget with dynamic widget management.

    This widget allows for the creation of an expandable panel with a customizable header
    and dynamic content. Widgets can be added, removed, or replaced in the content box.

    Attributes:
        content_box (widgets.VBox): A container for holding the widgets displayed in the panel.
        panel (v.ExpansionPanel): The main expansion panel containing the header and content.
    """

    def __init__(
        self,
        widget: Optional[Union[widgets.Widget, List[widgets.Widget]]] = None,
        widget_icon: str = "mdi-tools",
        close_icon: str = "mdi-close",
        label: str = "My Tools",
        background_color: str = "#f5f5f5",
        height: str = "40px",
        expanded: bool = True,
        host_map: Optional[Any] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the CustomWidget.

        Args:
            widget (Optional[Union[widgets.Widget, List[widgets.Widget]]]): Initial widget(s) to display in the content box.
            widget_icon (str): Icon for the header. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            close_icon (str): Icon for the close button. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            background_color (str): Background color of the header. Defaults to "#f5f5f5".
            label (str): Text label for the header. Defaults to "My Tools".
            height (str): Height of the header. Defaults to "40px".
            expanded (bool): Whether the panel is expanded by default. Defaults to True.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        # Wrap content in a mutable VBox
        self.content_box = widgets.VBox()
        self.host_map = host_map
        if widget:
            if isinstance(widget, (list, tuple)):
                self.content_box.children = widget
            else:
                self.content_box.children = [widget]

        # Close icon button
        close_btn = v.Btn(
            icon=True,
            small=True,
            class_="ma-0",
            style_="min-width: 24px; width: 24px;",
            children=[v.Icon(children=[close_icon])],
        )
        close_btn.on_event("click", self._handle_close)

        header = v.ExpansionPanelHeader(
            style_=f"height: {height}; min-height: {height}; background-color: {background_color};",
            children=[
                v.Row(
                    align="center",
                    class_="d-flex flex-grow-1 align-center",
                    children=[
                        v.Icon(children=[widget_icon], class_="ml-1"),
                        v.Spacer(),  # push title to center
                        v.Html(tag="span", children=[label], class_="text-subtitle-2"),
                        v.Spacer(),  # push close to right
                        close_btn,
                        v.Spacer(),
                    ],
                )
            ],
        )

        self.panel = v.ExpansionPanel(
            children=[
                header,
                v.ExpansionPanelContent(children=[self.content_box]),
            ]
        )

        super().__init__(
            children=[self.panel],
            v_model=[0] if expanded else [],
            multiple=True,
            *args,
            **kwargs,
        )

    def _handle_close(self, widget=None, event=None, data=None):
        """Calls the on_close callback if provided."""

        if self.host_map is not None:
            self.host_map.remove_from_sidebar(self)
        # self.close()

    def add_widget(self, widget: widgets.Widget) -> None:
        """
        Adds a widget to the content box.

        Args:
            widget (widgets.Widget): The widget to add to the content box.
        """
        self.content_box.children += (widget,)

    def remove_widget(self, widget: widgets.Widget) -> None:
        """
        Removes a widget from the content box.

        Args:
            widget (widgets.Widget): The widget to remove from the content box.
        """
        self.content_box.children = tuple(
            w for w in self.content_box.children if w != widget
        )

    def set_widgets(self, widgets_list: List[widgets.Widget]) -> None:
        """
        Replaces all widgets in the content box.

        Args:
            widgets_list (List[widgets.Widget]): A list of widgets to set as the content of the content box.
        """
        self.content_box.children = widgets_list


class LayerStyleWidget(widgets.VBox):
    """
    A widget for styling map layers interactively.

    Args:
        layer (dict): The layer to style.
        map_widget (ipyleaflet.Map or folium.Map): The map widget to update.
        widget_width (str, optional): The width of the widget. Defaults to "270px".
        label_width (str, optional): The width of the label. Defaults to "130px".
    """

    def __init__(
        self,
        layer: dict,
        map_widget: MapLibreMap,
        widget_width: str = "270px",
        label_width: str = "130px",
    ):
        super().__init__()
        self.layer = layer
        self.map = map_widget
        self.layer_type = self._get_layer_type()
        self.layer_id = layer["layer"].id
        self.layer_paint = layer["layer"].paint
        self.original_style = self._get_current_style()
        self.widget_width = widget_width
        self.label_width = label_width

        # Create the styling widgets based on layer type
        self.style_widgets = self._create_style_widgets()

        # Create buttons
        self.apply_btn = widgets.Button(
            description="Apply",
            button_style="primary",
            tooltip="Apply style changes",
            layout=widgets.Layout(width="auto"),
        )

        self.reset_btn = widgets.Button(
            description="Reset",
            button_style="warning",
            tooltip="Reset to original style",
            layout=widgets.Layout(width="auto"),
        )

        self.close_btn = widgets.Button(
            description="Close",
            button_style="",
            tooltip="Close the widget",
            layout=widgets.Layout(width="auto"),
        )

        self.output_widget = widgets.Output()

        # Button container
        self.button_box = widgets.HBox([self.apply_btn, self.reset_btn, self.close_btn])

        # Add button callbacks
        self.apply_btn.on_click(self._apply_style)
        self.reset_btn.on_click(self._reset_style)
        self.close_btn.on_click(self._close_widget)

        # Layout
        self.layout = widgets.Layout(width="300px", padding="10px")

        # Combine all widgets
        self.children = [*self.style_widgets, self.button_box, self.output_widget]

    def _get_layer_type(self) -> str:
        """Determine the layer type."""
        return self.layer["type"]

    def _get_current_style(self) -> dict:
        """Get the current layer style."""
        return self.layer_paint

    def _create_style_widgets(self) -> List[widgets.Widget]:
        """Create style widgets based on layer type."""
        widgets_list = []

        if self.layer_type == "circle":
            widgets_list.extend(
                [
                    self._create_color_picker(
                        "Circle Color", "circle-color", "#3388ff"
                    ),
                    self._create_number_slider(
                        "Circle Radius", "circle-radius", 6, 1, 20
                    ),
                    self._create_number_slider(
                        "Circle Opacity", "circle-opacity", 0.8, 0, 1, 0.05
                    ),
                    self._create_number_slider(
                        "Circle Blur", "circle-blur", 0, 0, 1, 0.05
                    ),
                    self._create_color_picker(
                        "Circle Stroke Color", "circle-stroke-color", "#3388ff"
                    ),
                    self._create_number_slider(
                        "Circle Stroke Width", "circle-stroke-width", 1, 0, 5
                    ),
                    self._create_number_slider(
                        "Circle Stroke Opacity",
                        "circle-stroke-opacity",
                        1.0,
                        0,
                        1,
                        0.05,
                    ),
                ]
            )

        elif self.layer_type == "line":
            widgets_list.extend(
                [
                    self._create_color_picker("Line Color", "line-color", "#3388ff"),
                    self._create_number_slider("Line Width", "line-width", 2, 1, 10),
                    self._create_number_slider(
                        "Line Opacity", "line-opacity", 1.0, 0, 1, 0.05
                    ),
                    self._create_number_slider("Line Blur", "line-blur", 0, 0, 1, 0.05),
                    self._create_dropdown(
                        "Line Style",
                        "line-dasharray",
                        [
                            ("Solid", [1]),
                            ("Dashed", [2, 4]),
                            ("Dotted", [1, 4]),
                            ("Dash-dot", [2, 4, 8, 4]),
                        ],
                    ),
                ]
            )

        elif self.layer_type == "fill":
            widgets_list.extend(
                [
                    self._create_color_picker("Fill Color", "fill-color", "#3388ff"),
                    self._create_number_slider(
                        "Fill Opacity", "fill-opacity", 0.2, 0, 1, 0.05
                    ),
                    self._create_color_picker(
                        "Fill Outline Color", "fill-outline-color", "#3388ff"
                    ),
                ]
            )
        else:
            widgets_list.extend(
                [widgets.HTML(value=f"Layer type {self.layer_type} is not supported.")]
            )

        return widgets_list

    def _create_color_picker(
        self, description: str, property_name: str, default_color: str
    ) -> widgets.ColorPicker:
        """Create a color picker widget."""
        return widgets.ColorPicker(
            description=description,
            value=self.original_style.get(property_name, default_color),
            layout=widgets.Layout(
                width=self.widget_width, description_width=self.label_width
            ),
            style={"description_width": "initial"},
        )

    def _create_number_slider(
        self,
        description: str,
        property_name: str,
        default_value: float,
        min_val: float,
        max_val: float,
        step: float = 1,
    ) -> widgets.FloatSlider:
        """Create a number slider widget."""
        return widgets.FloatSlider(
            description=description,
            value=self.original_style.get(property_name, default_value),
            min=min_val,
            max=max_val,
            step=step,
            layout=widgets.Layout(
                width=self.widget_width, description_width=self.label_width
            ),
            style={"description_width": "initial"},
            continuous_update=False,
        )

    def _create_dropdown(
        self,
        description: str,
        property_name: str,
        options: List[Tuple[str, List[float]]],
    ) -> widgets.Dropdown:
        """Create a dropdown widget."""
        return widgets.Dropdown(
            description=description,
            options=options,
            value=self.original_style.get(property_name, options[0][1]),
            layout=widgets.Layout(
                width=self.widget_width, description_width=self.label_width
            ),
            style={"description_width": "initial"},
        )

    def _apply_style(self, _) -> None:
        """Apply the style changes to the layer."""
        new_style = {}

        for widget in self.style_widgets:
            if isinstance(widget, widgets.ColorPicker):
                property_name = widget.description.lower().replace(" ", "-")
                new_style[property_name] = widget.value
            elif isinstance(widget, widgets.FloatSlider):
                property_name = widget.description.lower().replace(" ", "-")
                new_style[property_name] = widget.value
            elif isinstance(widget, widgets.Dropdown):
                property_name = widget.description.lower().replace(" ", "-")
                new_style[property_name] = widget.value

        with self.output_widget:
            try:
                for key, value in new_style.items():
                    if key == "line-style":
                        key = "line-dasharray"
                    self.map.set_paint_property(self.layer["layer"].id, key, value)
            except Exception as e:
                print(e)

        self.map.layer_manager.refresh()

    def _reset_style(self, _) -> None:
        """Reset to original style."""

        # Update widgets to reflect original style
        for widget in self.style_widgets:
            if isinstance(
                widget, (widgets.ColorPicker, widgets.FloatSlider, widgets.Dropdown)
            ):
                property_name = widget.description.lower().replace(" ", "-")
                if property_name in self.original_style:
                    widget.value = self.original_style[property_name]

    def _close_widget(self, _) -> None:
        """Close the widget."""
        # self.close()
        self.map.remove_from_sidebar(name=f"Style {self.layer['layer'].id}")


class Container(v.Container):
    """
    A container widget for displaying a map with an optional sidebar.

    This class creates a layout with a map on the left and a sidebar on the right.
    The sidebar can be toggled on or off and can display additional content.

    Attributes:
        sidebar_visible (bool): Whether the sidebar is visible.
        min_width (int): Minimum width of the sidebar in pixels.
        max_width (int): Maximum width of the sidebar in pixels.
        map_container (v.Col): The container for the map.
        sidebar_content_box (widgets.VBox): The container for the sidebar content.
        toggle_icon (v.Icon): The icon for the toggle button.
        toggle_btn (v.Btn): The button to toggle the sidebar.
        sidebar (v.Col): The container for the sidebar.
        row (v.Row): The main layout row containing the map and sidebar.
    """

    def __init__(
        self,
        host_map: Optional[Any] = None,
        sidebar_visible: bool = True,
        min_width: int = 250,
        max_width: int = 300,
        sidebar_content: Optional[Union[widgets.VBox, List[widgets.Widget]]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the Container widget.

        Args:
            host_map (Optional[Any]): The map object to display in the container. Defaults to None.
            sidebar_visible (bool): Whether the sidebar is visible. Defaults to True.
            min_width (int): Minimum width of the sidebar in pixels. Defaults to 250.
            max_width (int): Maximum width of the sidebar in pixels. Defaults to 300.
            sidebar_content (Optional[Union[widgets.VBox, List[widgets.Widget]]]):
                The content to display in the sidebar. Defaults to None.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        self.sidebar_visible = sidebar_visible
        self.min_width = min_width
        self.max_width = max_width
        self.host_map = host_map
        self.sidebar_widgets = {}

        # Map display container (left column)
        self.map_container = v.Col(
            class_="pa-1",
            style_="flex-grow: 1; flex-shrink: 1; flex-basis: 0;",
        )
        self.map_container.children = [host_map or self.create_map()]

        # Sidebar content container (mutable VBox)
        self.sidebar_content_box = widgets.VBox()
        if sidebar_content:
            self.set_sidebar_content(sidebar_content)

        # Toggle button
        if sidebar_visible:
            self.toggle_icon = v.Icon(children=["mdi-chevron-right"])
        else:
            self.toggle_icon = v.Icon(children=["mdi-chevron-left"])  # default icon
        self.toggle_btn = v.Btn(
            icon=True,
            children=[self.toggle_icon],
            style_="width: 48px; height: 48px; min-width: 48px;",
        )
        self.toggle_btn.on_event("click", self.toggle_sidebar)

        # Settings icon
        self.settings_icon = v.Icon(children=["mdi-wrench"])
        self.settings_btn = v.Btn(
            icon=True,
            children=[self.settings_icon],
            style_="width: 36px; height: 36px;",
        )
        self.settings_btn.on_event("click", self.toggle_width_slider)

        # Sidebar controls row (toggle + settings)
        self.sidebar_controls = v.Row(
            class_="ma-0 pa-0", children=[self.toggle_btn, self.settings_btn]
        )

        # Sidebar width slider (initially hidden)
        self.width_slider = widgets.IntSlider(
            value=self.max_width,
            min=200,
            max=1000,
            step=10,
            description="Width:",
            continuous_update=True,
        )
        self.width_slider.observe(self.on_width_change, names="value")

        self.settings_widget = CustomWidget(
            self.width_slider,
            widget_icon="mdi-cog",
            label="Sidebar Settings",
            host_map=self.host_map,
        )

        # Sidebar (right column)
        self.sidebar = v.Col(class_="pa-1", style_="overflow-y: hidden;")
        self.update_sidebar_content()

        # Main layout row
        self.row = v.Row(
            class_="d-flex flex-nowrap",
            children=[self.map_container, self.sidebar],
        )

        super().__init__(fluid=True, children=[self.row], *args, **kwargs)

    def create_map(self) -> Any:
        """
        Creates a default map object.

        Returns:
            Any: A default map object.
        """
        return MapLibreMap(center=[20, 0], zoom=2)

    def toggle_sidebar(self, *args: Any, **kwargs: Any) -> None:
        """
        Toggles the visibility of the sidebar.

        Args:
            *args (Any): Additional positional arguments.
            **kwargs (Any): Additional keyword arguments.
        """
        self.sidebar_visible = not self.sidebar_visible
        self.toggle_icon.children = [
            "mdi-chevron-right" if self.sidebar_visible else "mdi-chevron-left"
        ]
        self.update_sidebar_content()

    def update_sidebar_content(self) -> None:
        """
        Updates the content of the sidebar based on its visibility.
        If the sidebar is visible, it displays the toggle button and the sidebar content.
        If the sidebar is hidden, it only displays the toggle button.
        """
        if self.sidebar_visible:
            # Header row: toggle on the left, settings on the right
            header_row = v.Row(
                class_="ma-0 pa-0",
                align="center",
                justify="space-between",
                children=[self.toggle_btn, self.settings_btn],
            )

            children = [header_row]

            children.append(self.sidebar_content_box)

            self.sidebar.children = children
            self.sidebar.style_ = (
                f"min-width: {self.min_width}px; max-width: {self.max_width}px;"
            )
        else:
            self.sidebar.children = [self.toggle_btn]
            self.sidebar.style_ = "width: 48px; min-width: 48px; max-width: 48px;"

    def set_sidebar_content(
        self, content: Union[widgets.VBox, List[widgets.Widget]]
    ) -> None:
        """
        Replaces all content in the sidebar (except the toggle button).

        Args:
            content (Union[widgets.VBox, List[widgets.Widget]]): The new content for the sidebar.
        """
        if isinstance(content, (list, tuple)):
            self.sidebar_content_box.children = content
        else:
            self.sidebar_content_box.children = [content]

    def add_to_sidebar(
        self,
        widget: widgets.Widget,
        add_header: bool = True,
        widget_icon: str = "mdi-tools",
        close_icon: str = "mdi-close",
        label: str = "My Tools",
        background_color: str = "#f5f5f5",
        height: str = "40px",
        expanded: bool = True,
        host_map: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Appends a widget to the sidebar content.

        Args:
            widget (Optional[Union[widgets.Widget, List[widgets.Widget]]]): Initial widget(s) to display in the content box.
            widget_icon (str): Icon for the header. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            close_icon (str): Icon for the close button. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            background_color (str): Background color of the header. Defaults to "#f5f5f5".
            label (str): Text label for the header. Defaults to "My Tools".
            height (str): Height of the header. Defaults to "40px".
            expanded (bool): Whether the panel is expanded by default. Defaults to True.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """

        if label in self.sidebar_widgets:
            self.remove_from_sidebar(name=label)

        if add_header:
            widget = CustomWidget(
                widget,
                widget_icon=widget_icon,
                close_icon=close_icon,
                label=label,
                background_color=background_color,
                height=height,
                expanded=expanded,
                host_map=host_map,
                **kwargs,
            )

        self.sidebar_content_box.children += (widget,)
        self.sidebar_widgets[label] = widget

    def remove_from_sidebar(
        self, widget: widgets.Widget = None, name: str = None
    ) -> None:
        """
        Removes a widget from the sidebar content.

        Args:
            widget (widgets.Widget): The widget to remove from the sidebar.
            name (str): The name of the widget to remove from the sidebar.
        """
        key = None
        for key, value in self.sidebar_widgets.items():
            if value == widget or key == name:
                if widget is None:
                    widget = self.sidebar_widgets[key]
                break

        if key is not None and key in self.sidebar_widgets:
            self.sidebar_widgets.pop(key)
        self.sidebar_content_box.children = tuple(
            child for child in self.sidebar_content_box.children if child != widget
        )

    def set_sidebar_width(self, min_width: int = None, max_width: int = None) -> None:
        """
        Dynamically updates the sidebar's minimum and maximum width.

        Args:
            min_width (int, optional): New minimum width in pixels. If None, keep current.
            max_width (int, optional): New maximum width in pixels. If None, keep current.
        """
        if min_width is not None:
            if isinstance(min_width, str):
                min_width = int(min_width.replace("px", ""))
            self.min_width = min_width
        if max_width is not None:
            if isinstance(max_width, str):
                max_width = int(max_width.replace("px", ""))
            self.max_width = max_width
        self.update_sidebar_content()

    def toggle_width_slider(self, *args: Any) -> None:

        if self.settings_widget not in self.sidebar_content_box.children:
            self.add_to_sidebar(self.settings_widget, add_header=False)

    def on_width_change(self, change: dict) -> None:
        new_width = change["new"]
        self.set_sidebar_width(min_width=new_width, max_width=new_width)
