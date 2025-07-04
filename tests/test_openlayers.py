"""Tests for OpenLayers implementation."""

import pytest
import json
from unittest.mock import patch, mock_open
from anymap import OpenLayersMap


class TestOpenLayersMap:
    """Test cases for OpenLayersMap class."""

    def test_init_default_values(self):
        """Test OpenLayersMap initialization with default values."""
        ol_map = OpenLayersMap()

        assert ol_map.center == [0.0, 0.0]
        assert ol_map.zoom == 2.0
        assert ol_map.width == "100%"
        assert ol_map.height == "600px"
        assert ol_map.tile_layer == "OSM"
        assert ol_map.projection == "EPSG:3857"

    def test_init_custom_values(self):
        """Test OpenLayersMap initialization with custom values."""
        ol_map = OpenLayersMap(
            center=[-74.0060, 40.7128],
            zoom=10.0,
            tile_layer="CartoDB.Positron",
            projection="EPSG:4326",
            width="800px",
            height="500px",
        )

        assert ol_map.center == [-74.0060, 40.7128]
        assert ol_map.zoom == 10.0
        assert ol_map.width == "800px"
        assert ol_map.height == "500px"
        assert ol_map.tile_layer == "CartoDB.Positron"
        assert ol_map.projection == "EPSG:4326"

    def test_add_marker(self):
        """Test adding a marker to the map."""
        ol_map = OpenLayersMap()

        marker_id = ol_map.add_marker(
            [-0.1, 51.5], popup="Test Marker", tooltip="Test Tooltip"
        )

        assert marker_id in ol_map.get_layers()
        layer = ol_map.get_layers()[marker_id]
        assert layer["type"] == "marker"
        assert layer["coordinate"] == [-0.1, 51.5]
        assert layer["popup"] == "Test Marker"
        assert layer["tooltip"] == "Test Tooltip"

    def test_add_circle(self):
        """Test adding a circle to the map."""
        ol_map = OpenLayersMap()

        circle_id = ol_map.add_circle(
            [-0.1, 51.5],
            radius=1000,
            color="red",
            fillColor="pink",
            fillOpacity=0.5,
            strokeWidth=3,
        )

        assert circle_id in ol_map.get_layers()
        layer = ol_map.get_layers()[circle_id]
        assert layer["type"] == "circle"
        assert layer["center"] == [-0.1, 51.5]
        assert layer["radius"] == 1000
        assert layer["color"] == "red"
        assert layer["fillColor"] == "pink"
        assert layer["fillOpacity"] == 0.5
        assert layer["strokeWidth"] == 3

    def test_add_polygon(self):
        """Test adding a polygon to the map."""
        ol_map = OpenLayersMap()

        coords = [
            [[-0.1, 51.5], [-0.1, 51.6], [-0.2, 51.6], [-0.2, 51.5], [-0.1, 51.5]]
        ]
        polygon_id = ol_map.add_polygon(
            coords, color="blue", fillColor="lightblue", fillOpacity=0.3, strokeWidth=2
        )

        assert polygon_id in ol_map.get_layers()
        layer = ol_map.get_layers()[polygon_id]
        assert layer["type"] == "polygon"
        assert layer["coordinates"] == coords
        assert layer["color"] == "blue"
        assert layer["fillColor"] == "lightblue"
        assert layer["fillOpacity"] == 0.3
        assert layer["strokeWidth"] == 2

    def test_add_linestring(self):
        """Test adding a linestring to the map."""
        ol_map = OpenLayersMap()

        coords = [[-0.1, 51.5], [-0.1, 51.6], [-0.2, 51.6]]
        linestring_id = ol_map.add_linestring(coords, color="green", strokeWidth=5)

        assert linestring_id in ol_map.get_layers()
        layer = ol_map.get_layers()[linestring_id]
        assert layer["type"] == "linestring"
        assert layer["coordinates"] == coords
        assert layer["color"] == "green"
        assert layer["strokeWidth"] == 5

    def test_add_geojson(self):
        """Test adding GeoJSON data to the map."""
        ol_map = OpenLayersMap()

        geojson_data = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-0.1, 51.5]},
            "properties": {"name": "Test Point"},
        }

        geojson_id = ol_map.add_geojson(
            geojson_data, style={"fill": {"color": "purple"}}
        )

        assert geojson_id in ol_map.get_layers()
        layer = ol_map.get_layers()[geojson_id]
        assert layer["type"] == "geojson"
        assert layer["data"] == geojson_data
        assert layer["style"] == {"fill": {"color": "purple"}}

    def test_add_vector_layer(self):
        """Test adding a vector layer with features."""
        ol_map = OpenLayersMap()

        features = [
            {
                "geometry": {"type": "Point", "coordinates": [-0.1, 51.5]},
                "properties": {"name": "Test Feature"},
            }
        ]

        vector_id = ol_map.add_vector_layer(
            features, style={"image": {"circle": {"radius": 8}}}, layer_id="test_vector"
        )

        assert vector_id == "test_vector"
        assert vector_id in ol_map.get_layers()
        layer = ol_map.get_layers()[vector_id]
        assert layer["type"] == "vector"
        assert layer["features"] == features
        assert layer["style"] == {"image": {"circle": {"radius": 8}}}

    def test_add_tile_layer(self):
        """Test adding a tile layer to the map."""
        ol_map = OpenLayersMap()

        ol_map.add_tile_layer(
            "https://example.com/{z}/{x}/{y}.png",
            attribution="Test Attribution",
            layer_id="test_tiles",
        )

        assert "test_tiles" in ol_map.get_layers()
        layer = ol_map.get_layers()["test_tiles"]
        assert layer["type"] == "tile"
        assert layer["url"] == "https://example.com/{z}/{x}/{y}.png"
        assert layer["attribution"] == "Test Attribution"

    def test_remove_layer(self):
        """Test removing a layer from the map."""
        ol_map = OpenLayersMap()

        marker_id = ol_map.add_marker([-0.1, 51.5])
        assert marker_id in ol_map.get_layers()

        ol_map.remove_layer(marker_id)
        assert marker_id not in ol_map.get_layers()

    def test_clear_layers(self):
        """Test clearing all layers from the map."""
        ol_map = OpenLayersMap()

        ol_map.add_marker([-0.1, 51.5])
        ol_map.add_circle([-0.2, 51.6], radius=500)

        assert len(ol_map.get_layers()) == 2

        ol_map.clear_layers()
        assert len(ol_map.get_layers()) == 0

    def test_set_center(self):
        """Test setting map center."""
        ol_map = OpenLayersMap()

        ol_map.set_center(-74.0060, 40.7128)
        assert ol_map.center == [-74.0060, 40.7128]

    def test_set_zoom(self):
        """Test setting map zoom."""
        ol_map = OpenLayersMap()

        ol_map.set_zoom(15.0)
        assert ol_map.zoom == 15.0

    def test_fly_to(self):
        """Test fly_to method."""
        ol_map = OpenLayersMap()

        with patch.object(ol_map, "call_js_method") as mock_call:
            ol_map.fly_to(-74.0060, 40.7128, 12.0)
            mock_call.assert_called_once_with(
                "flyTo", {"center": [-74.0060, 40.7128], "zoom": 12.0}
            )

    def test_fit_extent(self):
        """Test fit_extent method."""
        ol_map = OpenLayersMap()

        extent = [-74.1, 40.7, -73.9, 40.8]
        with patch.object(ol_map, "call_js_method") as mock_call:
            ol_map.fit_extent(extent)
            mock_call.assert_called_once_with("fitExtent", extent)

    def test_transform_coordinate(self):
        """Test transform_coordinate method."""
        ol_map = OpenLayersMap()

        coordinate = [-74.0060, 40.7128]
        with patch.object(ol_map, "call_js_method") as mock_call:
            result = ol_map.transform_coordinate(coordinate, "EPSG:4326", "EPSG:3857")
            mock_call.assert_called_once_with(
                "transformCoordinate", coordinate, "EPSG:4326", "EPSG:3857"
            )
            assert result == coordinate  # Placeholder behavior

    def test_generate_html_template(self):
        """Test HTML template generation."""
        ol_map = OpenLayersMap(center=[-0.09, 51.505], zoom=13, tile_layer="OSM")

        # Add some content
        ol_map.add_marker([-0.1, 51.5], popup="Test")

        map_state = {
            "center": [-0.09, 51.505],
            "zoom": 13,
            "width": "100%",
            "height": "600px",
            "tile_layer": "OSM",
            "projection": "EPSG:3857",
            "_layers": ol_map.get_layers(),
            "_sources": {},
        }

        html = ol_map._generate_html_template(map_state, "Test Map")

        # Check that HTML contains expected elements
        assert "<!DOCTYPE html>" in html
        assert "Test Map" in html
        assert "ol.js" in html
        assert "ol.css" in html
        assert "new Map" in html
        assert "-0.09" in html
        assert "51.505" in html

    def test_to_html(self):
        """Test to_html method."""
        ol_map = OpenLayersMap()
        ol_map.add_marker([-0.1, 51.5], popup="Test Marker")

        html = ol_map.to_html(title="Test Export")

        assert "Test Export" in html
        assert "ol.js" in html
        assert "Test Marker" in html

    def test_to_html_with_file(self):
        """Test to_html method with file output."""
        ol_map = OpenLayersMap()

        with patch("builtins.open", mock_open()) as mock_file:
            html = ol_map.to_html(filename="test.html", title="Test")

            mock_file.assert_called_once_with("test.html", "w", encoding="utf-8")
            mock_file().write.assert_called_once()

    def test_custom_tile_layer_urls(self):
        """Test that custom tile layer URLs are handled correctly."""
        ol_map = OpenLayersMap()

        # Test with known provider
        map_state = {"tile_layer": "CartoDB.Positron"}
        html = ol_map._generate_html_template(map_state, "Test")
        assert "cartodb-basemaps" in html

        # Test with custom URL
        map_state = {"tile_layer": "https://custom.tiles.com/{z}/{x}/{y}.png"}
        html = ol_map._generate_html_template(map_state, "Test")
        assert "custom.tiles.com" in html

    def test_marker_with_custom_icon(self):
        """Test marker with custom icon configuration."""
        ol_map = OpenLayersMap()

        icon_config = {"src": "https://example.com/marker.png", "scale": 0.5}

        marker_id = ol_map.add_marker([-0.1, 51.5], icon=icon_config)

        layer = ol_map.get_layers()[marker_id]
        assert layer["icon"] == icon_config

    def test_layer_id_generation(self):
        """Test that layer IDs are generated correctly."""
        ol_map = OpenLayersMap()

        marker_id1 = ol_map.add_marker([-0.1, 51.5])
        marker_id2 = ol_map.add_marker([-0.2, 51.6])
        circle_id = ol_map.add_circle([-0.3, 51.7], radius=1000)

        assert marker_id1.startswith("marker_")
        assert marker_id2.startswith("marker_")
        assert circle_id.startswith("circle_")
        assert marker_id1 != marker_id2

    def test_empty_layers_and_sources(self):
        """Test behavior with empty layers and sources."""
        ol_map = OpenLayersMap()

        assert ol_map.get_layers() == {}
        assert ol_map.get_sources() == {}

        # Should not raise any errors
        ol_map.clear_layers()
        ol_map.clear_sources()

    def test_geojson_with_string_data(self):
        """Test GeoJSON with string data instead of dict."""
        ol_map = OpenLayersMap()

        geojson_string = '{"type": "Point", "coordinates": [0, 0]}'
        geojson_id = ol_map.add_geojson(geojson_string)

        layer = ol_map.get_layers()[geojson_id]
        assert layer["data"] == geojson_string

    def test_coordinate_order(self):
        """Test that OpenLayers uses longitude, latitude order."""
        ol_map = OpenLayersMap(center=[-74.0060, 40.7128])  # [lon, lat] - New York

        # Verify the coordinate order is preserved
        assert ol_map.center == [-74.0060, 40.7128]

        # Test marker coordinates
        marker_id = ol_map.add_marker([-0.1278, 51.5074])  # [lon, lat] - London
        layer = ol_map.get_layers()[marker_id]
        assert layer["coordinate"] == [-0.1278, 51.5074]

    def test_projection_support(self):
        """Test projection parameter."""
        ol_map = OpenLayersMap(projection="EPSG:4326")
        assert ol_map.projection == "EPSG:4326"

        # Test HTML generation includes projection
        map_state = {"projection": "EPSG:4326"}
        html = ol_map._generate_html_template(map_state, "Test")
        assert "EPSG:4326" in html

    def test_vector_layer_auto_id_generation(self):
        """Test that vector layer IDs are auto-generated when not provided."""
        ol_map = OpenLayersMap()

        features = [{"geometry": {"type": "Point", "coordinates": [0, 0]}}]
        vector_id = ol_map.add_vector_layer(features)

        assert vector_id.startswith("vector_")
        assert vector_id in ol_map.get_layers()

    def test_html_template_includes_openlayers_features(self):
        """Test that HTML template includes OpenLayers-specific features."""
        ol_map = OpenLayersMap()

        map_state = {
            "center": [0, 0],
            "zoom": 2,
            "projection": "EPSG:3857",
            "_layers": {},
        }

        html = ol_map._generate_html_template(map_state, "Test")

        # Check for OpenLayers-specific elements
        assert "fromLonLat" in html
        assert "toLonLat" in html
        assert "new Map" in html
        assert "new View" in html
        assert "TileLayer" in html
        assert "new OSM" in html

    def test_circle_geometry_parameters(self):
        """Test circle with specific OpenLayers geometry parameters."""
        ol_map = OpenLayersMap()

        circle_id = ol_map.add_circle(
            [0, 0],
            radius=1000,
            color="#ff0000",
            fillColor="#00ff00",
            fillOpacity=0.7,
            strokeWidth=4,
        )

        layer = ol_map.get_layers()[circle_id]
        assert layer["center"] == [0, 0]
        assert layer["radius"] == 1000
        assert layer["color"] == "#ff0000"
        assert layer["fillColor"] == "#00ff00"
        assert layer["fillOpacity"] == 0.7
        assert layer["strokeWidth"] == 4


if __name__ == "__main__":
    pytest.main([__file__])
