"""Tests for Leaflet implementation."""

import pytest
import json
from unittest.mock import patch, mock_open
from anymap import LeafletMap


class TestLeafletMap:
    """Test cases for LeafletMap class."""

    def test_init_default_values(self):
        """Test LeafletMap initialization with default values."""
        leaflet_map = LeafletMap()

        assert leaflet_map.center == [51.505, -0.09]
        assert leaflet_map.zoom == 13.0
        assert leaflet_map.width == "100%"
        assert leaflet_map.height == "600px"
        assert leaflet_map.tile_layer == "OpenStreetMap"

    def test_init_custom_values(self):
        """Test LeafletMap initialization with custom values."""
        leaflet_map = LeafletMap(
            center=[40.7128, -74.0060],
            zoom=10.0,
            tile_layer="CartoDB.Positron",
            width="800px",
            height="500px",
        )

        assert leaflet_map.center == [40.7128, -74.0060]
        assert leaflet_map.zoom == 10.0
        assert leaflet_map.width == "800px"
        assert leaflet_map.height == "500px"
        assert leaflet_map.tile_layer == "CartoDB.Positron"

    def test_add_marker(self):
        """Test adding a marker to the map."""
        leaflet_map = LeafletMap()

        marker_id = leaflet_map.add_marker(
            [51.5, -0.1], popup="Test Marker", tooltip="Test Tooltip", draggable=True
        )

        assert marker_id in leaflet_map.get_layers()
        layer = leaflet_map.get_layers()[marker_id]
        assert layer["type"] == "marker"
        assert layer["latlng"] == [51.5, -0.1]
        assert layer["popup"] == "Test Marker"
        assert layer["tooltip"] == "Test Tooltip"
        assert layer["draggable"] is True

    def test_add_circle(self):
        """Test adding a circle to the map."""
        leaflet_map = LeafletMap()

        circle_id = leaflet_map.add_circle(
            [51.5, -0.1], radius=1000, color="red", fillColor="pink", fillOpacity=0.5
        )

        assert circle_id in leaflet_map.get_layers()
        layer = leaflet_map.get_layers()[circle_id]
        assert layer["type"] == "circle"
        assert layer["latlng"] == [51.5, -0.1]
        assert layer["radius"] == 1000
        assert layer["color"] == "red"
        assert layer["fillColor"] == "pink"
        assert layer["fillOpacity"] == 0.5

    def test_add_polygon(self):
        """Test adding a polygon to the map."""
        leaflet_map = LeafletMap()

        coords = [[51.5, -0.1], [51.6, -0.1], [51.6, -0.2], [51.5, -0.2]]
        polygon_id = leaflet_map.add_polygon(
            coords, color="blue", fillColor="lightblue", fillOpacity=0.3
        )

        assert polygon_id in leaflet_map.get_layers()
        layer = leaflet_map.get_layers()[polygon_id]
        assert layer["type"] == "polygon"
        assert layer["latlngs"] == coords
        assert layer["color"] == "blue"
        assert layer["fillColor"] == "lightblue"
        assert layer["fillOpacity"] == 0.3

    def test_add_polyline(self):
        """Test adding a polyline to the map."""
        leaflet_map = LeafletMap()

        coords = [[51.5, -0.1], [51.6, -0.1], [51.6, -0.2]]
        polyline_id = leaflet_map.add_polyline(coords, color="green", weight=5)

        assert polyline_id in leaflet_map.get_layers()
        layer = leaflet_map.get_layers()[polyline_id]
        assert layer["type"] == "polyline"
        assert layer["latlngs"] == coords
        assert layer["color"] == "green"
        assert layer["weight"] == 5

    def test_add_geojson(self):
        """Test adding GeoJSON data to the map."""
        leaflet_map = LeafletMap()

        geojson_data = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-0.1, 51.5]},
            "properties": {"name": "Test Point"},
        }

        geojson_id = leaflet_map.add_geojson(geojson_data, style={"color": "purple"})

        assert geojson_id in leaflet_map.get_layers()
        layer = leaflet_map.get_layers()[geojson_id]
        assert layer["type"] == "geojson"
        assert layer["data"] == geojson_data
        assert layer["style"] == {"color": "purple"}

    def test_add_tile_layer(self):
        """Test adding a tile layer to the map."""
        leaflet_map = LeafletMap()

        leaflet_map.add_tile_layer(
            "https://example.com/{z}/{x}/{y}.png",
            attribution="Test Attribution",
            layer_id="test_tiles",
        )

        assert "test_tiles" in leaflet_map.get_layers()
        layer = leaflet_map.get_layers()["test_tiles"]
        assert layer["type"] == "tile"
        assert layer["url"] == "https://example.com/{z}/{x}/{y}.png"
        assert layer["attribution"] == "Test Attribution"

    def test_remove_layer(self):
        """Test removing a layer from the map."""
        leaflet_map = LeafletMap()

        marker_id = leaflet_map.add_marker([51.5, -0.1])
        assert marker_id in leaflet_map.get_layers()

        leaflet_map.remove_layer(marker_id)
        assert marker_id not in leaflet_map.get_layers()

    def test_clear_layers(self):
        """Test clearing all layers from the map."""
        leaflet_map = LeafletMap()

        leaflet_map.add_marker([51.5, -0.1])
        leaflet_map.add_circle([51.6, -0.2], radius=500)

        assert len(leaflet_map.get_layers()) == 2

        leaflet_map.clear_layers()
        assert len(leaflet_map.get_layers()) == 0

    def test_set_center(self):
        """Test setting map center."""
        leaflet_map = LeafletMap()

        leaflet_map.set_center(40.7128, -74.0060)
        assert leaflet_map.center == [40.7128, -74.0060]

    def test_set_zoom(self):
        """Test setting map zoom."""
        leaflet_map = LeafletMap()

        leaflet_map.set_zoom(15.0)
        assert leaflet_map.zoom == 15.0

    def test_fly_to(self):
        """Test fly_to method."""
        leaflet_map = LeafletMap()

        with patch.object(leaflet_map, "call_js_method") as mock_call:
            leaflet_map.fly_to(40.7128, -74.0060, 12.0)
            mock_call.assert_called_once_with(
                "flyTo", {"center": [40.7128, -74.0060], "zoom": 12.0}
            )

    def test_fit_bounds(self):
        """Test fit_bounds method."""
        leaflet_map = LeafletMap()

        bounds = [[40.7128, -74.0060], [40.7829, -73.9654]]
        with patch.object(leaflet_map, "call_js_method") as mock_call:
            leaflet_map.fit_bounds(bounds)
            mock_call.assert_called_once_with("fitBounds", bounds)

    def test_generate_html_template(self):
        """Test HTML template generation."""
        leaflet_map = LeafletMap(
            center=[51.505, -0.09], zoom=13, tile_layer="OpenStreetMap"
        )

        # Add some content
        leaflet_map.add_marker([51.5, -0.1], popup="Test")

        map_state = {
            "center": [51.505, -0.09],
            "zoom": 13,
            "width": "100%",
            "height": "600px",
            "tile_layer": "OpenStreetMap",
            "_layers": leaflet_map.get_layers(),
            "_sources": {},
        }

        html = leaflet_map._generate_html_template(map_state, "Test Map")

        # Check that HTML contains expected elements
        assert "<!DOCTYPE html>" in html
        assert "Test Map" in html
        assert "leaflet.js" in html
        assert "leaflet.css" in html
        assert "L.map" in html
        assert "51.505" in html
        assert "-0.09" in html

    def test_to_html(self):
        """Test to_html method."""
        leaflet_map = LeafletMap()
        leaflet_map.add_marker([51.5, -0.1], popup="Test Marker")

        html = leaflet_map.to_html(title="Test Export")

        assert "Test Export" in html
        assert "leaflet.js" in html
        assert "Test Marker" in html

    def test_to_html_with_file(self):
        """Test to_html method with file output."""
        leaflet_map = LeafletMap()

        with patch("builtins.open", mock_open()) as mock_file:
            html = leaflet_map.to_html(filename="test.html", title="Test")

            mock_file.assert_called_once_with("test.html", "w", encoding="utf-8")
            mock_file().write.assert_called_once()

    def test_custom_tile_layer_urls(self):
        """Test that custom tile layer URLs are handled correctly."""
        leaflet_map = LeafletMap()

        # Test with known provider
        map_state = {"tile_layer": "CartoDB.Positron"}
        html = leaflet_map._generate_html_template(map_state, "Test")
        assert "cartodb-basemaps" in html

        # Test with custom URL
        map_state = {"tile_layer": "https://custom.tiles.com/{z}/{x}/{y}.png"}
        html = leaflet_map._generate_html_template(map_state, "Test")
        assert "custom.tiles.com" in html

    def test_marker_with_custom_icon(self):
        """Test marker with custom icon configuration."""
        leaflet_map = LeafletMap()

        icon_config = {
            "iconUrl": "https://example.com/marker.png",
            "iconSize": [25, 41],
            "iconAnchor": [12, 41],
        }

        marker_id = leaflet_map.add_marker([51.5, -0.1], icon=icon_config)

        layer = leaflet_map.get_layers()[marker_id]
        assert layer["icon"] == icon_config

    def test_layer_id_generation(self):
        """Test that layer IDs are generated correctly."""
        leaflet_map = LeafletMap()

        marker_id1 = leaflet_map.add_marker([51.5, -0.1])
        marker_id2 = leaflet_map.add_marker([51.6, -0.2])
        circle_id = leaflet_map.add_circle([51.7, -0.3], radius=1000)

        assert marker_id1.startswith("marker_")
        assert marker_id2.startswith("marker_")
        assert circle_id.startswith("circle_")
        assert marker_id1 != marker_id2

    def test_empty_layers_and_sources(self):
        """Test behavior with empty layers and sources."""
        leaflet_map = LeafletMap()

        assert leaflet_map.get_layers() == {}
        assert leaflet_map.get_sources() == {}

        # Should not raise any errors
        leaflet_map.clear_layers()
        leaflet_map.clear_sources()

    def test_geojson_with_string_data(self):
        """Test GeoJSON with string data instead of dict."""
        leaflet_map = LeafletMap()

        geojson_string = '{"type": "Point", "coordinates": [0, 0]}'
        geojson_id = leaflet_map.add_geojson(geojson_string)

        layer = leaflet_map.get_layers()[geojson_id]
        assert layer["data"] == geojson_string


if __name__ == "__main__":
    pytest.main([__file__])
