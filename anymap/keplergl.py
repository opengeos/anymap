"""KeplerGL implementation of the map widget."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union
import json

from .base import MapWidget

# Load KeplerGL-specific js and css
try:
    with open(
        pathlib.Path(__file__).parent / "static" / "keplergl_widget.js",
        "r",
        encoding="utf-8",
    ) as f:
        _esm_keplergl = f.read()
except FileNotFoundError:
    _esm_keplergl = "console.error('KeplerGL widget JS not found');"

try:
    with open(
        pathlib.Path(__file__).parent / "static" / "keplergl_widget.css",
        "r",
        encoding="utf-8",
    ) as f:
        _css_keplergl = f.read()
except FileNotFoundError:
    _css_keplergl = "/* KeplerGL widget CSS not found */"


class KeplerGLMap(MapWidget):
    """KeplerGL implementation of the map widget."""

    # KeplerGL-specific traits
    map_config = traitlets.Dict({}).tag(sync=True)
    show_docs = traitlets.Bool(False).tag(sync=True)
    read_only = traitlets.Bool(False).tag(sync=True)
    _data = traitlets.Dict({}).tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_keplergl
    _css = _css_keplergl

    def __init__(
        self,
        center: List[float] = [37.7749, -122.4194],
        zoom: float = 9.0,
        width: str = "100%",
        height: str = "600px",
        show_docs: bool = False,
        read_only: bool = False,
        **kwargs,
    ):
        """Initialize KeplerGL map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level
            width: Widget width
            height: Widget height
            show_docs: Whether to show documentation panel
            read_only: Whether the map is read-only
            **kwargs: Additional widget arguments
        """
        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            **kwargs,
        )
        self.show_docs = show_docs
        self.read_only = read_only
        self._initialize_config()

    def _initialize_config(self):
        """Initialize the KeplerGL configuration."""
        self.map_config = {
            "version": "v1",
            "config": {
                "mapState": {
                    "latitude": self.center[0],
                    "longitude": self.center[1],
                    "zoom": self.zoom,
                    "bearing": 0,
                    "pitch": 0,
                    "dragRotate": False,
                    "width": self.width,
                    "height": self.height,
                    "isSplit": False,
                },
                "mapStyle": {
                    "styleType": "dark",
                    "topLayerGroups": {},
                    "visibleLayerGroups": {
                        "label": True,
                        "road": True,
                        "border": False,
                        "building": True,
                        "water": True,
                        "land": True,
                        "3d building": False,
                    },
                    "mapStyles": {},
                },
                "visState": {
                    "layers": [],
                    "interactionConfig": {
                        "tooltip": {"fieldsToShow": {}, "enabled": True},
                        "brush": {"size": 0.5, "enabled": False},
                        "geocoder": {"enabled": False},
                        "coordinate": {"enabled": False},
                    },
                    "filters": [],
                    "layerBlending": "normal",
                    "splitMaps": [],
                    "animationConfig": {"currentTime": None, "speed": 1},
                },
            },
        }

    def add_data(self, data: Union[Dict, List], name: str = "dataset") -> None:
        """Add data to the map.

        Args:
            data: Data to add (GeoJSON, DataFrame, etc.)
            name: Name for the dataset
        """
        # Determine data type and format
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            # GeoJSON data
            data_type = "geojson"
        elif isinstance(data, list):
            # Array of objects (CSV-like data)
            data_type = "csv"
        else:
            # Default to geojson
            data_type = "geojson"

        # Store the data in the widget's internal data structure
        current_data = dict(self._data)
        current_data[name] = {"type": data_type, "data": data}
        self._data = current_data

    def add_geojson(
        self, geojson: Union[str, Dict], layer_name: str = "geojson_layer", **kwargs
    ) -> None:
        """Add GeoJSON data to the map.

        Args:
            geojson: GeoJSON data (dict or file path)
            layer_name: Name for the layer
            **kwargs: Additional layer configuration
        """
        if isinstance(geojson, str):
            # Load from file
            with open(geojson, "r") as f:
                geojson_data = json.load(f)
        else:
            geojson_data = geojson

        # Store the data in the widget's internal data structure
        current_data = dict(self._data)
        current_data[layer_name] = {"type": "geojson", "data": geojson_data}
        self._data = current_data

    def add_csv(
        self, csv_data: Union[str, List[Dict]], layer_name: str = "csv_layer", **kwargs
    ) -> None:
        """Add CSV data to the map.

        Args:
            csv_data: CSV data (file path or list of dictionaries)
            layer_name: Name for the layer
            **kwargs: Additional layer configuration
        """
        if isinstance(csv_data, str):
            # Load from file
            import pandas as pd

            df = pd.read_csv(csv_data)
            csv_data = df.to_dict("records")
        elif isinstance(csv_data, list):
            # Data is already in the correct format (list of dictionaries)
            pass
        else:
            # Convert other formats to list of dictionaries
            csv_data = [csv_data]

        # Store the data in the widget's internal data structure
        current_data = dict(self._data)
        current_data[layer_name] = {"type": "csv", "data": csv_data}
        self._data = current_data

    def set_filter(self, filter_config: Dict[str, Any]) -> None:
        """Set filter configuration.

        Args:
            filter_config: Filter configuration
        """
        self.call_js_method("setFilter", filter_config)

    def update_map_config(self, config: Dict[str, Any]) -> None:
        """Update the map configuration.

        Args:
            config: New configuration to merge
        """

        # Deep merge the configuration
        def deep_merge(dict1, dict2):
            result = dict1.copy()
            for key, value in dict2.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        self.map_config = deep_merge(self.map_config, config)

    def get_map_state(self) -> Dict[str, Any]:
        """Get the current map state.

        Returns:
            Current map state dictionary
        """
        return self.map_config

    def save_config(self, filename: str) -> None:
        """Save the current configuration to a file.

        Args:
            filename: Path to save the configuration
        """
        with open(filename, "w") as f:
            json.dump(self.map_config, f, indent=2)

    def load_config(self, filename: str) -> None:
        """Load configuration from a file.

        Args:
            filename: Path to the configuration file
        """
        with open(filename, "r") as f:
            config = json.load(f)
        self.update_map_config(config)

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs
    ) -> str:
        """Generate HTML template for KeplerGL."""
        # Serialize map state for JavaScript
        map_state_json = json.dumps(map_state, indent=2)

        # Get the current configuration
        config_json = json.dumps(self.map_config, indent=2)

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: sans-serif;
        }}
        #map {{
            width: {map_state.get('width', '100%')};
            height: {map_state.get('height', '600px')};
        }}
        .loading {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
            font-size: 18px;
            color: #555;
        }}
    </style>
</head>
<body>
    <div id="map">
        <div class="loading">Loading KeplerGL Map...</div>
    </div>

    <script src="https://unpkg.com/react@16/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@16/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/redux@3.7.2/dist/redux.js"></script>
    <script src="https://unpkg.com/react-redux@5.1.1/dist/react-redux.min.js"></script>
    <script src="https://unpkg.com/kepler.gl@3.0.0/umd/keplergl.min.js"></script>

    <script>
        // Initialize KeplerGL
        const {{ KeplerGl, injectComponents }} = window.KeplerGl;

        // Map configuration
        const mapConfig = {config_json};
        const mapState = {map_state_json};

        // Create KeplerGL instance
        const App = () => {{
            return React.createElement(KeplerGl, {{
                id: "map",
                width: mapState.width || "100%",
                height: mapState.height || "600px",
                mapboxApiAccessToken: undefined, // Use default map tiles
                initialUiState: mapConfig.config || {{}},
                getMapboxRef: () => {{}},
                onSaveMap: () => {{}},
                onViewStateChange: () => {{}},
                onInteractionStateChange: () => {{}}
            }});
        }};

        // Render the app
        ReactDOM.render(React.createElement(App), document.getElementById('map'));

        // Initialize with data if available
        if (mapState._layers && Object.keys(mapState._layers).length > 0) {{
            // Add layers to the map
            console.log('Adding layers:', mapState._layers);
        }}
    </script>
</body>
</html>"""

        return html_template
