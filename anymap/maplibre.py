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
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import ipywidgets as widgets
import traitlets
from IPython.display import display

from .base import MapWidget

try:
    import geopandas as gpd

    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False
from .maplibre_widgets import Container, LayerManagerWidget
from . import utils

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
    clicked = traitlets.Dict().tag(sync=True)
    _deckgl_layers = traitlets.Dict().tag(sync=True)
    flatgeobuf_layers = traitlets.Dict({}).tag(sync=True)
    geoman_data = traitlets.Dict({"type": "FeatureCollection", "features": []}).tag(
        sync=True
    )

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
            style = utils.construct_maplibre_style(style)

        if abs(center[1]) > 90:
            center = center[::-1]

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
            elif control == "geoman":
                self.add_geoman_control(position=position)
                self.controls[control] = position
            elif control == "export":
                self.add_export_control(position=position)
                self.controls[control] = position
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
        self._widget_control_widgets: Dict[str, widgets.Widget] = {}
        self._flatgeobuf_defaults: Dict[str, Any] = {}
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
        widget: Union[widgets.Widget, List[widgets.Widget]],
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

    def add_flatgeobuf_layer(
        self,
        url: str,
        layer_id: str,
        *,
        layer_type: str = "fill",
        source_id: Optional[str] = None,
        paint: Optional[Dict[str, Any]] = None,
        layout: Optional[Dict[str, Any]] = None,
        filter: Optional[Any] = None,
        bbox: Optional[List[float]] = None,
        promote_id: Optional[Union[str, Dict[str, str]]] = None,
        minzoom: Optional[float] = None,
        maxzoom: Optional[float] = None,
        before_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> str:
        """
        Add a vector layer from a FlatGeobuf dataset.

        The FlatGeobuf file is streamed in the browser and converted to GeoJSON
        before being added to the map. Rendering happens entirely client-side,
        so very large datasets may still impact browser performance.

        Args:
            url: URL pointing to the FlatGeobuf resource.
            layer_id: Unique identifier for the map layer.
            layer_type: MapLibre layer type (e.g., ``'fill'``, ``'line'``, ``'circle'``).
            source_id: Optional custom source identifier. Defaults to ``{layer_id}_source``.
            paint: Optional paint properties dictionary.
            layout: Optional layout properties dictionary.
            filter: Optional MapLibre expression used to filter features.
            bbox: Optional bounding box ``[minX, minY, maxX, maxY]`` used to limit
                features retrieved from the dataset.
            promote_id: Optional feature identifier promotion configuration.
            minzoom: Optional minimum zoom level for the layer.
            maxzoom: Optional maximum zoom level for the layer.
            before_id: Optional layer id to insert the new layer before.
            metadata: Optional metadata dictionary attached to the layer configuration.
            name: Optional friendly name used in the layer manager. Defaults to ``layer_id``.

        Returns:
            str: The identifier of the layer that was registered.
        """

        if source_id is None:
            source_id = f"{layer_id}_source"

        layer_config: Dict[str, Any] = {
            "id": layer_id,
            "type": layer_type,
            "source": source_id,
        }
        if paint:
            layer_config["paint"] = paint
        if layout:
            layer_config["layout"] = layout
        if filter is not None:
            layer_config["filter"] = filter
        if promote_id is not None:
            layer_config["promoteId"] = promote_id
        if minzoom is not None:
            layer_config["minzoom"] = minzoom
        if maxzoom is not None:
            layer_config["maxzoom"] = maxzoom
        if metadata:
            layer_config["metadata"] = metadata

        # Track the layer locally so the layer manager can interact with it.
        current_layers = dict(self._layers)
        current_layers[layer_id] = layer_config
        self._layers = current_layers

        display_name = name or layer_id
        self.layer_dict[layer_id] = {
            "layer": layer_config,
            "opacity": 1.0,
            "visible": True,
            "type": "flatgeobuf",
            "name": display_name,
            "url": url,
        }
        self._update_layer_controls()

        config: Dict[str, Any] = {
            "layerId": layer_id,
            "sourceId": source_id,
            "url": url,
            "layerType": layer_type,
        }
        if paint:
            config["paint"] = paint
        if layout:
            config["layout"] = layout
        if filter is not None:
            config["filter"] = filter
        if bbox is not None:
            config["bbox"] = bbox
        if promote_id is not None:
            config["promoteId"] = promote_id
        if minzoom is not None:
            config["minzoom"] = minzoom
        if maxzoom is not None:
            config["maxzoom"] = maxzoom
        if before_id is not None:
            config["beforeId"] = before_id
        if metadata:
            config["metadata"] = metadata
        if name:
            config["name"] = display_name

        flatgeobuf_layers = dict(self.flatgeobuf_layers)
        flatgeobuf_layers[layer_id] = config
        self.flatgeobuf_layers = flatgeobuf_layers

        return layer_id

    def enable_feature_popup(
        self,
        layer_id: str,
        *,
        fields: Optional[Union[Sequence[str], Dict[str, str]]] = None,
        aliases: Optional[Dict[str, str]] = None,
        title: Optional[str] = None,
        title_field: Optional[str] = None,
        max_properties: int = 25,
        close_button: bool = True,
        max_width: str = "320px",
    ) -> None:
        """
        Enable attribute popups for a layer when users click its features.

        Args:
            layer_id: Identifier of the target layer.
            fields: Optional ordered list of attribute keys to display. When omitted,
                up to ``max_properties`` properties are shown.
            aliases: Optional mapping from attribute key to display label. Only applies
                when ``fields`` is provided.
            title: Optional static string rendered above the attribute table.
            title_field: Optional property key whose value should be used as the popup
                title. Ignored when ``title`` is provided.
            max_properties: Maximum number of properties displayed when ``fields`` is
                not supplied. Defaults to 25.
            close_button: Whether the popup shows a close button. Defaults to True.
            max_width: CSS max-width applied to the popup container. Defaults to 320px.
        """

        alias_lookup: Dict[str, str] = aliases or {}

        field_config: Optional[List[Dict[str, str]]] = None
        if fields is not None:
            if isinstance(fields, dict):
                field_config = [
                    {"name": str(key), "label": str(value)}
                    for key, value in fields.items()
                ]
            else:
                field_config = []
                for name in fields:
                    field_name = str(name)
                    label_source = alias_lookup.get(
                        name, alias_lookup.get(field_name, field_name)
                    )
                    field_config.append(
                        {"name": field_name, "label": str(label_source)}
                    )

        config: Dict[str, Any] = {
            "layerId": layer_id,
            "maxProperties": max_properties,
            "closeButton": close_button,
            "maxWidth": max_width,
        }
        if field_config is not None:
            config["fields"] = field_config
        if title is not None:
            config["title"] = title
        if title_field is not None:
            config["titleField"] = title_field

        self.call_js_method("enableFeaturePopup", config)

    def disable_feature_popup(self, layer_id: str) -> None:
        """
        Disable attribute popups for the specified layer.

        Args:
            layer_id: Identifier of the target layer.
        """

        self.call_js_method("disableFeaturePopup", {"layerId": layer_id})

    def add_widget_control(
        self,
        widget: widgets.Widget,
        *,
        label: str = "Tools",
        icon: str = "⋮",
        position: str = "top-right",
        collapsed: bool = True,
        panel_width: int = 320,
        panel_min_width: int = 220,
        panel_max_width: int = 420,
        control_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """
        Add a collapsible widget control anchored to the map viewport.

        The control displays as a button alongside other MapLibre controls. Clicking
        the button expands a sidebar-style panel that renders the supplied
        ipywidget content.

        Args:
            widget: The ipywidget instance to embed inside the collapsible panel.
            label: Title shown at the top of the expanded panel.
            icon: Text or icon hint shown on the toggle button. Defaults to a vertical ellipsis.
            position: Map control corner (``'top-left'``, ``'top-right'``,
                ``'bottom-left'``, or ``'bottom-right'``).
            collapsed: Whether the panel starts collapsed.
            panel_width: Default panel width in pixels.
            panel_min_width: Minimum panel width in pixels when resized on the front-end.
            panel_max_width: Maximum panel width in pixels when resized on the front-end.
            control_id: Optional identifier used for duplicate detection and later removal.
                If omitted, a unique identifier is generated from the label.
            description: Optional tooltip description for the toggle button.

        Returns:
            str: The unique identifier assigned to the widget control.

        Raises:
            TypeError: If ``widget`` is not an ipywidget instance.
        """
        if not isinstance(widget, widgets.Widget):
            raise TypeError("widget must be an ipywidgets.Widget instance")

        if control_id is None:
            base_slug = "".join(
                char.lower() if char.isalnum() else "-" for char in label
            ).strip("-")
            if not base_slug:
                base_slug = "widget"
            control_id = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # Ensure uniqueness when callers supply their own identifier
        if control_id in self._widget_control_widgets:
            raise ValueError(f"Widget control '{control_id}' already exists")

        widget_id = getattr(widget, "model_id", None)
        if widget_id is None:
            raise ValueError(
                "The supplied widget does not have a model_id. Ensure it is an ipywidget "
                "instance created within the current notebook session."
            )

        control_options: Dict[str, Any] = {
            "position": position,
            "label": label,
            "icon": icon,
            "collapsed": collapsed,
            "panelWidth": panel_width,
            "panelMinWidth": panel_min_width,
            "panelMaxWidth": panel_max_width,
            "control_id": control_id,
            "widget_model_id": widget_id,
        }

        if description:
            control_options["description"] = description

        control_key = f"widget_panel_{control_id}"

        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "widget_panel",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self._widget_control_widgets[control_id] = widget
        self.call_js_method("addControl", "widget_panel", control_options)

        return control_id

    def remove_widget_control(self, control_id: str) -> None:
        """Remove a previously registered widget control."""
        if not control_id:
            raise ValueError("control_id is required")

        current_controls = dict(self._controls)
        target_key = None
        for key, config in current_controls.items():
            if (
                config.get("type") == "widget_panel"
                and config.get("options", {}).get("control_id") == control_id
            ):
                target_key = key
                break

        if target_key:
            current_controls.pop(target_key)
            self._controls = current_controls

        if control_id in self._widget_control_widgets:
            del self._widget_control_widgets[control_id]

        self.call_js_method("removeWidgetControl", control_id)

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
        layer: Dict[str, Any],
        before_id: Optional[str] = None,
        layer_id: str = None,
        opacity: Optional[float] = 1.0,
        visible: Optional[bool] = True,
        overwrite: bool = False,
        **kwargs: Any,
    ) -> None:
        """Add a layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            layer_config: Layer configuration dictionary containing
                         properties like type, source, paint, and layout.
            before_id: Optional layer ID to insert this layer before.
                      If None, layer is added on top.
        """

        if isinstance(layer, dict):
            if "minzoom" in layer:
                layer["min-zoom"] = layer.pop("minzoom")
            if "maxzoom" in layer:
                layer["max-zoom"] = layer.pop("maxzoom")
            layer = utils.replace_top_level_hyphens(layer)

        if "name" in kwargs and layer_id is None:
            layer_id = kwargs.pop("name")

        if layer_id is None:
            layer_id = utils.get_unique_name(
                layer["id"], list(self._layers.keys()), overwrite
            )

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

        self.add_layer(layer=layer_config, before_id=before_id, layer_id=layer_id)

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

        self.add_layer(layer=layer_config, before_id=before_id, layer_id=layer_id)

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

        self.add_layer(layer=layer_config, before_id=before_id, layer_id=layer_id)

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

        self.add_layer(layer=layer_config, before_id=before_id, layer_id=layer_id)

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

    def add_export_control(
        self,
        position: str = "top-right",
        filename: str = "map",
        page_size: Optional[Sequence[Union[int, float]]] = None,
        page_orientation: str = "landscape",
        default_format: str = "pdf",
        dpi: int = 300,
        allowed_sizes: Optional[Sequence[str]] = None,
        crosshair: bool = False,
        printable_area: bool = False,
        locale: str = "en",
        options: Optional[Dict[str, Any]] = None,
        collapsed: bool = True,
    ) -> None:
        """Add an export control for saving the map as images or PDF.

        This control leverages the `@watergis/maplibre-gl-export` plugin to provide an
        interactive, collapsible button that lets users export the current map view as
        PNG, JPEG, PDF, or SVG files. The control appears alongside other MapLibre
        controls and opens a small panel when toggled.

        Args:
            position: Placement of the control on the map container.
            filename: Default filename (without extension) suggested for exports.
            page_size: Size of the export page in millimetres as [width, height]. If
                omitted, the plugin defaults to A4.
            page_orientation: Page orientation, either ``"landscape"`` or ``"portrait"``.
            default_format: Default export format (``"pdf"``, ``"png"``, ``"jpg"``, ``"svg"``).
            dpi: Dots per inch used when rendering the export.
            allowed_sizes: Optional whitelist of page sizes (e.g. ``["A4", "LETTER"]``).
            crosshair: Whether to show the crosshair overlay when the panel is open.
            printable_area: Whether to show the printable area overlay when the panel is open.
            locale: Two-letter locale code for the control's UI language.
            options: Extra keyword arguments forwarded to the export plugin.
            collapsed: Whether the control should start collapsed (button only).
        """

        orientation_value = page_orientation.lower()
        if orientation_value not in {"landscape", "portrait"}:
            raise ValueError("page_orientation must be 'landscape' or 'portrait'")

        format_value = default_format.lower()
        if format_value not in {"png", "jpg", "jpeg", "pdf", "svg"}:
            raise ValueError(
                "default_format must be one of {'png', 'jpg', 'jpeg', 'pdf', 'svg'}"
            )
        # Normalise JPEG alias
        if format_value == "jpeg":
            format_value = "jpg"

        control_options: Dict[str, Any] = dict(options or {})
        clean_filename = (
            filename.strip() if isinstance(filename, str) else str(filename)
        )
        clean_locale = (
            locale.strip().lower() if isinstance(locale, str) else str(locale).lower()
        )

        control_options["position"] = position
        control_options.setdefault("Filename", clean_filename or "map")
        control_options.setdefault("PageOrientation", orientation_value)
        control_options.setdefault("Format", format_value)
        control_options.setdefault("DPI", int(dpi))
        control_options.setdefault("Crosshair", bool(crosshair))
        control_options.setdefault("PrintableArea", bool(printable_area))
        control_options.setdefault("Locale", clean_locale or "en")
        control_options["collapsed"] = collapsed

        if page_size is not None:
            page_size_values = list(page_size)
            if len(page_size_values) != 2:
                raise ValueError(
                    "page_size must contain exactly two values [width, height]"
                )
            control_options["PageSize"] = [
                float(page_size_values[0]),
                float(page_size_values[1]),
            ]

        if allowed_sizes is not None:
            control_options["AllowedSizes"] = [
                size.upper() for size in allowed_sizes if isinstance(size, str)
            ]

        control_key = f"export_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "export",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls

        self.call_js_method("addControl", "export", control_options)

    def add_geoman_control(
        self,
        position: str = "top-left",
        geoman_options: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        controls: Optional[Dict[str, Any]] = None,
        collapsed: Optional[bool] = False,
    ) -> None:
        """Add the MapLibre-Geoman drawing and editing toolkit.

        Args:
            position: Where to dock the Geoman toolbar on the map.
            geoman_options: Raw configuration dictionary passed directly to the
                ``Geoman`` constructor.
            settings: Optional convenience overrides merged into
                ``geoman_options['settings']``.
            controls: Optional overrides for toolbar sections such as ``draw``,
                ``edit``, or ``helper``. Each key should map to a dictionary of
                button configuration overrides.
            collapsed: Whether the toolbar UI should start collapsed. Use
                ``None`` to defer to the underlying configuration.
        """

        geoman_config: Dict[str, Any] = dict(geoman_options or {})

        if settings:
            geoman_settings = geoman_config.setdefault("settings", {})
            geoman_settings.update(settings)

        if controls:
            geoman_controls = geoman_config.setdefault("controls", {})
            for section, section_options in controls.items():
                if isinstance(section_options, dict):
                    section_config = geoman_controls.setdefault(section, {})
                    section_config.update(section_options)
                else:
                    geoman_controls[section] = section_options

        if collapsed is not None:
            geoman_settings = geoman_config.setdefault("settings", {})
            geoman_settings.setdefault("controlsCollapsible", True)
            geoman_settings["controlsUiEnabledByDefault"] = False if collapsed else True

        control_options: Dict[str, Any] = {"position": position}
        if geoman_config:
            control_options["geoman_options"] = geoman_config
        if collapsed is not None:
            control_options["collapsed"] = bool(collapsed)

        control_key = f"geoman_{position}"
        current_controls = dict(self._controls)
        current_controls[control_key] = {
            "type": "geoman",
            "position": position,
            "options": control_options,
        }
        self._controls = current_controls
        self.controls["geoman"] = position

        self.call_js_method("addControl", "geoman", control_options)

    def remove_geoman_control(self, position: str = "top-left") -> None:
        """Remove the Geoman control toolbar."""

        control_key = f"geoman_{position}"
        current_controls = dict(self._controls)
        if control_key in current_controls:
            current_controls.pop(control_key)
            self._controls = current_controls
        self.controls.pop("geoman", None)
        self.call_js_method("removeControl", "geoman", position)

    def set_geoman_data(self, data: Dict[str, Any]) -> None:
        """Replace the current Geoman feature collection."""

        self.geoman_data = data or {"type": "FeatureCollection", "features": []}

    def clear_geoman_data(self) -> None:
        """Clear all Geoman-managed features."""

        self.set_geoman_data({"type": "FeatureCollection", "features": []})

    def get_geoman_data(
        self,
    ) -> Dict[str, Any]:
        """Return the current Geoman feature collection.

        Returns:
            A GeoJSON FeatureCollection containing all Geoman-managed features.

        """

        return self.geoman_data

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
            api_key = utils.get_env_var("GOOGLE_MAPS_API_KEY")
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

        # Remove FlatGeobuf metadata if present
        if layer_id in self.flatgeobuf_layers:
            self.call_js_method("removeFlatGeobufLayer", layer_id)
            flatgeobuf_layers = dict(self.flatgeobuf_layers)
            del flatgeobuf_layers[layer_id]
            self.flatgeobuf_layers = flatgeobuf_layers

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
        titiler_endpoint: Optional[str] = None,
        fit_bounds: bool = True,
        **kwargs: Any,
    ) -> None:
        """Add a Cloud Optimized GeoTIFF (COG) layer to the map.

        This method supports COGs in any coordinate reference system (CRS). For COGs
        in EPSG:3857, it uses the maplibre-cog-protocol for direct rendering. For COGs
        in other CRS, it uses TiTiler to reproject on-the-fly.

        Args:
            layer_id: Unique identifier for the COG layer.
            cog_url: URL to the COG file.
            opacity: Layer opacity between 0.0 and 1.0.
            visible: Whether the layer should be visible initially.
            paint: Optional paint properties for the layer.
            before_id: Optional layer ID to insert this layer before.
            titiler_endpoint: Optional TiTiler endpoint URL. If None, checks COG CRS
                and uses TiTiler automatically for non-EPSG:3857 COGs. Set to a TiTiler
                URL (e.g., "https://giswqs-titiler-endpoint.hf.space") to force using TiTiler.
            fit_bounds: If True, automatically fit map bounds to COG extent.
            **kwargs: Additional parameters passed to TiTiler (e.g., rescale, colormap,
                bidx for band selection).

        Example:
            >>> m = MapLibreMap()
            >>> # COG in EPSG:3857 (uses cog:// protocol)
            >>> m.add_cog_layer("cog1", "https://example.com/data_3857.tif")
            >>>
            >>> # COG in any other CRS (uses TiTiler)
            >>> m.add_cog_layer("cog2", "https://example.com/data_4326.tif")
            >>>
            >>> # Force TiTiler with custom endpoint
            >>> m.add_cog_layer(
            ...     "cog3",
            ...     "https://example.com/data.tif",
            ...     titiler_endpoint="https://giswqs-titiler-endpoint.hf.space",
            ...     rescale="0,255",
            ...     colormap="viridis"
            ... )
        """
        source_id = f"{layer_id}_source"

        # Check if we should use TiTiler
        use_titiler = titiler_endpoint is not None

        if not use_titiler:
            # Auto-detect if TiTiler is needed by checking COG CRS
            try:
                metadata = self.get_cog_metadata(cog_url, crs=None)
                if metadata and metadata.get("crs"):
                    cog_crs = metadata["crs"]
                    # Use TiTiler if COG is not in EPSG:3857
                    if cog_crs != "EPSG:3857":
                        use_titiler = True
                        print(f"COG is in {cog_crs}, using TiTiler for reprojection")
            except Exception as e:
                print(f"Could not determine COG CRS, trying cog:// protocol: {e}")

        if use_titiler:
            # Use TiTiler for on-the-fly reprojection
            if titiler_endpoint is None:
                titiler_endpoint = "https://giswqs-titiler-endpoint.hf.space"

            # Build TiTiler tile URL
            from urllib.parse import urlencode, quote

            # Encode the COG URL
            encoded_url = quote(cog_url, safe="")

            # Build query parameters
            params = {
                "url": cog_url,
                "TileMatrixSetId": "WebMercatorQuad",  # Reproject to Web Mercator
            }

            # Add any additional TiTiler parameters
            for key, value in kwargs.items():
                params[key] = value

            query_string = urlencode({k: v for k, v in params.items() if k != "url"})

            # TiTiler tile URL format: {endpoint}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}
            tile_url = f"{titiler_endpoint}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}?url={encoded_url}"
            if query_string:
                tile_url += f"&{query_string}"

            # print(f"Using TiTiler: {titiler_endpoint}")
            # print(f"Tile URL pattern: {tile_url[:100]}...")

            self.add_source(
                source_id,
                {
                    "type": "raster",
                    "tiles": [tile_url],
                    "tileSize": 256,
                    "attribution": "TiTiler",
                },
            )

        else:
            # Use cog:// protocol for EPSG:3857 COGs
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
            layer=layer_config,
            before_id=before_id,
            layer_id=layer_id,
            opacity=opacity,
            visible=visible,
        )

        # Optionally fit bounds to COG extent
        if fit_bounds:
            try:
                metadata = self.get_cog_metadata(cog_url, crs="EPSG:4326")
                if metadata and metadata.get("bbox"):
                    bbox = metadata["bbox"]
                    bounds = [[bbox[0], bbox[1]], [bbox[2], bbox[3]]]
                    self.fit_bounds(bounds, padding=50)
                    # print(f"Map fitted to COG bounds: {bounds}")
            except Exception as e:
                print(f"Could not fit bounds to COG extent: {e}")

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
                layer=layer_config,
                before_id=before_id,
                layer_id=layer_config["id"],
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
        preserve_selection_on_edit: bool = True,
        styles: Optional[List[Dict[str, Any]]] = None,
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
            preserve_selection_on_edit: Whether to keep features selected during vertex editing/moving.
                                       If True, features remain selected after editing. If False, uses
                                       default MapboxDraw behavior (deselection after edit).
            styles: Optional list of custom MapboxDraw style objects. If None, uses default styles.
                   Each style should be a dict with 'id', 'type', 'filter', and 'paint'/'layout' properties.
                   See MapboxDraw documentation for style object format.
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
            "preserveSelectionOnEdit": preserve_selection_on_edit,
            "customStyles": styles,
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

    # Draw styles moved to draw_styles.py module

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

    def add_draw_data(self, geojson_data: Union[Dict[str, Any], str]) -> None:
        """Add GeoJSON features to the existing draw control data.

        This method appends new features to the draw control without clearing
        existing drawn features, unlike load_draw_data which replaces all data.

        Args:
            geojson_data: GeoJSON data as dictionary or JSON string. Can be a
                         FeatureCollection or a single Feature.
        """
        if isinstance(geojson_data, str):
            geojson_data = json.loads(geojson_data)

        # Normalize input to FeatureCollection if it's a single Feature
        if geojson_data.get("type") == "Feature":
            geojson_data = {"type": "FeatureCollection", "features": [geojson_data]}

        # Send to JavaScript - it will handle adding features and syncing back the data
        self.call_js_method("addDrawData", geojson_data)

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

    @property
    def draw_data(self) -> Dict[str, Any]:
        """Get the current draw data as GeoJSON."""
        return self.get_draw_data()

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

    def save_draw_data(self, filepath: str, driver: Optional[str] = None) -> None:
        """Save drawn features to a file in various formats.

        Args:
            filepath: Path where to save the file. The file extension determines
                     the output format if driver is not specified.
            driver: GeoPandas driver name (e.g., 'GeoJSON', 'ESRI Shapefile', 'GPKG').
                   If None, inferred from file extension.

        Raises:
            ImportError: If geopandas is not installed.
            ValueError: If no drawn features exist or invalid driver/format.

        Note:
            For shapefiles, all features must have the same geometry type.
            Use GeoJSON or GPKG formats for mixed geometry types.
        """
        if not HAS_GEOPANDAS:
            raise ImportError(
                "geopandas is required for save_draw_data. "
                "Install it with: pip install geopandas"
            )

        # Get the drawn features
        draw_data = self.get_draw_data()

        if not draw_data or not draw_data.get("features"):
            raise ValueError("No drawn features to save")

        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(draw_data["features"])

        # Set a default CRS if not present
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)

        # Save to file
        try:
            gdf.to_file(filepath, driver=driver)
        except Exception as e:
            # Provide helpful error message for common shapefile issues
            if "shapefile" in str(e).lower() or (
                driver and "shapefile" in driver.lower()
            ):
                geometry_types = gdf.geometry.geom_type.unique()
                if len(geometry_types) > 1:
                    raise ValueError(
                        f"Cannot save mixed geometry types {list(geometry_types)} to shapefile. "
                        "Use GeoJSON (.geojson) or GeoPackage (.gpkg) format instead."
                    ) from e
            raise e

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

    def get_cog_metadata(
        self, url: str, crs: str = "EPSG:4326"
    ) -> Optional[Dict[str, Any]]:
        """Retrieve metadata from a Cloud Optimized GeoTIFF (COG) file.

        This method fetches metadata from a COG file. It uses rasterio if available,
        which provides comprehensive metadata extraction capabilities.

        Note:
            This feature corresponds to the getCogMetadata function in maplibre-cog-protocol,
            which is marked as [unstable]. Some metadata internals may change in future releases.

        Args:
            url (str): The URL of the COG file to retrieve metadata from.
            crs (str, optional): The coordinate reference system to use for the output bbox.
                Defaults to "EPSG:4326" (WGS84 lat/lon). Set to None to use the COG's native CRS.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing COG metadata with keys such as:
                - bbox: Bounding box coordinates [west, south, east, north] in the specified CRS
                - bounds: BoundingBox in native CRS
                - width: Width of the raster in pixels
                - height: Height of the raster in pixels
                - crs: Original coordinate reference system of the COG
                - output_crs: CRS of the returned bbox
                - transform: Affine transformation matrix
                - count: Number of bands
                - dtypes: Data types for each band
                - nodata: NoData value
                - scale: Scale value (if available)
                - offset: Offset value (if available)
            Returns None if metadata retrieval fails.

        Example:
            >>> m = MapLibreMap()
            >>> url = "https://example.com/data.tif"
            >>> # Get metadata with bbox in WGS84 (default)
            >>> metadata = m.get_cog_metadata(url)
            >>> if metadata:
            ...     print(f"Bounding box (WGS84): {metadata.get('bbox')}")
            ...     # Fit bounds using WGS84 coordinates
            ...     bbox = metadata['bbox']
            ...     m.fit_bounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]])
            >>>
            >>> # Get metadata in native CRS
            >>> metadata = m.get_cog_metadata(url, crs=None)
            >>> if metadata:
            ...     print(f"Native CRS: {metadata.get('crs')}")
        """
        return utils.get_cog_metadata(url, crs=crs)

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

    def _process_deckgl_props(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """Process DeckGL properties to handle lambda functions and other non-serializable objects.

        Args:
            props: Dictionary of DeckGL layer properties.

        Returns:
            Processed properties dictionary with serializable values.
        """
        processed_props = {}

        for key, value in props.items():
            if callable(value):
                # Handle lambda functions and other callables
                if hasattr(value, "__name__") and value.__name__ == "<lambda>":
                    # For lambda functions, we'll need to convert them to accessor strings
                    # This is a simplified approach - in practice, you might want to
                    # inspect the lambda to generate appropriate accessors
                    processed_props[key] = f"@@=d => d.{key.replace('get', '').lower()}"
                else:
                    # For named functions, convert to string representation
                    processed_props[key] = str(value)
            else:
                # Keep other values as-is
                processed_props[key] = value

        return processed_props

    def add_deckgl_layer(
        self,
        layer_id: str,
        layer_type: str,
        data: Union[List[Dict], Dict[str, Any]],
        props: Optional[Dict[str, Any]] = None,
        visible: bool = True,
        **kwargs: Any,
    ) -> None:
        """Add a DeckGL layer to the map.

        This method adds a DeckGL layer overlay to the MapLibre map. DeckGL provides
        high-performance visualization of large datasets with WebGL-powered layers.

        Args:
            layer_id: Unique identifier for the DeckGL layer.
            layer_type: Type of DeckGL layer (e.g., 'ScatterplotLayer', 'PathLayer', 'GeoJsonLayer').
            data: Data for the layer. Can be a list of objects or GeoJSON-like structure.
            props: Layer-specific properties for styling and behavior.
            visible: Whether the layer should be visible initially.
            **kwargs: Additional layer properties.

        Example:
            >>> m = MapLibreMap()
            >>>
            >>> # Add a scatterplot layer
            >>> data = [
            ...     {"position": [-122.4, 37.8], "radius": 100, "color": [255, 0, 0]},
            ...     {"position": [-74.0, 40.7], "radius": 150, "color": [0, 255, 0]}
            ... ]
            >>> m.add_deckgl_layer(
            ...     "my_points",
            ...     "ScatterplotLayer",
            ...     data,
            ...     props={
            ...         "getPosition": "position",
            ...         "getRadius": "radius",
            ...         "getFillColor": "color",
            ...         "pickable": True
            ...     }
            ... )
        """
        if props is None:
            props = {}

        # Merge kwargs into props
        layer_props = {**props, **kwargs}

        # Convert lambda functions to JavaScript-compatible strings
        layer_props = self._process_deckgl_props(layer_props)

        layer_config = {
            "id": layer_id,
            "type": layer_type,
            "data": data,
            "props": layer_props,
            "visible": visible,
        }

        # Store layer in local state
        current_layers = dict(self._deckgl_layers)
        current_layers[layer_id] = layer_config
        self._deckgl_layers = current_layers

        # Send to JavaScript
        self.call_js_method("addDeckGLLayer", layer_config)

    def remove_deckgl_layer(self, layer_id: str) -> None:
        """Remove a DeckGL layer from the map.

        Args:
            layer_id: Unique identifier of the DeckGL layer to remove.
        """
        # Remove from local state
        if layer_id in self._deckgl_layers:
            current_layers = dict(self._deckgl_layers)
            del current_layers[layer_id]
            self._deckgl_layers = current_layers

        # Send to JavaScript
        self.call_js_method("removeDeckGLLayer", layer_id)

    def update_deckgl_layer(
        self,
        layer_id: str,
        data: Optional[Union[List[Dict], Dict[str, Any]]] = None,
        props: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Update a DeckGL layer's data or properties.

        Args:
            layer_id: Unique identifier of the DeckGL layer to update.
            data: New data for the layer. If None, data is not updated.
            props: New or updated properties for the layer.
            **kwargs: Additional layer properties to update.
        """
        if layer_id not in self._deckgl_layers:
            raise ValueError(f"DeckGL layer '{layer_id}' not found")

        # Get current layer config
        current_layers = dict(self._deckgl_layers)
        layer_config = current_layers[layer_id].copy()

        # Update data if provided
        if data is not None:
            layer_config["data"] = data

        # Update properties if provided
        if props is not None or kwargs:
            current_props = layer_config.get("props", {})
            if props:
                current_props.update(props)
            if kwargs:
                current_props.update(kwargs)
            # Process the updated props to handle lambda functions
            layer_config["props"] = self._process_deckgl_props(current_props)

        # Store updated config
        current_layers[layer_id] = layer_config
        self._deckgl_layers = current_layers

        # Send to JavaScript
        self.call_js_method("updateDeckGLLayer", layer_config)

    def set_deckgl_layer_visibility(self, layer_id: str, visible: bool) -> None:
        """Set the visibility of a DeckGL layer.

        Args:
            layer_id: Unique identifier of the DeckGL layer.
            visible: Whether the layer should be visible.
        """
        if layer_id in self._deckgl_layers:
            current_layers = dict(self._deckgl_layers)
            current_layers[layer_id]["visible"] = visible
            self._deckgl_layers = current_layers

            # Send to JavaScript
            self.call_js_method("setDeckGLLayerVisibility", layer_id, visible)

    def get_deckgl_layers(self) -> Dict[str, Dict[str, Any]]:
        """Get all DeckGL layers currently on the map.

        Returns:
            Dictionary mapping layer IDs to their configurations.
        """
        return dict(self._deckgl_layers)

    def clear_deckgl_layers(self) -> None:
        """Remove all DeckGL layers from the map."""
        # Clear local state
        self._deckgl_layers = {}

        # Send to JavaScript
        self.call_js_method("clearDeckGLLayers")

    def to_html(
        self,
        filename: Optional[str] = None,
        title: str = "Anymap Export",
        width: str = "100%",
        height: str = "600px",
        **kwargs: Any,
    ) -> str:
        """Export the map to a standalone HTML file with DeckGL layers.

        This method extends the base to_html method to include DeckGL layer state.

        Args:
            filename: Optional filename to save the HTML. If None, returns HTML string.
            title: Title for the HTML page.
            width: Width of the map container as CSS string.
            height: Height of the map container as CSS string.
            **kwargs: Additional arguments passed to the HTML template.

        Returns:
            HTML string content of the exported map.
        """
        # Get the current map state
        map_state = {
            "center": self.center,
            "zoom": self.zoom,
            "width": width,
            "height": height,
            "style": self.style,
            "_layers": dict(self._layers),
            "_sources": dict(self._sources),
            "_controls": dict(self._controls),
            "_terrain": dict(self._terrain),
            "_deckgl_layers": dict(self._deckgl_layers),  # Include DeckGL layers
        }

        # Add class-specific attributes
        if hasattr(self, "style"):
            map_state["style"] = self.style
        if hasattr(self, "bearing"):
            map_state["bearing"] = self.bearing
        if hasattr(self, "pitch"):
            map_state["pitch"] = self.pitch
        if hasattr(self, "antialias"):
            map_state["antialias"] = self.antialias
        if hasattr(self, "_draw_data"):
            map_state["_draw_data"] = dict(self._draw_data)
        if hasattr(self, "_terra_draw_data"):
            map_state["_terra_draw_data"] = dict(self._terra_draw_data)

        # Generate HTML content
        html_content = self._generate_html_template(map_state, title, **kwargs)

        # Save to file if filename provided
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content
