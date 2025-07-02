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
    height = traitlets.Unicode("400px").tag(sync=True)
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
        height: str = "400px",
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
