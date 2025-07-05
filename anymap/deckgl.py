"""DeckGL implementation of the map widget that extends MapLibre."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union
import json

from .maplibre import MapLibreMap

# Load DeckGL-specific js and css
with open(
    pathlib.Path(__file__).parent / "static" / "deckgl_widget.js", "r", encoding="utf-8"
) as f:
    _esm_deckgl = f.read()

with open(
    pathlib.Path(__file__).parent / "static" / "deckgl_widget.css",
    "r",
    encoding="utf-8",
) as f:
    _css_deckgl = f.read()


class DeckGLMap(MapLibreMap):
    """DeckGL implementation of the map widget that extends MapLibre."""

    # DeckGL-specific traits
    deckgl_layers = traitlets.List([]).tag(sync=True)
    controller_options = traitlets.Dict({}).tag(sync=True)

    # Override the JavaScript module
    _esm = _esm_deckgl
    _css = _css_deckgl

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        style: str = "https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json",
        width: str = "100%",
        height: str = "600px",
        bearing: float = 0.0,
        pitch: float = 0.0,
        controller_options: Dict[str, Any] = None,
        **kwargs,
    ):
        """Initialize DeckGL map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level
            style: MapLibre style URL or style object
            width: Widget width
            height: Widget height
            bearing: Map bearing (rotation) in degrees
            pitch: Map pitch (tilt) in degrees
            controller_options: DeckGL controller options
        """
        super().__init__(
            center=center,
            zoom=zoom,
            style=style,
            width=width,
            height=height,
            bearing=bearing,
            pitch=pitch,
            **kwargs,
        )

        if controller_options is None:
            controller_options = {"doubleClickZoom": False}
        self.controller_options = controller_options

    def add_deckgl_layer(self, layer_config: Dict[str, Any]) -> None:
        """Add a DeckGL layer to the map.

        Args:
            layer_config: DeckGL layer configuration dictionary
        """
        current_layers = list(self.deckgl_layers)
        current_layers.append(layer_config)
        self.deckgl_layers = current_layers

    def remove_deckgl_layer(self, layer_id: str) -> None:
        """Remove a DeckGL layer from the map.

        Args:
            layer_id: ID of the layer to remove
        """
        current_layers = [
            layer for layer in self.deckgl_layers if layer.get("id") != layer_id
        ]
        self.deckgl_layers = current_layers

    def clear_deckgl_layers(self) -> None:
        """Clear all DeckGL layers from the map."""
        self.deckgl_layers = []

    def add_geojson_layer(
        self,
        layer_id: str,
        geojson_data: Dict[str, Any],
        layer_type: str = "GeoJsonLayer",
        **layer_props,
    ) -> None:
        """Add a GeoJSON layer using DeckGL.

        Args:
            layer_id: Unique identifier for the layer
            geojson_data: GeoJSON data
            layer_type: DeckGL layer type (e.g., 'GeoJsonLayer')
            **layer_props: Additional DeckGL layer properties
        """
        layer_config = {
            "@@type": layer_type,
            "id": layer_id,
            "data": geojson_data,
            "pickable": True,
            "autoHighlight": True,
            **layer_props,
        }
        self.add_deckgl_layer(layer_config)

    def add_arc_layer(
        self,
        layer_id: str,
        data: Union[str, List[Dict[str, Any]]],
        get_source_position: Union[List[float], str] = None,
        get_target_position: Union[List[float], str] = None,
        **layer_props,
    ) -> None:
        """Add an Arc layer using DeckGL.

        Args:
            layer_id: Unique identifier for the layer
            data: Data source (URL or array of objects)
            get_source_position: Source position accessor (coordinates or accessor function)
            get_target_position: Target position accessor (coordinates or accessor function)
            **layer_props: Additional DeckGL layer properties
        """
        layer_config = {
            "@@type": "ArcLayer",
            "id": layer_id,
            "data": data,
            "pickable": True,
            "autoHighlight": True,
            **layer_props,
        }

        if get_source_position:
            layer_config["getSourcePosition"] = get_source_position
        if get_target_position:
            layer_config["getTargetPosition"] = get_target_position

        self.add_deckgl_layer(layer_config)

    def add_scatterplot_layer(
        self,
        layer_id: str,
        data: Union[str, List[Dict[str, Any]]],
        get_position: List[float] = None,
        get_radius: Union[int, List[int]] = 100,
        get_fill_color: List[int] = [255, 140, 0, 160],
        **layer_props,
    ) -> None:
        """Add a Scatterplot layer using DeckGL.

        Args:
            layer_id: Unique identifier for the layer
            data: Data source (URL or array of objects)
            get_position: Position accessor
            get_radius: Radius accessor
            get_fill_color: Fill color accessor
            **layer_props: Additional DeckGL layer properties
        """
        layer_config = {
            "@@type": "ScatterplotLayer",
            "id": layer_id,
            "data": data,
            "pickable": True,
            "autoHighlight": True,
            "radiusMinPixels": 2,
            "radiusMaxPixels": 100,
            "getRadius": get_radius,
            "getFillColor": get_fill_color,
            **layer_props,
        }

        if get_position:
            layer_config["getPosition"] = get_position

        self.add_deckgl_layer(layer_config)

    def to_html(
        self,
        filename: Optional[str] = None,
        title: str = "DeckGL Map Export",
        width: str = "100%",
        height: str = "600px",
        **kwargs,
    ) -> str:
        """Export the DeckGL map to a standalone HTML file.

        Args:
            filename: Optional filename to save the HTML. If None, returns HTML string.
            title: Title for the HTML page
            width: Width of the map container
            height: Height of the map container
            **kwargs: Additional arguments passed to the HTML template

        Returns:
            HTML string content
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
            "deckgl_layers": list(self.deckgl_layers),  # Include DeckGL layers
            "controller_options": dict(self.controller_options),
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

        # Generate HTML content
        html_content = self._generate_html_template(map_state, title, **kwargs)

        # Save to file if filename is provided
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs
    ) -> str:
        """Generate HTML template for DeckGL."""
        # Serialize map state for JavaScript
        map_state_json = json.dumps(map_state, indent=2)

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://unpkg.com/deck.gl@9.1.12/dist.min.js"></script>
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

        // Parse DeckGL layers from configuration
        function parseDeckGLLayers(layerConfigs) {{
            // Helper function to convert accessor expressions to functions
            function parseAccessor(accessor) {{
                if (typeof accessor === 'string' && accessor.startsWith('@@=')) {{
                    const expression = accessor.substring(3); // Remove '@@=' prefix

                    try {{
                        // Handle arrow function expressions directly
                        if (expression.includes('=>')) {{
                            // This is already an arrow function, just evaluate it
                            return eval(`(${{expression}})`);
                        }}
                        // Create a function from the expression
                        // Handle different variable contexts (d = data item, f = feature, etc.)
                        else if (expression.includes('f.geometry.coordinates')) {{
                            return new Function('f', `return ${{expression}}`);
                        }} else if (expression.includes('f.properties')) {{
                            return new Function('f', `return ${{expression}}`);
                        }} else if (expression.includes('d.features')) {{
                            // For dataTransform functions
                            return new Function('d', `return ${{expression}}`);
                        }} else if (expression.includes('d.')) {{
                            return new Function('d', `return ${{expression}}`);
                        }} else {{
                            // Default context
                            return new Function('d', `return ${{expression}}`);
                        }}
                    }} catch (error) {{
                        console.warn('Failed to parse accessor expression:', accessor, error);
                        return accessor; // Return original if parsing fails
                    }}
                }}
                return accessor;
            }}

            // Helper function to process layer properties and convert accessors
            function processLayerProps(props) {{
                const processed = {{ ...props }};

                // List of properties that should be treated as accessors
                const accessorProps = [
                    'getSourcePosition', 'getTargetPosition', 'getPosition',
                    'getRadius', 'getFillColor', 'getLineColor', 'getWidth',
                    'getPointRadius', 'dataTransform'
                ];

                accessorProps.forEach(prop => {{
                    if (prop in processed) {{
                        processed[prop] = parseAccessor(processed[prop]);
                    }}
                }});

                return processed;
            }}

            return layerConfigs.map(config => {{
                const layerType = config["@@type"];
                const layerProps = processLayerProps({{ ...config }});
                delete layerProps["@@type"];

                try {{
                    switch (layerType) {{
                        case "GeoJsonLayer":
                            return new deck.GeoJsonLayer(layerProps);
                        case "ArcLayer":
                            return new deck.ArcLayer(layerProps);
                        case "ScatterplotLayer":
                            return new deck.ScatterplotLayer(layerProps);
                        default:
                            console.warn(`Unknown DeckGL layer type: ${{layerType}}`);
                            return null;
                    }}
                }} catch (error) {{
                    console.error(`Error creating ${{layerType}}:`, error, layerProps);
                    return null;
                }}
            }}).filter(layer => layer !== null);
        }}

        // Initialize DeckGL with MapLibre
        const deckgl = new deck.DeckGL({{
            container: 'map',
            mapStyle: mapState.style || 'https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json',
            initialViewState: {{
                latitude: mapState.center[0],
                longitude: mapState.center[1],
                zoom: mapState.zoom || 2,
                bearing: mapState.bearing || 0,
                pitch: mapState.pitch || 0
            }},
            controller: true,
            layers: parseDeckGLLayers(mapState.deckgl_layers || []),
            onViewStateChange: ({{viewState}}) => {{
                console.log('View state changed:', viewState);
            }},
            onClick: (info) => {{
                if (info.object) {{
                    console.log('Clicked object:', info.object);
                    if (info.object.properties && info.object.properties.name) {{
                        alert(`${{info.object.properties.name}} (${{info.object.properties.abbrev || 'N/A'}})`);
                    }}
                }}
            }}
        }});

        // Add navigation controls styling
        const mapContainer = document.getElementById('map');
        mapContainer.style.position = 'relative';

        console.log('DeckGL map initialized successfully');
        console.log('Loaded layers:', mapState.deckgl_layers ? mapState.deckgl_layers.length : 0);
    </script>
</body>
</html>"""

        return html_template
