"""OpenLayers implementation of the map widget."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union
import json

from .base import MapWidget

# Load OpenLayers-specific js and css
try:
    with open(
        pathlib.Path(__file__).parent / "static" / "openlayers_widget.js", "r"
    ) as f:
        _esm_openlayers = f.read()
except FileNotFoundError:
    _esm_openlayers = "console.error('OpenLayers widget JS not found');"

try:
    with open(
        pathlib.Path(__file__).parent / "static" / "openlayers_widget.css", "r"
    ) as f:
        _css_openlayers = f.read()
except FileNotFoundError:
    _css_openlayers = "/* OpenLayers widget CSS not found */"


class OpenLayersMap(MapWidget):
    """OpenLayers implementation of the map widget."""

    # OpenLayers-specific traits
    tile_layer = traitlets.Unicode("OSM").tag(sync=True)
    projection = traitlets.Unicode("EPSG:3857").tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_openlayers
    _css = _css_openlayers

    def __init__(
        self,
        center: List[float] = [0.0, 0.0],
        zoom: float = 2.0,
        tile_layer: str = "OSM",
        projection: str = "EPSG:3857",
        width: str = "100%",
        height: str = "600px",
        **kwargs,
    ):
        """Initialize OpenLayers map widget.

        Args:
            center: Map center as [longitude, latitude] (note: OpenLayers uses lon/lat order)
            zoom: Initial zoom level
            tile_layer: Tile layer provider name or URL template
            projection: Map projection (default: EPSG:3857)
            width: Widget width
            height: Widget height
            **kwargs: Additional widget arguments
        """
        super().__init__(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            **kwargs,
        )
        self.tile_layer = tile_layer
        self.projection = projection

    def add_tile_layer(
        self,
        url_template: str,
        attribution: str = "",
        layer_id: str = None,
        **options,
    ) -> None:
        """Add a tile layer to the map.

        Args:
            url_template: URL template for the tile layer
            attribution: Attribution text for the layer
            layer_id: Unique identifier for the layer
            **options: Additional layer options
        """
        if layer_id is None:
            layer_id = f"tile_layer_{len(self._layers)}"

        layer_config = {
            "type": "tile",
            "url": url_template,
            "attribution": attribution,
            **options,
        }
        self.add_layer(layer_id, layer_config)

    def add_marker(
        self,
        coordinate: List[float],
        popup: str = "",
        tooltip: str = "",
        icon: Optional[Dict[str, Any]] = None,
        **options,
    ) -> str:
        """Add a marker to the map.

        Args:
            coordinate: Marker position as [longitude, latitude]
            popup: Popup text
            tooltip: Tooltip text
            icon: Icon configuration
            **options: Additional marker options

        Returns:
            Marker ID
        """
        marker_id = f"marker_{len(self._layers)}"

        marker_config = {
            "type": "marker",
            "coordinate": coordinate,
            "popup": popup,
            "tooltip": tooltip,
            **options,
        }

        if icon:
            marker_config["icon"] = icon

        self.add_layer(marker_id, marker_config)
        return marker_id

    def add_circle(
        self,
        center: List[float],
        radius: float,
        color: str = "blue",
        fillColor: str = "blue",
        fillOpacity: float = 0.2,
        strokeWidth: float = 2,
        **options,
    ) -> str:
        """Add a circle to the map.

        Args:
            center: Circle center as [longitude, latitude]
            radius: Circle radius in meters
            color: Circle stroke color
            fillColor: Circle fill color
            fillOpacity: Circle fill opacity
            strokeWidth: Circle stroke width
            **options: Additional circle options

        Returns:
            Circle ID
        """
        circle_id = f"circle_{len(self._layers)}"

        circle_config = {
            "type": "circle",
            "center": center,
            "radius": radius,
            "color": color,
            "fillColor": fillColor,
            "fillOpacity": fillOpacity,
            "strokeWidth": strokeWidth,
            **options,
        }

        self.add_layer(circle_id, circle_config)
        return circle_id

    def add_polygon(
        self,
        coordinates: List[List[List[float]]],
        color: str = "blue",
        fillColor: str = "blue",
        fillOpacity: float = 0.2,
        strokeWidth: float = 2,
        **options,
    ) -> str:
        """Add a polygon to the map.

        Args:
            coordinates: Polygon coordinates as [[[lon, lat], [lon, lat], ...]]
            color: Polygon stroke color
            fillColor: Polygon fill color
            fillOpacity: Polygon fill opacity
            strokeWidth: Polygon stroke width
            **options: Additional polygon options

        Returns:
            Polygon ID
        """
        polygon_id = f"polygon_{len(self._layers)}"

        polygon_config = {
            "type": "polygon",
            "coordinates": coordinates,
            "color": color,
            "fillColor": fillColor,
            "fillOpacity": fillOpacity,
            "strokeWidth": strokeWidth,
            **options,
        }

        self.add_layer(polygon_id, polygon_config)
        return polygon_id

    def add_linestring(
        self,
        coordinates: List[List[float]],
        color: str = "blue",
        strokeWidth: float = 3,
        **options,
    ) -> str:
        """Add a line string to the map.

        Args:
            coordinates: Line coordinates as [[lon, lat], [lon, lat], ...]
            color: Line color
            strokeWidth: Line stroke width
            **options: Additional line options

        Returns:
            LineString ID
        """
        linestring_id = f"linestring_{len(self._layers)}"

        linestring_config = {
            "type": "linestring",
            "coordinates": coordinates,
            "color": color,
            "strokeWidth": strokeWidth,
            **options,
        }

        self.add_layer(linestring_id, linestring_config)
        return linestring_id

    def add_geojson(
        self,
        data: Union[str, Dict[str, Any]],
        style: Optional[Dict[str, Any]] = None,
        **options,
    ) -> str:
        """Add GeoJSON data to the map.

        Args:
            data: GeoJSON data as string or dict
            style: Style configuration
            **options: Additional GeoJSON options

        Returns:
            GeoJSON layer ID
        """
        geojson_id = f"geojson_{len(self._layers)}"

        geojson_config = {
            "type": "geojson",
            "data": data,
            **options,
        }

        if style:
            geojson_config["style"] = style

        self.add_layer(geojson_id, geojson_config)
        return geojson_id

    def add_vector_layer(
        self,
        features: List[Dict[str, Any]],
        style: Optional[Dict[str, Any]] = None,
        layer_id: str = None,
        **options,
    ) -> str:
        """Add a vector layer with features.

        Args:
            features: List of feature objects
            style: Style configuration for the layer
            layer_id: Unique identifier for the layer
            **options: Additional layer options

        Returns:
            Vector layer ID
        """
        if layer_id is None:
            layer_id = f"vector_{len(self._layers)}"

        layer_config = {
            "type": "vector",
            "features": features,
            "style": style or {},
            **options,
        }

        self.add_layer(layer_id, layer_config)
        return layer_id

    def fit_extent(self, extent: List[float]) -> None:
        """Fit the map view to given extent.

        Args:
            extent: Extent as [minX, minY, maxX, maxY]
        """
        self.call_js_method("fitExtent", extent)

    def transform_coordinate(
        self, coordinate: List[float], from_proj: str, to_proj: str
    ) -> List[float]:
        """Transform coordinate from one projection to another.

        Args:
            coordinate: Coordinate as [x, y]
            from_proj: Source projection
            to_proj: Target projection

        Returns:
            Transformed coordinate
        """
        # This would typically be handled on the JavaScript side
        self.call_js_method("transformCoordinate", coordinate, from_proj, to_proj)
        return coordinate  # Placeholder - real transformation happens in JS

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs
    ) -> str:
        """Generate the HTML template with map state for OpenLayers."""

        # Get tile layer URL template
        tile_providers = {
            "OSM": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "CartoDB.Positron": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
            "CartoDB.DarkMatter": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
            "Stamen.Terrain": "https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
            "Stamen.Watercolor": "https://stamen-tiles-{s}.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
        }

        tile_url = tile_providers.get(map_state.get("tile_layer", "OSM"))
        if not tile_url:
            tile_url = map_state.get("tile_layer", tile_providers["OSM"])

        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@v10.6.1/ol.css"
          crossorigin=""/>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }}
        #map {{
            width: {map_state.get('width', '100%')};
            height: {map_state.get('height', '600px')};
        }}
        .ol-popup {{
            position: absolute;
            background-color: white;
            box-shadow: 0 1px 4px rgba(0,0,0,0.2);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #cccccc;
            bottom: 12px;
            left: -50px;
            min-width: 280px;
        }}
        .ol-popup:after, .ol-popup:before {{
            top: 100%;
            border: solid transparent;
            content: " ";
            height: 0;
            width: 0;
            position: absolute;
            pointer-events: none;
        }}
        .ol-popup:after {{
            border-color: rgba(255, 255, 255, 0);
            border-top-color: white;
            border-width: 10px;
            left: 48px;
            margin-left: -10px;
        }}
        .ol-popup:before {{
            border-color: rgba(204, 204, 204, 0);
            border-top-color: #cccccc;
            border-width: 11px;
            left: 48px;
            margin-left: -11px;
        }}
        .ol-popup-closer {{
            text-decoration: none;
            position: absolute;
            top: 2px;
            right: 8px;
        }}
        .ol-popup-closer:after {{
            content: "✖";
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="popup" class="ol-popup">
        <a href="#" id="popup-closer" class="ol-popup-closer"></a>
        <div id="popup-content"></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/ol@v10.6.1/dist/ol.js"
            crossorigin=""></script>
    <script>
        // Import OpenLayers modules
        const {{Map, View}} = ol;
        const {{Tile: TileLayer, Vector: VectorLayer}} = ol.layer;
        const {{OSM, XYZ, Vector: VectorSource}} = ol.source;
        const {{Feature}} = ol;
        const {{Point, Circle: CircleGeom, Polygon, LineString}} = ol.geom;
        const {{Style, Fill, Stroke, Icon, Circle: CircleStyle}} = ol.style;
        const {{fromLonLat, toLonLat}} = ol.proj;
        const {{Overlay}} = ol;
        const {{GeoJSON}} = ol.format;

        // Initialize the map
        const view = new View({{
            center: fromLonLat({map_state.get('center', [0, 0])}),
            zoom: {map_state.get('zoom', 2)},
            projection: '{map_state.get('projection', 'EPSG:3857')}'
        }});

        const map = new Map({{
            target: 'map',
            view: view
        }});

        // Add base tile layer
        let baseSource;
        if ('{map_state.get('tile_layer', 'OSM')}' === 'OSM') {{
            baseSource = new OSM();
        }} else {{
            baseSource = new XYZ({{
                url: '{tile_url}',
                attributions: '© Map data providers'
            }});
        }}
        const baseLayer = new TileLayer({{
            source: baseSource
        }});
        map.addLayer(baseLayer);

        // Setup popup
        const container = document.getElementById('popup');
        const content = document.getElementById('popup-content');
        const closer = document.getElementById('popup-closer');

        const overlay = new Overlay({{
            element: container,
            autoPan: {{
                animation: {{
                    duration: 250,
                }}
            }}
        }});
        map.addOverlay(overlay);

        closer.onclick = function() {{
            overlay.setPosition(undefined);
            closer.blur();
            return false;
        }};

        // Add layers
        const layers = {json.dumps(map_state.get('_layers', {}))};
        for (const layerId in layers) {{
            const layer = layers[layerId];
            let olLayer = null;

            if (layer.type === 'tile') {{
                olLayer = new TileLayer({{
                    source: new XYZ({{
                        url: layer.url,
                        attributions: layer.attribution || ''
                    }})
                }});
            }} else if (layer.type === 'marker') {{
                const feature = new Feature({{
                    geometry: new Point(fromLonLat(layer.coordinate))
                }});

                if (layer.popup) {{
                    feature.set('popup', layer.popup);
                }}

                const vectorSource = new VectorSource({{
                    features: [feature]
                }});

                olLayer = new VectorLayer({{
                    source: vectorSource,
                    style: new Style({{
                        image: new CircleStyle({{
                            radius: 8,
                            fill: new Fill({{color: 'red'}}),
                            stroke: new Stroke({{color: 'white', width: 2}})
                        }})
                    }})
                }});
            }} else if (layer.type === 'circle') {{
                const feature = new Feature({{
                    geometry: new CircleGeom(fromLonLat(layer.center), layer.radius)
                }});

                const vectorSource = new VectorSource({{
                    features: [feature]
                }});

                olLayer = new VectorLayer({{
                    source: vectorSource,
                    style: new Style({{
                        fill: new Fill({{
                            color: layer.fillColor || 'blue',
                            opacity: layer.fillOpacity || 0.2
                        }}),
                        stroke: new Stroke({{
                            color: layer.color || 'blue',
                            width: layer.strokeWidth || 2
                        }})
                    }})
                }});
            }} else if (layer.type === 'polygon') {{
                const feature = new Feature({{
                    geometry: new Polygon(layer.coordinates.map(ring =>
                        ring.map(coord => fromLonLat(coord))
                    ))
                }});

                const vectorSource = new VectorSource({{
                    features: [feature]
                }});

                olLayer = new VectorLayer({{
                    source: vectorSource,
                    style: new Style({{
                        fill: new Fill({{
                            color: layer.fillColor || 'blue',
                            opacity: layer.fillOpacity || 0.2
                        }}),
                        stroke: new Stroke({{
                            color: layer.color || 'blue',
                            width: layer.strokeWidth || 2
                        }})
                    }})
                }});
            }} else if (layer.type === 'linestring') {{
                const feature = new Feature({{
                    geometry: new LineString(layer.coordinates.map(coord => fromLonLat(coord)))
                }});

                const vectorSource = new VectorSource({{
                    features: [feature]
                }});

                olLayer = new VectorLayer({{
                    source: vectorSource,
                    style: new Style({{
                        stroke: new Stroke({{
                            color: layer.color || 'blue',
                            width: layer.strokeWidth || 3
                        }})
                    }})
                }});
            }} else if (layer.type === 'geojson') {{
                const vectorSource = new VectorSource({{
                    features: new GeoJSON().readFeatures(layer.data, {{
                        featureProjection: 'EPSG:3857'
                    }})
                }});

                olLayer = new VectorLayer({{
                    source: vectorSource
                }});
            }}

            if (olLayer) {{
                map.addLayer(olLayer);
            }}
        }}

        // Handle map clicks for popups
        map.on('singleclick', function(evt) {{
            const feature = map.forEachFeatureAtPixel(evt.pixel, function(feature) {{
                return feature;
            }});

            if (feature && feature.get('popup')) {{
                const coordinate = evt.coordinate;
                content.innerHTML = feature.get('popup');
                overlay.setPosition(coordinate);
            }} else {{
                overlay.setPosition(undefined);
            }}
        }});
    </script>
</body>
</html>"""
        return html_template
