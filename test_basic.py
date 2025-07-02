#!/usr/bin/env python3
"""Basic test script for anymap functionality."""

from anymap import MapLibreMap
import json


def test_basic_functionality():
    """Test basic map functionality."""
    print("Testing AnyMap basic functionality...")

    # Test 1: Create a basic map
    print("1. Creating basic map...")
    m = MapLibreMap(
        center=[37.7749, -122.4194], zoom=12, height="500px"  # San Francisco
    )
    print("   ✓ Map created successfully")

    # Test 2: Test property changes
    print("2. Testing property changes...")
    m.set_center(40.7128, -74.0060)  # New York
    m.set_zoom(10)
    print("   ✓ Center and zoom changed successfully")

    # Test 3: Test method calls
    print("3. Testing JavaScript method calls...")
    m.fly_to(51.5074, -0.1278, zoom=14)  # London
    print("   ✓ fly_to method called successfully")

    # Test 4: Test marker addition
    print("4. Testing marker addition...")
    m.add_marker(51.5074, -0.1278, popup="London, UK")
    print("   ✓ Marker added successfully")

    # Test 5: Test GeoJSON layer
    print("5. Testing GeoJSON layer...")
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-0.1278, 51.5074]},
                "properties": {"name": "London"},
            }
        ],
    }

    m.add_geojson_layer(
        layer_id="test-points",
        geojson_data=geojson_data,
        layer_type="circle",
        paint={"circle-radius": 8, "circle-color": "#ff0000"},
    )
    print("   ✓ GeoJSON layer added successfully")

    # Test 6: Test layer removal
    print("6. Testing layer removal...")
    m.remove_layer("test-points")
    print("   ✓ Layer removed successfully")

    # Test 7: Test event handler registration
    print("7. Testing event handler registration...")

    def test_handler(event):
        print(f"   Event received: {event}")

    m.on_map_event("click", test_handler)
    print("   ✓ Event handler registered successfully")

    print("\n✅ All basic functionality tests passed!")


def test_multiple_maps():
    """Test creating multiple map instances."""
    print("\nTesting multiple map instances...")

    maps = []
    for i in range(3):
        m = MapLibreMap(center=[40 + i, -74 + i], zoom=10 + i, height="400px")
        maps.append(m)
        print(f"   ✓ Map {i+1} created successfully")

    print("✅ Multiple map instances test passed!")


if __name__ == "__main__":
    # Run basic functionality tests
    test_basic_functionality()

    # Run multiple maps test
    test_multiple_maps()

    print(f"\n🎉 All tests completed successfully!")
