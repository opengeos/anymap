#!/usr/bin/env python

"""Tests for `anymap` package."""

import unittest
from unittest.mock import Mock, patch
from anymap import MapWidget, MapLibreMap, MapboxMap, CesiumMap


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
        self.assertEqual(self.widget.height, "600px")
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

        # Trigger the observer manually
        self.widget._handle_js_events({"new": test_event})

        # Check that callback was called with the event
        callback.assert_called_with({"type": "click", "data": "test"})
        # Verify it was called at least once
        self.assertTrue(callback.called)


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


class TestEnhancedMapFeatures(unittest.TestCase):
    """Test cases for enhanced map features."""

    def setUp(self):
        """Set up test fixtures."""
        self.map = MapLibreMap(center=[40.7128, -74.0060], zoom=12)

    def test_get_layers(self):
        """Test getting layers from map."""
        # Initially should be empty
        self.assertEqual(self.map.get_layers(), {})

        # Add a layer
        layer_config = {"id": "test", "type": "circle", "source": "test"}
        self.map.add_layer("test", layer_config)

        layers = self.map.get_layers()
        self.assertIn("test", layers)
        self.assertEqual(layers["test"], layer_config)

    def test_get_sources(self):
        """Test getting sources from map."""
        # Initially should be empty
        self.assertEqual(self.map.get_sources(), {})

        # Add a source
        source_config = {"type": "geojson", "data": {}}
        self.map.add_source("test", source_config)

        sources = self.map.get_sources()
        self.assertIn("test", sources)
        self.assertEqual(sources["test"], source_config)

    def test_clear_layers(self):
        """Test clearing all layers."""
        # Add some layers
        self.map.add_layer("layer1", {"id": "layer1", "type": "circle"})
        self.map.add_layer("layer2", {"id": "layer2", "type": "fill"})

        self.assertEqual(len(self.map.get_layers()), 2)

        # Clear layers
        self.map.clear_layers()
        self.assertEqual(len(self.map.get_layers()), 0)

    def test_clear_sources(self):
        """Test clearing all sources."""
        # Add some sources
        self.map.add_source("source1", {"type": "geojson", "data": {}})
        self.map.add_source("source2", {"type": "geojson", "data": {}})

        self.assertEqual(len(self.map.get_sources()), 2)

        # Clear sources
        self.map.clear_sources()
        self.assertEqual(len(self.map.get_sources()), 0)

    def test_clear_all(self):
        """Test clearing all layers and sources."""
        # Add layers and sources
        self.map.add_source("source1", {"type": "geojson", "data": {}})
        self.map.add_layer(
            "layer1", {"id": "layer1", "type": "circle", "source": "source1"}
        )

        self.assertEqual(len(self.map.get_layers()), 1)
        self.assertEqual(len(self.map.get_sources()), 1)

        # Clear all
        self.map.clear_all()
        self.assertEqual(len(self.map.get_layers()), 0)
        self.assertEqual(len(self.map.get_sources()), 0)

    def test_add_raster_layer(self):
        """Test adding a raster layer."""
        self.map.add_raster_layer(
            layer_id="raster_test",
            source_url="https://example.com/tiles/{z}/{x}/{y}.png",
        )

        # Check that both source and layer were added
        sources = self.map.get_sources()
        layers = self.map.get_layers()

        self.assertIn("raster_test_source", sources)
        self.assertIn("raster_test", layers)
        self.assertEqual(layers["raster_test"]["type"], "raster")

    def test_add_vector_layer(self):
        """Test adding a vector layer."""
        self.map.add_vector_layer(
            layer_id="vector_test",
            source_url="https://example.com/tiles.json",
            source_layer="data_layer",
            layer_type="fill",
        )

        # Check that both source and layer were added
        sources = self.map.get_sources()
        layers = self.map.get_layers()

        self.assertIn("vector_test_source", sources)
        self.assertIn("vector_test", layers)
        self.assertEqual(layers["vector_test"]["type"], "fill")
        self.assertEqual(layers["vector_test"]["source-layer"], "data_layer")

    def test_add_image_layer(self):
        """Test adding an image layer."""
        coordinates = [[-80, 25], [-80, 26], [-79, 26], [-79, 25]]

        self.map.add_image_layer(
            layer_id="image_test",
            image_url="https://example.com/image.png",
            coordinates=coordinates,
        )

        # Check that both source and layer were added
        sources = self.map.get_sources()
        layers = self.map.get_layers()

        self.assertIn("image_test_source", sources)
        self.assertIn("image_test", layers)
        self.assertEqual(sources["image_test_source"]["type"], "image")
        self.assertEqual(sources["image_test_source"]["coordinates"], coordinates)


class TestLayerPersistence(unittest.TestCase):
    """Test cases for layer persistence across widget renders."""

    def test_layer_state_persistence(self):
        """Test that layers persist in widget state."""
        map_widget = MapLibreMap(center=[0, 0], zoom=1)

        # Add a layer
        layer_config = {"id": "persistent", "type": "circle", "source": "test"}
        source_config = {"type": "geojson", "data": {}}

        map_widget.add_source("test", source_config)
        map_widget.add_layer("persistent", layer_config)

        # Check internal state
        self.assertIn("persistent", map_widget._layers)
        self.assertIn("test", map_widget._sources)

        # Verify layer config is preserved
        self.assertEqual(map_widget._layers["persistent"], layer_config)
        self.assertEqual(map_widget._sources["test"], source_config)

    def test_layer_removal_from_state(self):
        """Test that removing layers updates the state."""
        map_widget = MapLibreMap(center=[0, 0], zoom=1)

        # Add and then remove a layer
        map_widget.add_source("test", {"type": "geojson", "data": {}})
        map_widget.add_layer("temp", {"id": "temp", "type": "circle", "source": "test"})

        self.assertIn("temp", map_widget._layers)
        self.assertIn("test", map_widget._sources)

        # Remove layer and source
        map_widget.remove_layer("temp")
        map_widget.remove_source("test")

        self.assertNotIn("temp", map_widget._layers)
        self.assertNotIn("test", map_widget._sources)


class TestMapboxMap(unittest.TestCase):
    """Test cases for the MapboxMap class."""

    def setUp(self):
        """Set up test fixtures."""
        self.map = MapboxMap(
            center=[37.7749, -122.4194],
            zoom=12,
            map_style="mapbox://styles/mapbox/streets-v12",
        )

    def test_initialization(self):
        """Test Mapbox map initialization."""
        self.assertEqual(self.map.center, [37.7749, -122.4194])
        self.assertEqual(self.map.zoom, 12)
        self.assertEqual(self.map.map_style, "mapbox://styles/mapbox/streets-v12")
        self.assertEqual(self.map.bearing, 0.0)
        self.assertEqual(self.map.pitch, 0.0)
        self.assertTrue(self.map.antialias)
        # Token handling depends on environment

    def test_access_token_handling(self):
        """Test access token management."""
        # Test setting access token
        test_token = "pk.test_token"
        self.map.set_access_token(test_token)
        self.assertEqual(self.map.access_token, test_token)

        # Test creating map with custom token
        custom_map = MapboxMap(access_token="pk.custom_token")
        self.assertEqual(custom_map.access_token, "pk.custom_token")

    def test_default_access_token(self):
        """Test default access token retrieval."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            token = MapboxMap._get_default_access_token()
            # Token could be empty if no environment variable set
            self.assertIsInstance(token, str)

    def test_mapbox_specific_methods(self):
        """Test Mapbox-specific methods."""
        # Test adding controls
        self.map.add_control("navigation", "top-left")
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addControl" for call in calls))

        # Test terrain
        terrain_config = {"source": "mapbox-terrain", "exaggeration": 1.5}
        self.map.set_terrain(terrain_config)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setTerrain" for call in calls))

        # Test fog
        fog_config = {"color": "rgb(186, 210, 235)", "high-color": "rgb(36, 92, 223)"}
        self.map.set_fog(fog_config)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setFog" for call in calls))

    def test_add_3d_buildings(self):
        """Test adding 3D buildings layer."""
        self.map.add_3d_buildings()

        # Check that the layer was added
        layers = self.map.get_layers()
        self.assertIn("3d-buildings", layers)

        layer_config = layers["3d-buildings"]
        self.assertEqual(layer_config["type"], "fill-extrusion")
        self.assertEqual(layer_config["source"], "composite")
        self.assertEqual(layer_config["source-layer"], "building")

    def test_mapbox_styles(self):
        """Test Mapbox style handling."""
        # Test setting standard Mapbox style
        self.map.set_style("mapbox://styles/mapbox/satellite-v9")
        self.assertEqual(self.map.map_style, "mapbox://styles/mapbox/satellite-v9")

        # Test setting custom style object
        custom_style = {"version": 8, "sources": {}, "layers": []}
        self.map.set_style(custom_style)

        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setStyle" for call in calls))

    def test_inheritance_from_mapwidget(self):
        """Test that MapboxMap inherits all MapWidget functionality."""
        # Test basic methods work
        self.map.set_center(40.7128, -74.0060)
        self.assertEqual(self.map.center, [40.7128, -74.0060])

        # Test layer management
        layer_config = {"id": "test", "type": "circle", "source": "test"}
        self.map.add_layer("test", layer_config)
        self.assertIn("test", self.map.get_layers())

        # Test source management
        source_config = {"type": "geojson", "data": {}}
        self.map.add_source("test", source_config)
        self.assertIn("test", self.map.get_sources())


class TestMapboxMapboxInteraction(unittest.TestCase):
    """Test interaction between MapLibre and Mapbox maps."""

    def test_independent_map_instances(self):
        """Test that MapLibre and Mapbox maps work independently."""
        # Create one of each type
        maplibre_map = MapLibreMap(center=[37.7749, -122.4194], zoom=10)
        mapbox_map = MapboxMap(center=[40.7128, -74.0060], zoom=12)

        # Verify they have different configurations
        self.assertNotEqual(maplibre_map.center, mapbox_map.center)
        self.assertNotEqual(maplibre_map.zoom, mapbox_map.zoom)
        self.assertNotEqual(maplibre_map.map_style, mapbox_map.map_style)

        # Add different layers to each
        maplibre_map.add_geojson_layer(
            "ml_layer", {"type": "FeatureCollection", "features": []}
        )
        mapbox_map.add_geojson_layer(
            "mb_layer", {"type": "FeatureCollection", "features": []}
        )

        # Verify layers are independent
        self.assertIn("ml_layer", maplibre_map.get_layers())
        self.assertNotIn("ml_layer", mapbox_map.get_layers())
        self.assertIn("mb_layer", mapbox_map.get_layers())
        self.assertNotIn("mb_layer", maplibre_map.get_layers())

    def test_different_javascript_modules(self):
        """Test that different map types use different JavaScript modules."""
        maplibre_map = MapLibreMap()
        mapbox_map = MapboxMap()

        # Check they use different implementations by verifying the content differs
        maplibre_content = str(maplibre_map._esm)
        mapbox_content = str(mapbox_map._esm)

        # Verify they contain different library imports
        self.assertIn("maplibre-gl", maplibre_content)
        self.assertIn("mapbox-gl-js", mapbox_content)
        self.assertNotEqual(maplibre_content, mapbox_content)

        # Check they use different CSS
        maplibre_css = str(maplibre_map._css)
        mapbox_css = str(mapbox_map._css)
        self.assertNotEqual(maplibre_css, mapbox_css)


class TestCesiumMap(unittest.TestCase):
    """Test cases for the CesiumMap class."""

    def setUp(self):
        """Set up test fixtures."""
        self.map = CesiumMap(
            center=[37.7749, -122.4194],
            zoom=12,
            camera_height=15000000,
        )

    def test_initialization(self):
        """Test Cesium map initialization."""
        self.assertEqual(self.map.center, [37.7749, -122.4194])
        self.assertEqual(self.map.zoom, 12)
        self.assertEqual(self.map.camera_height, 15000000)
        self.assertEqual(self.map.heading, 0.0)
        self.assertEqual(self.map.pitch, -90.0)
        self.assertEqual(self.map.roll, 0.0)
        self.assertTrue(self.map.base_layer_picker)
        self.assertFalse(self.map.timeline)  # Default is False based on implementation

    def test_access_token_handling(self):
        """Test access token management."""
        # Test setting access token
        test_token = "ey.test"
        self.map.set_access_token(test_token)
        self.assertEqual(self.map.access_token, test_token)

        # Test creating map with custom token
        custom_map = CesiumMap(access_token="custom_token")
        self.assertEqual(custom_map.access_token, "custom_token")

    def test_default_access_token(self):
        """Test default access token retrieval."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            token = CesiumMap._get_default_access_token()
            # Token could be empty if no environment variable set
            self.assertIsInstance(token, str)

    def test_cesium_specific_methods(self):
        """Test Cesium-specific methods."""
        # Test fly to
        self.map.fly_to(40.7128, -74.0060, height=20000000, duration=5.0)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "flyTo" for call in calls))

        # Test adding point
        point_id = self.map.add_point(
            40.7128, -74.0060, height=100000, name="Test Point"
        )
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addEntity" for call in calls))
        self.assertIsInstance(point_id, str)

        # Test adding billboard
        billboard_id = self.map.add_billboard(40.7128, -74.0060, image_url="test.png")
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addEntity" for call in calls))

        # Test adding polyline
        coordinates = [[40.0, -74.0, 0], [41.0, -75.0, 1000]]
        polyline_id = self.map.add_polyline(coordinates, width=5, color="#ff0000")
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addEntity" for call in calls))

        # Test adding polygon
        polygon_id = self.map.add_polygon(coordinates, color="#00ff00")
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addEntity" for call in calls))

    def test_entity_management(self):
        """Test entity management."""
        # Add an entity
        entity_id = self.map.add_point(40.0, -74.0, name="Test Entity")

        # Remove the entity
        self.map.remove_entity(entity_id)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "removeEntity" for call in calls))

        # Test zoom to entity
        self.map.zoom_to_entity(entity_id)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "zoomToEntity" for call in calls))

    def test_data_sources(self):
        """Test data source management."""
        # Test GeoJSON data source
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "Test Point"},
                }
            ],
        }

        self.map.add_geojson(geojson_data, options={"name": "Test GeoJSON"})
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addDataSource" for call in calls))

        # Test KML data source
        self.map.add_kml("https://example.com/test.kml", options={"name": "Test KML"})
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addDataSource" for call in calls))

        # Test CZML data source
        czml_data = [{"id": "document", "version": "1.0"}]
        self.map.add_czml(czml_data, options={"name": "Test CZML"})
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "addDataSource" for call in calls))

    def test_terrain_management(self):
        """Test terrain management."""
        # Test Cesium World Terrain
        self.map.set_cesium_world_terrain(request_water_mask=True)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setTerrain" for call in calls))

        # Test custom terrain
        self.map.set_terrain({"url": "https://example.com/terrain"})
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setTerrain" for call in calls))

        # Test disable terrain
        self.map.set_terrain(None)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setTerrain" for call in calls))

    def test_imagery_management(self):
        """Test imagery management."""
        # Test Bing Maps imagery
        self.map.set_imagery({"type": "bing", "key": "test_key", "mapStyle": "Aerial"})
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setImagery" for call in calls))

        # Test OpenStreetMap imagery
        self.map.set_imagery({"type": "osm"})
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setImagery" for call in calls))

    def test_scene_management(self):
        """Test scene management."""
        # Test scene modes
        self.map.set_scene_mode_3d()
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setScene3D" for call in calls))

        self.map.set_scene_mode_2d()
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setScene2D" for call in calls))

        self.map.set_scene_mode_columbus()
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "setSceneColumbusView" for call in calls))

        # Test lighting and fog
        self.map.enable_lighting(True)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "enableLighting" for call in calls))

        self.map.enable_fog(True)
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "enableFog" for call in calls))

    def test_camera_controls(self):
        """Test camera controls."""
        # Test home view
        self.map.home()
        calls = self.map._js_calls
        self.assertTrue(any(call["method"] == "home" for call in calls))

        # Test setting camera position
        self.map.set_camera_position(
            40.0, -74.0, 20000000, heading=45, pitch=-60, roll=10
        )
        self.assertEqual(self.map.center, [40.0, -74.0])
        self.assertEqual(self.map.camera_height, 20000000)
        self.assertEqual(self.map.heading, 45)
        self.assertEqual(self.map.pitch, -60)
        self.assertEqual(self.map.roll, 10)

    def test_inheritance_from_mapwidget(self):
        """Test that CesiumMap inherits all MapWidget functionality."""
        # Test basic methods work
        self.map.set_center(40.7128, -74.0060)
        self.assertEqual(self.map.center, [40.7128, -74.0060])

        # Test event handling
        callback = Mock()
        self.map.on_map_event("click", callback)
        self.assertIn("click", self.map._event_handlers)

    def test_cesium_widget_options(self):
        """Test Cesium widget configuration options."""
        # Test with custom options
        custom_map = CesiumMap(
            base_layer_picker=False,
            fullscreen_button=False,
            vr_button=False,
            geocoder=False,
            home_button=False,
            info_box=False,
            scene_mode_picker=False,
            selection_indicator=False,
            timeline=False,
            navigation_help_button=False,
            animation=False,
            should_animate=False,
        )

        self.assertFalse(custom_map.base_layer_picker)
        self.assertFalse(custom_map.fullscreen_button)
        self.assertFalse(custom_map.timeline)
        self.assertFalse(custom_map.animation)


class TestCesiumMapIntegration(unittest.TestCase):
    """Test integration between all map types including Cesium."""

    def test_independent_map_instances(self):
        """Test that all three map types work independently."""
        # Create one of each type
        maplibre_map = MapLibreMap(center=[37.7749, -122.4194], zoom=10)
        mapbox_map = MapboxMap(center=[40.7128, -74.0060], zoom=12)
        cesium_map = CesiumMap(
            center=[51.5074, -0.1278], zoom=8, camera_height=25000000
        )

        # Verify they have different configurations
        self.assertNotEqual(maplibre_map.center, mapbox_map.center)
        self.assertNotEqual(mapbox_map.center, cesium_map.center)
        self.assertNotEqual(maplibre_map.zoom, cesium_map.zoom)

        # Add different features to each
        maplibre_map.add_geojson_layer(
            "ml_layer", {"type": "FeatureCollection", "features": []}
        )
        mapbox_map.add_geojson_layer(
            "mb_layer", {"type": "FeatureCollection", "features": []}
        )
        cesium_map.add_point(51.5074, -0.1278, name="London")

        # Verify features are independent
        self.assertIn("ml_layer", maplibre_map.get_layers())
        self.assertNotIn("ml_layer", mapbox_map.get_layers())
        self.assertIn("mb_layer", mapbox_map.get_layers())
        self.assertNotIn("mb_layer", maplibre_map.get_layers())

        # Cesium uses entities, not layers
        cesium_calls = [
            call for call in cesium_map._js_calls if call["method"] == "addEntity"
        ]
        self.assertEqual(len(cesium_calls), 1)

    def test_different_javascript_modules(self):
        """Test that different map types use different JavaScript modules."""
        maplibre_map = MapLibreMap()
        mapbox_map = MapboxMap()
        cesium_map = CesiumMap()

        # Check they use different implementations by verifying the content differs
        maplibre_content = str(maplibre_map._esm)
        mapbox_content = str(mapbox_map._esm)
        cesium_content = str(cesium_map._esm)

        # Verify they contain different library imports
        self.assertIn("maplibre-gl", maplibre_content)
        self.assertIn("mapbox-gl-js", mapbox_content)
        self.assertIn("cesium.com", cesium_content)

        # Verify all three are different
        self.assertNotEqual(maplibre_content, mapbox_content)
        self.assertNotEqual(mapbox_content, cesium_content)
        self.assertNotEqual(maplibre_content, cesium_content)

        # Check they use different CSS
        maplibre_css = str(maplibre_map._css)
        mapbox_css = str(mapbox_map._css)
        cesium_css = str(cesium_map._css)

        self.assertNotEqual(maplibre_css, mapbox_css)
        self.assertNotEqual(mapbox_css, cesium_css)
        self.assertNotEqual(maplibre_css, cesium_css)


if __name__ == "__main__":
    unittest.main()
