#!/usr/bin/env python3
"""
AnyMap Demo Script

This script demonstrates the key features of the AnyMap package.
Run this in a Jupyter notebook to see the interactive maps.
"""

from anymap import MapLibreMap
import json


def demo_basic_map():
    """Demo: Basic map creation"""
    print("🗺️  Creating a basic map...")

    m = MapLibreMap(
        center=[37.7749, -122.4194], zoom=12, height="400px"  # San Francisco
    )

    print("✅ Basic map created!")
    return m


def demo_markers_and_popups(map_instance):
    """Demo: Adding markers with popups"""
    print("📍 Adding markers with popups...")

    # Add multiple markers
    locations = [
        {"name": "Golden Gate Bridge", "coords": [37.8199, -122.4783]},
        {"name": "Alcatraz Island", "coords": [37.8270, -122.4230]},
        {"name": "Fisherman's Wharf", "coords": [37.8080, -122.4177]},
    ]

    for loc in locations:
        map_instance.add_marker(
            lat=loc["coords"][0],
            lng=loc["coords"][1],
            popup=f"<h3>{loc['name']}</h3><p>San Francisco landmark</p>",
        )

    print("✅ Added markers for SF landmarks!")


def demo_geojson_layer(map_instance):
    """Demo: Adding GeoJSON data"""
    print("🌍 Adding GeoJSON layer...")

    # Create sample GeoJSON data
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
                "properties": {
                    "name": "San Francisco",
                    "population": 875000,
                    "category": "major",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.2711, 37.8044]},
                "properties": {
                    "name": "Oakland",
                    "population": 430000,
                    "category": "major",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.0838, 37.4220]},
                "properties": {
                    "name": "Palo Alto",
                    "population": 67000,
                    "category": "minor",
                },
            },
        ],
    }

    # Add the layer with data-driven styling
    map_instance.add_geojson_layer(
        layer_id="bay-area-cities",
        geojson_data=geojson_data,
        layer_type="circle",
        paint={
            "circle-radius": ["case", ["==", ["get", "category"], "major"], 15, 8],
            "circle-color": [
                "case",
                ["==", ["get", "category"], "major"],
                "#ff0000",
                "#0000ff",
            ],
            "circle-opacity": 0.8,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
        },
    )

    print("✅ Added Bay Area cities layer with data-driven styling!")


def demo_event_handling(map_instance):
    """Demo: Event handling"""
    print("🖱️  Setting up event handlers...")

    def handle_click(event):
        lat, lng = event["lngLat"]
        print(f"   🎯 Map clicked at: {lat:.4f}, {lng:.4f}")

    def handle_zoom(event):
        zoom = event.get("zoom", 0)
        print(f"   🔍 Zoom changed to: {zoom:.2f}")

    map_instance.on_map_event("click", handle_click)
    map_instance.on_map_event("zoomend", handle_zoom)

    print("✅ Event handlers registered! Click and zoom the map to see events.")


def demo_dynamic_updates(map_instance):
    """Demo: Dynamic map updates"""
    print("🔄 Demonstrating dynamic updates...")

    # Fly to New York
    map_instance.fly_to(40.7128, -74.0060, zoom=13)
    print("✈️  Flying to New York City...")

    # Add a marker there
    map_instance.add_marker(
        40.7128, -74.0060, popup="<h2>New York City</h2><p>The Big Apple!</p>"
    )

    print("✅ Added NYC marker!")


def demo_multiple_maps():
    """Demo: Multiple independent map instances"""
    print("🌐 Creating multiple independent maps...")

    cities = [
        {"name": "London", "coords": [51.5074, -0.1278]},
        {"name": "Tokyo", "coords": [35.6762, 139.6503]},
        {"name": "Sydney", "coords": [-33.8688, 151.2093]},
    ]

    maps = []
    for city in cities:
        m = MapLibreMap(center=city["coords"], zoom=11, height="300px")
        m.add_marker(
            city["coords"][0], city["coords"][1], popup=f"<h3>{city['name']}</h3>"
        )
        maps.append(m)
        print(f"   🏙️  Created map for {city['name']}")

    print(f"✅ Created {len(maps)} independent map instances!")
    return maps


def main():
    """Run the complete demo"""
    print("🚀 AnyMap Package Demo")
    print("=" * 50)

    # Demo 1: Basic map
    main_map = demo_basic_map()
    print()

    # Demo 2: Markers and popups
    demo_markers_and_popups(main_map)
    print()

    # Demo 3: GeoJSON layers
    demo_geojson_layer(main_map)
    print()

    # Demo 4: Event handling
    demo_event_handling(main_map)
    print()

    # Demo 5: Dynamic updates
    demo_dynamic_updates(main_map)
    print()

    # Demo 6: Multiple maps
    additional_maps = demo_multiple_maps()
    print()

    print("🎉 Demo completed!")
    print("\nTo see the interactive maps, run this script in a Jupyter notebook:")
    print("1. Copy this script to a notebook cell")
    print("2. Run main() and display the returned map objects")
    print("3. Interact with the maps to test events and functionality")

    total_maps = 1 + len(additional_maps)
    print(f"\nTotal maps created: {total_maps}")

    return {"main_map": main_map, "city_maps": additional_maps}


if __name__ == "__main__":
    result = main()
    print(
        "\nMaps created successfully! In a Jupyter notebook, you can display them with:"
    )
    print("result['main_map']  # Display the main San Francisco map")
    print("result['city_maps'][0]  # Display the London map")
    print("result['city_maps'][1]  # Display the Tokyo map")
    print("result['city_maps'][2]  # Display the Sydney map")
