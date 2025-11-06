"""Leaflet implementation of the map widget."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union
import json

from .base import MapWidget

# Load Leaflet-specific js and css
try:
    with open(pathlib.Path(__file__).parent / "static" / "leaflet_widget.js", "r") as f:
        _esm_leaflet = f.read()
except FileNotFoundError:
    _esm_leaflet = "console.error('Leaflet widget JS not found');"

try:
    with open(
        pathlib.Path(__file__).parent / "static" / "leaflet_widget.css", "r"
    ) as f:
        _css_leaflet = f.read()
except FileNotFoundError:
    _css_leaflet = "/* Leaflet widget CSS not found */"


class LeafletMap(MapWidget):
    """Leaflet implementation of the map widget."""

    # Leaflet-specific traits
    tile_layer = traitlets.Unicode("OpenStreetMap").tag(sync=True)
    attribution = traitlets.Unicode("").tag(sync=True)
    map_options = traitlets.Dict(default_value={}).tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_leaflet
    _css = _css_leaflet

    def __init__(
        self,
        center: List[float] = [51.505, -0.09],
        zoom: float = 13.0,
        tile_layer: str = "OpenStreetMap",
        width: str = "100%",
        height: str = "600px",
        **kwargs,
    ):
        """Initialize Leaflet map widget.

        Args:
            center: Map center as [latitude, longitude]
            zoom: Initial zoom level
            tile_layer: Tile layer provider name or URL template
            width: Widget width
            height: Widget height
            map_options: Leaflet Map Options (see https://leafletjs.com/reference.html#map-option)
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
        latlng: List[float],
        popup: str = "",
        tooltip: str = "",
        tooltip_options: Optional[Dict] = None,
        icon: Optional[Dict[str, Any]] = None,
        draggable: bool = False,
        **options,
    ) -> str:
        """Add a marker to the map.

        Args:
            latlng: Marker position as [latitude, longitude]
            popup: Popup text
            tooltip: Tooltip text
            tooltip_options: Tooltip options
            icon: Icon configuration
            draggable: Whether the marker is draggable
            **options: Additional marker options

        Returns:
            Marker ID
        """
        marker_id = f"marker_{len(self._layers)}"

        marker_config = {
            "type": "marker",
            "latlng": latlng,
            "popup": popup,
            "tooltip": tooltip,
            "tooltip_options": tooltip_options,
            "draggable": draggable,
            **options,
        }

        if icon:
            marker_config["icon"] = icon

        self.add_layer(marker_id, marker_config)
        return marker_id

    def add_circle(
        self,
        latlng: List[float],
        radius: float,
        color: str = "blue",
        fillColor: str = "blue",
        fillOpacity: float = 0.2,
        tooltip: str = "",
        tooltip_options: Optional[Dict] = None,
        **options,
    ) -> str:
        """Add a circle to the map.

        Args:
            latlng: Circle center as [latitude, longitude]
            radius: Circle radius in meters
            color: Circle stroke color
            fillColor: Circle fill color
            fillOpacity: Circle fill opacity
            tooltip: Tooltip text
            tooltip_options: Tooltip options
            **options: Additional circle options

        Returns:
            Circle ID
        """
        circle_id = f"circle_{len(self._layers)}"

        circle_config = {
            "type": "circle",
            "latlng": latlng,
            "radius": radius,
            "color": color,
            "fillColor": fillColor,
            "fillOpacity": fillOpacity,
            "tooltip": tooltip,
            "tooltip_options": tooltip_options,
            **options,
        }

        self.add_layer(circle_id, circle_config)
        return circle_id

    def add_polygon(
        self,
        latlngs: List[List[float]],
        color: str = "blue",
        fillColor: str = "blue",
        fillOpacity: float = 0.2,
        tooltip: str = "",
        tooltip_options: Optional[Dict] = None,
        **options,
    ) -> str:
        """Add a polygon to the map.

        Args:
            latlngs: Polygon vertices as [[lat, lng], [lat, lng], ...]
            color: Polygon stroke color
            fillColor: Polygon fill color
            fillOpacity: Polygon fill opacity
            **options: Additional polygon options

        Returns:
            Polygon ID
        """
        polygon_id = f"polygon_{len(self._layers)}"

        polygon_config = {
            "type": "polygon",
            "latlngs": latlngs,
            "color": color,
            "fillColor": fillColor,
            "fillOpacity": fillOpacity,
            "tooltip": tooltip,
            "tooltip_options": tooltip_options,
            **options,
        }

        self.add_layer(polygon_id, polygon_config)
        return polygon_id

    def add_polyline(
        self,
        latlngs: List[List[float]],
        color: str = "blue",
        weight: float = 3,
        tooltip: str = "",
        tooltip_options: Optional[Dict] = None,
        **options,
    ) -> str:
        """Add a polyline to the map.

        Args:
            latlngs: Polyline vertices as [[lat, lng], [lat, lng], ...]
            color: Polyline color
            weight: Polyline weight
            **options: Additional polyline options

        Returns:
            Polyline ID
        """
        polyline_id = f"polyline_{len(self._layers)}"

        polyline_config = {
            "type": "polyline",
            "latlngs": latlngs,
            "color": color,
            "weight": weight,
            "tooltip": tooltip,
            "tooltip_options": tooltip_options,
            **options,
        }

        self.add_layer(polyline_id, polyline_config)
        return polyline_id

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

    def add_geotiff(
        self,
        url: str,
        layer_id: Optional[str] = None,
        fit_bounds: bool = True,
        **options: Any,
    ) -> str:
        """Add a Cloud Optimized GeoTIFF (COG) to the map without TiTiler.

        This method uses georaster-layer-for-leaflet in the frontend to stream and
        render a COG directly in the browser via HTTP range requests.

        Args:
            url: URL to the Cloud Optimized GeoTIFF.
            layer_id: Optional unique identifier for the layer. If not provided,
                one will be generated.
            fit_bounds: Whether to fit the map to the layer's bounds after it
                loads on the client.
            **options: Additional options forwarded to GeoRasterLayer (e.g.,
                ``opacity``, ``resolution``, ``resampling``, ``nodata``).

        Returns:
            The layer ID used to add the layer.
        """
        if layer_id is None:
            layer_id = f"geotiff_{len(self._layers)}"

        layer_config = {
            "type": "geotiff",
            "url": url,
            "fit_bounds": fit_bounds,
            **options,
        }

        self.add_layer(layer_id, layer_config)
        return layer_id

    def fit_bounds(self, bounds: List[List[float]]) -> None:
        """Fit the map view to given bounds.

        Args:
            bounds: Bounds as [[south, west], [north, east]]
        """
        self.call_js_method("fitBounds", bounds)

    def _generate_html_template(
        self, map_state: Dict[str, Any], title: str, **kwargs
    ) -> str:
        """Generate the HTML template with map state for Leaflet."""

        # Get tile layer URL template
        tile_providers = {
            "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "CartoDB.Positron": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
            "CartoDB.DarkMatter": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
            "Stamen.Terrain": "https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
            "Stamen.Watercolor": "https://stamen-tiles-{s}.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
        }

        tile_url = tile_providers.get(map_state.get("tile_layer", "OpenStreetMap"))
        if not tile_url:
            tile_url = map_state.get("tile_layer", tile_providers["OpenStreetMap"])

        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
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
    </style>
</head>
<body>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""></script>
    <script>
        // Initialize the map
        var map = L.map('map', {{
            center: {map_state.get('center', [51.505, -0.09])},
            zoom: {map_state.get('zoom', 13)}
        }});

        // Add tile layer
        L.tileLayer('{tile_url}', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);

        // Add layers
        var layers = {json.dumps(map_state.get('_layers', {}))};
        for (var layerId in layers) {{
            var layer = layers[layerId];
            var leafletLayer = null;

            if (layer.type === 'tile') {{
                leafletLayer = L.tileLayer(layer.url, {{
                    attribution: layer.attribution || ''
                }});
            }} else if (layer.type === 'marker') {{
                leafletLayer = L.marker(layer.latlng, {{
                    draggable: layer.draggable || false
                }});
                if (layer.popup) {{
                    leafletLayer.bindPopup(layer.popup);
                }}
                if (layer.tooltip) {{
                    leafletLayer.bindTooltip(layer.tooltip);
                }}
            }} else if (layer.type === 'circle') {{
                leafletLayer = L.circle(layer.latlng, {{
                    radius: layer.radius,
                    color: layer.color || 'blue',
                    fillColor: layer.fillColor || 'blue',
                    fillOpacity: layer.fillOpacity || 0.2
                }});
            }} else if (layer.type === 'polygon') {{
                leafletLayer = L.polygon(layer.latlngs, {{
                    color: layer.color || 'blue',
                    fillColor: layer.fillColor || 'blue',
                    fillOpacity: layer.fillOpacity || 0.2
                }});
            }} else if (layer.type === 'polyline') {{
                leafletLayer = L.polyline(layer.latlngs, {{
                    color: layer.color || 'blue',
                    weight: layer.weight || 3
                }});
            }} else if (layer.type === 'geojson') {{
                leafletLayer = L.geoJSON(layer.data, layer.style || {{}});
            }} else if (layer.type === 'geotiff') {{
                // Load COG via georaster-layer-for-leaflet
                (function(layerCfg) {{
                    var loadScriptWithFallback = function(urls) {{
                        return new Promise(function(resolve, reject) {{
                            var i = 0;
                            var next = function() {{
                                if (i >= urls.length) return reject(new Error('All script sources failed'));
                                var u = urls[i++];
                                var s = document.createElement('script');
                                s.async = true;
                                s.src = u;
                                s.onload = function() {{ resolve({ ok: true, url: u }); }};
                                s.onerror = function() {{ console.warn('Script failed, trying fallback:', u); s.remove(); next(); }};
                                document.head.appendChild(s);
                            }};
                            next();
                        }});
                    }};
                    var ensureScripts = function() {{
                        if (window.GeoRasterLayer && window.parseGeoraster) return Promise.resolve(true);
                        var georasterUrls = [
                            '/files/anymap/static/vendor/georaster.browser.bundle.min.js',
                            '/files/anymap/static/vendor/georaster.bundle.min.js',
                            '/files/anymap/static/vendor/georaster.browser.min.js',
                            'https://cdn.jsdelivr.net/npm/georaster@1.6.0/dist/georaster.browser.bundle.min.js',
                            'https://fastly.jsdelivr.net/npm/georaster@1.6.0/dist/georaster.browser.bundle.min.js',
                            'https://unpkg.com/georaster@1.6.0/dist/georaster.browser.bundle.min.js'
                        ];
                        var layerUrls = [
                            '/files/anymap/static/vendor/georaster-layer-for-leaflet.min.js',
                            'https://cdn.jsdelivr.net/npm/georaster-layer-for-leaflet@2.0.2/dist/georaster-layer-for-leaflet.min.js',
                            'https://fastly.jsdelivr.net/npm/georaster-layer-for-leaflet@2.0.2/dist/georaster-layer-for-leaflet.min.js',
                            'https://unpkg.com/georaster-layer-for-leaflet@2.0.2/dist/georaster-layer-for-leaflet.min.js'
                        ];
                        var prevModule = window.module; var prevExports = window.exports; try {{ delete window.module; delete window.exports; }} catch(e) {{}}
                        return loadScriptWithFallback(georasterUrls).then(function() {{
                            return loadScriptWithFallback(layerUrls);
                        }}).finally(function() {{ if (prevModule !== undefined) window.module = prevModule; if (prevExports !== undefined) window.exports = prevExports; }});
                    }};

                    ensureScripts().then(function() {{
                        window.parseGeoraster(layerCfg.url).then(function(georaster) {{
                            var opts = Object.assign({{ georaster: georaster }}, layerCfg);
                            delete opts.type; delete opts.url; delete opts.fit_bounds;

                            // Provide a default grayscale for single-band rasters if not specified
                            try {{
                                var bands = georaster.numberOfRasters || (georaster.bands ? georaster.bands.length : 1);
                                if (!opts.pixelValuesToColorFn && bands === 1 && georaster.mins && georaster.maxs) {{
                                    var min = georaster.mins[0];
                                    var max = georaster.maxs[0];
                                    var opacity = (typeof layerCfg.opacity === 'number') ? layerCfg.opacity : 1.0;
                                    opts.pixelValuesToColorFn = function(values) {{
                                        var v = values[0];
                                        if (v === null || v === undefined || isNaN(v)) return null;
                                        var t = (v - min) / (max - min);
                                        t = Math.max(0, Math.min(1, t));
                                        var gray = Math.round(255 * t);
                                        return 'rgba(' + gray + ',' + gray + ',' + gray + ',' + opacity + ')';
                                    }};
                                }}
                            }} catch (e) {{ console.warn('Default color mapping failed:', e); }}

                            var grLayer = new GeoRasterLayer(opts);
                            grLayer.addTo(map);
                            if (layerCfg.fit_bounds !== false && grLayer.getBounds) {{
                                try {{ map.fitBounds(grLayer.getBounds()); }} catch (e) {{}}
                            }}
                        }}).catch(function(err) {{ console.error('Failed to load GeoTIFF:', err); }});
                    }}).catch(function(err) {{ console.error('Failed to load georaster scripts:', err); }});
                }})(layer);
            }}

            if (leafletLayer) {{
                leafletLayer.addTo(map);
            }}
        }}
    </script>
</body>
</html>
"""
        return html_template
