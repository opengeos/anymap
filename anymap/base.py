"""Base class for interactive map widgets using anywidget.

This module provides the core MapWidget class that serves as the foundation for
all mapping backends in the anymap library. It handles JavaScript communication,
state management, and provides common mapping functionality.
"""

import anywidget
import traitlets
from typing import Dict, List, Any, Optional, Callable, Union


class MapWidget(anywidget.AnyWidget):
    """Base class for interactive map widgets using anywidget.

    This class provides the core functionality for creating interactive maps
    using different JavaScript mapping libraries. It handles communication
    between Python and JavaScript, manages map state, and provides common
    mapping operations.

    Attributes:
        center: Map center coordinates as [longitude, latitude].
        zoom: Map zoom level.
        width: Map container width as CSS string.
        height: Map container height as CSS string.
        style: Map style configuration.
    """

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
    _controls = traitlets.Dict({}).tag(sync=True)
    _projection = traitlets.Dict({}).tag(sync=True)
    _terrain = traitlets.Dict({}).tag(sync=True)

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the map widget.

        Args:
            **kwargs: Additional keyword arguments passed to parent class.
        """
        super().__init__(**kwargs)
        self._event_handlers = {}
        self._js_method_counter = 0

    def call_js_method(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        """Call a JavaScript method on the map instance.

        Args:
            method_name: Name of the JavaScript method to call.
            *args: Positional arguments to pass to the method.
            **kwargs: Keyword arguments to pass to the method.
        """
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

    def on_map_event(
        self, event_type: str, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register a callback for map events.

        Args:
            event_type: Type of event to listen for (e.g., 'click', 'zoom').
            callback: Function to call when the event occurs. Should accept
                     a dictionary containing event data.
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(callback)

    @traitlets.observe("_js_events")
    def _handle_js_events(self, change: Dict[str, Any]) -> None:
        """Handle events from JavaScript.

        Args:
            change: Dictionary containing the change information from traitlets.
        """
        events = change["new"]
        for event in events:
            event_type = event.get("type")
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    handler(event)

    def set_center(self, lng: float, lat: float) -> None:
        """Set the map center coordinates.

        Args:
            lng: Longitude coordinate.
            lat: Latitude coordinate.
        """
        self.center = [lng, lat]

    def set_zoom(self, zoom: float) -> None:
        """Set the map zoom level.

        Args:
            zoom: Zoom level (typically 0-20, where higher values show more detail).
        """
        self.zoom = zoom

    def fly_to(self, lat: float, lng: float, zoom: Optional[float] = None) -> None:
        """Animate the map to fly to a specific location.

        Args:
            lat: Target latitude coordinate.
            lng: Target longitude coordinate.
            zoom: Optional target zoom level. If None, keeps current zoom.
        """
        options = {"center": [lat, lng]}
        if zoom is not None:
            options["zoom"] = zoom
        self.call_js_method("flyTo", options)

    def add_layer(
        self,
        layer_id: str,
        layer_config: Dict[str, Any],
    ) -> None:
        """Add a layer to the map.

        Args:
            layer_id: Unique identifier for the layer.
            layer_config: Dictionary containing layer configuration.
        """
        # Store layer in local state for persistence
        current_layers = dict(self._layers)
        current_layers[layer_id] = layer_config
        self._layers = current_layers

        self.call_js_method("addLayer", layer_config, layer_id)

    def remove_layer(self, layer_id: str) -> None:
        """Remove a layer from the map.

        Args:
            layer_id: Unique identifier of the layer to remove.
        """
        # Remove from local state
        current_layers = dict(self._layers)
        if layer_id in current_layers:
            del current_layers[layer_id]
            self._layers = current_layers

        self.call_js_method("removeLayer", layer_id)

    def add_source(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Add a data source to the map.

        Args:
            source_id: Unique identifier for the data source.
            source_config: Dictionary containing source configuration.
        """
        # Store source in local state for persistence
        current_sources = dict(self._sources)
        current_sources[source_id] = source_config
        self._sources = current_sources

        self.call_js_method("addSource", source_id, source_config)

    def remove_source(self, source_id: str) -> None:
        """Remove a data source from the map.

        Args:
            source_id: Unique identifier of the source to remove.
        """
        # Remove from local state
        current_sources = dict(self._sources)
        if source_id in current_sources:
            del current_sources[source_id]
            self._sources = current_sources

        self.call_js_method("removeSource", source_id)

    def get_layers(self) -> Dict[str, Any]:
        """Get all layers currently on the map.

        Returns:
            Dictionary mapping layer IDs to their configurations.
        """
        return dict(self._layers)

    def get_sources(self) -> Dict[str, Any]:
        """Get all sources currently on the map.

        Returns:
            Dictionary mapping source IDs to their configurations.
        """
        return dict(self._sources)

    def clear_layers(self) -> None:
        """Clear all layers from the map.

        Removes all layers that have been added to the map.
        """
        layer_ids = list(self._layers.keys())
        for layer_id in layer_ids:
            self.remove_layer(layer_id)

    def clear_sources(self) -> None:
        """Clear all sources from the map.

        Removes all data sources that have been added to the map.
        """
        source_ids = list(self._sources.keys())
        for source_id in source_ids:
            self.remove_source(source_id)

    def clear_all(self) -> None:
        """Clear all layers and sources from the map.

        Removes all layers and data sources from the map.
        """
        self.clear_layers()
        self.clear_sources()

    def to_html(
        self,
        filename: Optional[str] = None,
        title: str = "Anymap Export",
        width: str = "100%",
        height: str = "600px",
        **kwargs: Any,
    ) -> str:
        """Export the map to a standalone HTML file.

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
        if hasattr(self, "access_token"):
            map_state["access_token"] = self.access_token
        if hasattr(self, "_draw_data"):
            map_state["_draw_data"] = dict(self._draw_data)

        # Generate HTML content
        html_content = self._generate_html_template(map_state, title, **kwargs)

        # Save to file if filename is provided
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs: Any
    ) -> str:
        """Generate the HTML template with map state.

        This method should be overridden by subclasses to provide library-specific templates.

        Args:
            map_state: Dictionary containing the current map state.
            title: Title for the HTML page.
            **kwargs: Additional arguments for template generation.

        Returns:
            HTML string content.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _generate_html_template")
