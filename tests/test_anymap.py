#!/usr/bin/env python

"""Tests for `anymap` package."""

import unittest
from unittest.mock import Mock, patch
from anymap import MapWidget, MapLibreMap


class TestMapWidget(unittest.TestCase):
    """Test cases for the base MapWidget class."""

    def setUp(self):
        """Set up test fixtures."""
        self.widget = MapWidget()

    def test_initialization(self):
        """Test widget initialization."""
        self.assertEqual(self.widget.center, [0.0, 0.0])
        self.assertEqual(self.widget.zoom, 2.0)
        self.assertEqual(self.widget.width, "100%")
        self.assertEqual(self.widget.height, "400px")
        self.assertEqual(self.widget._js_calls, [])
        self.assertEqual(self.widget._js_events, [])

    def test_set_center(self):
        """Test setting map center."""
        self.widget.set_center(40.7128, -74.0060)
        self.assertEqual(self.widget.center, [40.7128, -74.0060])

    def test_set_zoom(self):
        """Test setting map zoom."""
        self.widget.set_zoom(12)
        self.assertEqual(self.widget.zoom, 12)

    def test_call_js_method(self):
        """Test calling JavaScript methods."""
        self.widget.call_js_method("testMethod", 1, 2, keyword="value")

        calls = self.widget._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "testMethod")
        self.assertEqual(calls[0]["args"], (1, 2))
        self.assertEqual(calls[0]["kwargs"], {"keyword": "value"})
        self.assertIn("id", calls[0])

    def test_fly_to(self):
        """Test fly_to method."""
        self.widget.fly_to(51.5074, -0.1278, zoom=14)

        calls = self.widget._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "flyTo")
        self.assertEqual(calls[0]["args"][0]["center"], [51.5074, -0.1278])
        self.assertEqual(calls[0]["args"][0]["zoom"], 14)

    def test_add_layer(self):
        """Test adding a layer."""
        layer_config = {"id": "test", "type": "circle"}
        self.widget.add_layer("test-layer", layer_config)

        calls = self.widget._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "addLayer")
        self.assertEqual(calls[0]["args"], (layer_config, "test-layer"))

    def test_remove_layer(self):
        """Test removing a layer."""
        self.widget.remove_layer("test-layer")

        calls = self.widget._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "removeLayer")
        self.assertEqual(calls[0]["args"], ("test-layer",))

    def test_add_source(self):
        """Test adding a data source."""
        source_config = {"type": "geojson", "data": {}}
        self.widget.add_source("test-source", source_config)

        calls = self.widget._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "addSource")
        self.assertEqual(calls[0]["args"], ("test-source", source_config))

    def test_remove_source(self):
        """Test removing a data source."""
        self.widget.remove_source("test-source")

        calls = self.widget._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "removeSource")
        self.assertEqual(calls[0]["args"], ("test-source",))

    def test_event_handling(self):
        """Test event handling registration."""
        callback = Mock()
        self.widget.on_map_event("click", callback)

        # Simulate event from JavaScript
        test_event = [{"type": "click", "data": "test"}]
        self.widget._js_events = test_event

        # Trigger the observer manually
        self.widget._handle_js_events({"new": test_event})

        callback.assert_called_once_with({"type": "click", "data": "test"})


class TestMapLibreMap(unittest.TestCase):
    """Test cases for the MapLibreMap class."""

    def setUp(self):
        """Set up test fixtures."""
        self.map = MapLibreMap(
            center=[37.7749, -122.4194],
            zoom=12,
            map_style="https://example.com/style.json",
        )

    def test_initialization(self):
        """Test MapLibre map initialization."""
        self.assertEqual(self.map.center, [37.7749, -122.4194])
        self.assertEqual(self.map.zoom, 12)
        self.assertEqual(self.map.map_style, "https://example.com/style.json")
        self.assertEqual(self.map.bearing, 0.0)
        self.assertEqual(self.map.pitch, 0.0)
        self.assertTrue(self.map.antialias)

    def test_set_style(self):
        """Test setting map style."""
        # Test with string style
        self.map.set_style("https://new-style.com/style.json")
        self.assertEqual(self.map.map_style, "https://new-style.com/style.json")

        # Test with object style
        style_obj = {"version": 8, "sources": {}}
        self.map.set_style(style_obj)

        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setStyle" for call in calls))

    def test_set_bearing(self):
        """Test setting map bearing."""
        self.map.set_bearing(45)
        self.assertEqual(self.map.bearing, 45)

    def test_set_pitch(self):
        """Test setting map pitch."""
        self.map.set_pitch(60)
        self.assertEqual(self.map.pitch, 60)

    def test_add_geojson_layer(self):
        """Test adding GeoJSON layer."""
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                }
            ],
        }

        self.map.add_geojson_layer(
            layer_id="test-geojson",
            geojson_data=geojson_data,
            layer_type="circle",
            paint={"circle-radius": 5},
        )

        calls = self.map._js_calls
        # Should have calls for both addSource and addLayer
        self.assertTrue(any(call["method"] == "addSource" for call in calls))
        self.assertTrue(any(call["method"] == "addLayer" for call in calls))

    def test_add_marker(self):
        """Test adding a marker."""
        self.map.add_marker(40.7128, -74.0060, popup="New York")

        calls = self.map._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "addMarker")
        self.assertEqual(calls[0]["args"][0]["coordinates"], [-74.0060, 40.7128])
        self.assertEqual(calls[0]["args"][0]["popup"], "New York")

    def test_fit_bounds(self):
        """Test fitting map to bounds."""
        bounds = [[40.0, -75.0], [41.0, -74.0]]
        self.map.fit_bounds(bounds, padding=100)

        calls = self.map._js_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "fitBounds")
        self.assertEqual(calls[0]["args"][0], bounds)
        self.assertEqual(calls[0]["args"][1]["padding"], 100)


class TestMultipleInstances(unittest.TestCase):
    """Test cases for multiple map instances."""

    def test_multiple_map_creation(self):
        """Test creating multiple map instances."""
        maps = []
        for i in range(5):
            map_instance = MapLibreMap(center=[40 + i, -74 + i], zoom=10 + i)
            maps.append(map_instance)

        self.assertEqual(len(maps), 5)

        # Verify each map has unique properties
        for i, map_instance in enumerate(maps):
            self.assertEqual(map_instance.center, [40 + i, -74 + i])
            self.assertEqual(map_instance.zoom, 10 + i)

    def test_independent_map_operations(self):
        """Test that map operations are independent."""
        map1 = MapLibreMap(center=[40, -74], zoom=10)
        map2 = MapLibreMap(center=[50, -100], zoom=8)

        # Modify first map
        map1.set_zoom(15)
        map1.add_marker(40, -74, popup="Map 1")

        # Modify second map
        map2.set_zoom(12)
        map2.add_marker(50, -100, popup="Map 2")

        # Verify independence
        self.assertEqual(map1.zoom, 15)
        self.assertEqual(map2.zoom, 12)

        # Verify separate JS call lists
        map1_calls = [call for call in map1._js_calls if call["method"] == "addMarker"]
        map2_calls = [call for call in map2._js_calls if call["method"] == "addMarker"]

        self.assertEqual(len(map1_calls), 1)
        self.assertEqual(len(map2_calls), 1)
        self.assertEqual(map1_calls[0]["args"][0]["popup"], "Map 1")
        self.assertEqual(map2_calls[0]["args"][0]["popup"], "Map 2")


if __name__ == "__main__":
    unittest.main()
