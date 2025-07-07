"""MapLibre GL JS implementation of the map widget.

This module provides the MapLibreMap class which implements an interactive map
widget using the MapLibre GL JS library. MapLibre GL JS is an open-source fork
of Mapbox GL JS, providing fast vector map rendering with WebGL.

Classes:
    MapLibreMap: Main map widget class for MapLibre GL JS.

Example:
    Basic usage of MapLibreMap:

    >>> from anymap.maplibre import MapLibreMap
    >>> m = MapLibreMap(center=[-74.0, 40.7], zoom=10)
    >>> m.add_basemap("OpenStreetMap.Mapnik")
    >>> m
"""

import json
import os
import pathlib
import requests
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import ipywidgets as widgets
import traitlets
from IPython.display import display

from .base import MapWidget
from .utils import construct_maplibre_style, get_env_var
from .maplibre_widgets import Container, LayerManagerWidget

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
        center: List[float] = [0, 20],
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
            "layers": "top-right",
        },
        projection: str = "mercator",
        add_sidebar: bool = False,
        sidebar_visible: bool = False,
        sidebar_width: int = 360,
        sidebar_args: Optional[Dict] = None,
        layer_manager_expanded: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize MapLibre map widget.

        Args:
            center: Map center coordinates as [longitude, latitude]. Default is [0, 20].
            zoom: Initial zoom level (typically 0-20). Default is 1.0.
            style: MapLibre style URL string or style object dictionary.
            width: Widget width as CSS string (e.g., "100%", "800px").
            height: Widget height as CSS string (e.g., "600px", "50vh").
            bearing: Map bearing (rotation) in degrees (0-360).
            pitch: Map pitch (tilt) in degrees (0-60).
            controls: Dictionary of control names and their positions. Default is {
                "navigation": "top-right",
                "fullscreen": "top-right",
                "scale": "bottom-left",
                "globe": "top-right",
                "layers": "top-right",
            }.
            projection: Map projection type. Can be "mercator" or "globe". Default is "mercator".
            add_sidebar: Whether to add a sidebar to the map. Default is False.
            sidebar_visible: Whether the sidebar is visible. Default is False.
            sidebar_width: Width of the sidebar in pixels. Default is 360.
            sidebar_args: Additional keyword arguments for the sidebar. Default is None.
            layer_manager_expanded: Whether the layer manager is expanded. Default is True.
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

        # Initialize current state attributes
        self._current_center = center
        self._current_zoom = zoom
        self._current_bearing = bearing
        self._current_pitch = pitch
        self._current_bounds = None  # Will be set after map loads

        # Register event handler to update current state
        self.on_map_event("moveend", self._update_current_state)

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

        self.controls = {}
        for control, position in controls.items():
            if control == "layers":
                self.add_layer_control(position)
            else:
                self.add_control(control, position)
                self.controls[control] = position

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

    def set_terrain(
        self,
        source: str = "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png",
        exaggeration: float = 1.0,
        tile_size: int = 256,
        encoding: str = "terrarium",
        source_id: str = "terrain-dem",
    ) -> None:
        """Add terrain visualization to the map.

        Args:
            source: URL template for terrain tiles. Defaults to AWS elevation tiles.
            exaggeration: Terrain exaggeration factor. Defaults to 1.0.
            tile_size: Tile size in pixels. Defaults to 256.
            encoding: Encoding for the terrain tiles. Defaults to "terrarium".
            source_id: Unique identifier for the terrain source. Defaults to "terrain-dem".
        """
        # Add terrain source
        self.add_source(
            source_id,
            {
                "type": "raster-dem",
                "tiles": [source],
                "tileSize": tile_size,
                "encoding": encoding,
            },
        )

        # Set terrain on the map
        terrain_config = {"source": source_id, "exaggeration": exaggeration}

        # Store terrain configuration in persistent state
        self._terrain = terrain_config
        self.call_js_method("setTerrain", terrain_config)

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

    def add_marker(self, lng: float, lat: float, popup: Optional[str] = None) -> None:
        """Add a marker to the map.

        Args:
            lng: Longitude coordinate for the marker.
            lat: Latitude coordinate for the marker.
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

    def add_geocoder_control(
        self,
        position: str = "top-left",
        api_config: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        collapsed: bool = True,
    ) -> None:
        """Add a geocoder control to the map for searching locations.

        The geocoder control allows users to search for locations using a geocoding service.
        By default, it uses the Nominatim (OpenStreetMap) geocoding API.

        Args:
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            api_config: Configuration for the geocoding API. If None, uses default Nominatim config
            options: Additional options for the geocoder control
            collapsed: If True, shows only search icon initially. Click to expand input box.
        """
        if api_config is None:
            # Default configuration using Nominatim API
            api_config = {
                "forwardGeocode": True,
                "reverseGeocode": False,
                "placeholder": "Search for places...",
                "limit": 5,
                "api_url": "https://nominatim.openstreetmap.org/search",
            }

        control_options = options or {}
        control_options.update(
            {
                "position": position,
                "api_config": api_config,
                "collapsed": collapsed,
            }
        )

        # Store control in persistent state
        control_key = f"geocoder_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "geocoder",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self.call_js_method("addControl", "geocoder", control_options)

    def add_google_streetview(
        self,
        position: str = "top-left",
        api_key: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a Google Street View control to the map.

        This method adds a Google Street View control that allows users to view
        street-level imagery at clicked locations on the map.

        Args:
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            api_key: Google Maps API key. If None, retrieves from GOOGLE_MAPS_API_KEY environment variable
            options: Additional options for the Street View control

        Raises:
            ValueError: If no API key is provided and none can be found in environment variables
        """
        if api_key is None:
            api_key = get_env_var("GOOGLE_MAPS_API_KEY")
            if api_key is None:
                raise ValueError(
                    "Google Maps API key is required. Please provide it as a parameter "
                    "or set the GOOGLE_MAPS_API_KEY environment variable."
                )

        control_options = options or {}
        control_options.update(
            {
                "position": position,
                "api_key": api_key,
            }
        )

        # Store control in persistent state
        control_key = f"google_streetview_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "google_streetview",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self.call_js_method("addControl", "google_streetview", control_options)

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
        import os

        # Get the directory of the current file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, "templates", "maplibre_template.html")

        # Read the template file
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        # Serialize map state for JavaScript
        map_state_json = json.dumps(map_state, indent=2)

        # Replace placeholders with actual values
        html_template = template_content.format(
            title=title,
            width=map_state["width"],
            height=map_state["height"],
            map_state_json=map_state_json,
        )

        return html_template

    def _update_current_state(self, event: Dict[str, Any]) -> None:
        """Update current state attributes from moveend event."""
        if "center" in event:
            self._current_center = event["center"]
        if "zoom" in event:
            self._current_zoom = event["zoom"]
        if "bearing" in event:
            self._current_bearing = event["bearing"]
        if "pitch" in event:
            self._current_pitch = event["pitch"]
        if "bounds" in event:
            self._current_bounds = event["bounds"]

    def set_center(self, lng: float, lat: float) -> None:
        """Set the map center coordinates.

        Args:
            lng: Longitude coordinate.
            lat: Latitude coordinate.
        """
        self.center = [lng, lat]
        self._current_center = [lng, lat]

    def set_zoom(self, zoom: float) -> None:
        """Set the map zoom level.

        Args:
            zoom: Zoom level (typically 0-20).
        """
        self.zoom = zoom
        self._current_zoom = zoom

    @property
    def current_center(self) -> List[float]:
        """Get the current map center coordinates as [longitude, latitude]."""
        return self._current_center

    @property
    def current_zoom(self) -> float:
        """Get the current map zoom level."""
        return self._current_zoom

    @property
    def current_bounds(self) -> Optional[List[List[float]]]:
        """Get the current map bounds as [[lng, lat], [lng, lat]] (southwest, northeast)."""
        return self._current_bounds

    @property
    def viewstate(self) -> Dict[str, Any]:
        """Get the current map viewstate including center, zoom, bearing, pitch, and bounds."""
        return {
            "center": self._current_center,
            "zoom": self._current_zoom,
            "bearing": self._current_bearing,
            "pitch": self._current_pitch,
            "bounds": self._current_bounds,
        }

    def add_basemap_control(
        self,
        position: str = "top-right",
        basemaps: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        initial_basemap: Optional[str] = None,
        expand_direction: str = "down",
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a basemap control to the map for switching between different basemaps.

        The basemap control allows users to switch between different basemap providers
        using a dropdown or expandable control. It uses the maplibre-gl-basemaps library.

        Args:
            position: Position on map ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            basemaps: List of basemap names to include. If None, uses a default set.
                     Available basemaps can be found in anymap.basemaps.available_basemaps
            labels: Dictionary mapping basemap names to display labels. If None, uses basemap names.
            initial_basemap: Name of the initial basemap to show. If None, uses the first basemap.
            expand_direction: Direction to expand the control ('up', 'down', 'left', 'right')
            options: Additional options for the basemap control

        Example:
            >>> m = MapLibreMap()
            >>> m.add_basemap_control(
            ...     position="top-right",
            ...     basemaps=["OpenStreetMap.Mapnik", "Esri.WorldImagery", "CartoDB.DarkMatter"],
            ...     labels={"OpenStreetMap.Mapnik": "OpenStreetMap", "Esri.WorldImagery": "Satellite"},
            ...     initial_basemap="OpenStreetMap.Mapnik"
            ... )
        """
        from .basemaps import available_basemaps

        # Default basemaps if none provided
        if basemaps is None:
            basemaps = [
                "OpenStreetMap.Mapnik",
                "Esri.WorldImagery",
                "CartoDB.DarkMatter",
                "CartoDB.Positron",
            ]

        # Filter available basemaps to only include those that exist
        valid_basemaps = [name for name in basemaps if name in available_basemaps]
        if not valid_basemaps:
            raise ValueError(
                f"No valid basemaps found. Available basemaps: {list(available_basemaps.keys())}"
            )

        # Set initial basemap if not provided
        if initial_basemap is None:
            initial_basemap = valid_basemaps[0]
        elif initial_basemap not in valid_basemaps:
            raise ValueError(
                f"Initial basemap '{initial_basemap}' not found in provided basemaps"
            )

        # Create basemap configurations for the control
        basemap_configs = []
        for basemap_name in valid_basemaps:
            basemap_provider = available_basemaps[basemap_name]
            tile_url = basemap_provider.build_url()
            attribution = basemap_provider.get("attribution", "")

            # Use custom label if provided, otherwise use basemap name
            display_label = (
                labels.get(basemap_name, basemap_name) if labels else basemap_name
            )

            basemap_config = {
                "id": basemap_name,
                "tiles": [tile_url],
                "sourceExtraParams": {
                    "tileSize": 256,
                    "attribution": attribution,
                    "minzoom": basemap_provider.get("min_zoom", 0),
                    "maxzoom": basemap_provider.get("max_zoom", 22),
                },
                "label": display_label,
            }
            basemap_configs.append(basemap_config)

        control_options = options or {}
        control_options.update(
            {
                "position": position,
                "basemaps": basemap_configs,
                "initialBasemap": initial_basemap,
                "expandDirection": expand_direction,
            }
        )

        # Store control in persistent state
        control_key = f"basemap_control_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "basemap_control",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self.call_js_method("addControl", "basemap_control", control_options)
