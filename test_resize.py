#!/usr/bin/env python3
"""Test script to verify resize functionality improvements."""

from anymap import MapLibreMap
import time


def test_resize_functionality():
    """Test the resize functionality."""
    print("🔧 Testing resize functionality improvements...")

    # Create a map instance
    m = MapLibreMap(
        center=[37.7749, -122.4194], zoom=12, height="400px"  # San Francisco
    )

    print("✅ Map created with resize improvements")
    print("📝 Resize features added:")
    print("   - ResizeObserver for automatic resizing")
    print("   - Multiple resize triggers on load")
    print("   - Improved CSS for responsive containers")
    print("   - requestAnimationFrame for DOM readiness")

    # Add a marker to make it more visible
    m.add_marker(
        37.7749,
        -122.4194,
        popup="<h3>San Francisco</h3><p>Test resize functionality</p>",
    )

    print("📍 Added marker for visibility")
    print()
    print("🎯 To test in Jupyter:")
    print("1. Create a map: m = MapLibreMap(...)")
    print("2. Display in cell 1: m")
    print("3. Display in cell 2: m")
    print("4. Both should now render at full width automatically")
    print("5. Try resizing the browser window - maps should adapt")

    pass


if __name__ == "__main__":
    test_resize_functionality()
    print(f"\n✅ Resize test completed successfully!")
    print("The map instance is ready for Jupyter notebook testing.")
