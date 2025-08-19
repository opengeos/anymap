"""Draw control styling utilities for AnyMap.

This module provides utilities for creating and managing draw control styles
for MapLibre GL JS and other mapping backends.
"""

from typing import Any, Dict, List


def create_draw_styles(
    point_color: str = "#3bb2d0",
    line_color: str = "#3bb2d0",
    polygon_fill_color: str = "#3bb2d0",
    polygon_stroke_color: str = "#3bb2d0",
    active_color: str = "#fbb03b",
    point_radius: float = 3,
    line_width: float = 2,
    polygon_opacity: float = 0.1,
) -> List[Dict[str, Any]]:
    """Create custom draw control styles.

    Args:
        point_color: Color for point features
        line_color: Color for line features
        polygon_fill_color: Fill color for polygon features
        polygon_stroke_color: Stroke color for polygon features
        active_color: Color for active/selected features
        point_radius: Radius for point features
        line_width: Width for line features
        polygon_opacity: Opacity for polygon fill

    Returns:
        List of style definitions for MapLibre draw control
    """
    return [
        # Point styles
        {
            "id": "gl-draw-point",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["!=", "meta", "midpoint"]],
            "paint": {"circle-radius": point_radius, "circle-color": point_color},
        },
        # Line styles
        {
            "id": "gl-draw-line",
            "type": "line",
            "filter": ["all", ["==", "$type", "LineString"], ["!=", "mode", "static"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": line_color, "line-width": line_width},
        },
        # Polygon fill
        {
            "id": "gl-draw-polygon-fill",
            "type": "fill",
            "filter": ["all", ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
            "paint": {
                "fill-color": polygon_fill_color,
                "fill-outline-color": polygon_stroke_color,
                "fill-opacity": polygon_opacity,
            },
        },
        # Polygon stroke
        {
            "id": "gl-draw-polygon-stroke",
            "type": "line",
            "filter": ["all", ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": polygon_stroke_color, "line-width": line_width},
        },
        # Active point
        {
            "id": "gl-draw-point-active",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "active", "true"]],
            "paint": {"circle-radius": point_radius + 1, "circle-color": active_color},
        },
        # Active line
        {
            "id": "gl-draw-line-active",
            "type": "line",
            "filter": ["all", ["==", "$type", "LineString"], ["==", "active", "true"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": active_color, "line-width": line_width + 1},
        },
        # Active polygon fill
        {
            "id": "gl-draw-polygon-fill-active",
            "type": "fill",
            "filter": ["all", ["==", "$type", "Polygon"], ["==", "active", "true"]],
            "paint": {
                "fill-color": active_color,
                "fill-outline-color": active_color,
                "fill-opacity": polygon_opacity,
            },
        },
        # Active polygon stroke
        {
            "id": "gl-draw-polygon-stroke-active",
            "type": "line",
            "filter": ["all", ["==", "$type", "Polygon"], ["==", "active", "true"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": active_color, "line-width": line_width + 1},
        },
        # Static styles (for completed features)
        {
            "id": "gl-draw-point-static",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "mode", "static"]],
            "paint": {"circle-radius": point_radius, "circle-color": point_color},
        },
        {
            "id": "gl-draw-line-static",
            "type": "line",
            "filter": ["all", ["==", "$type", "LineString"], ["==", "mode", "static"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": line_color, "line-width": line_width},
        },
        {
            "id": "gl-draw-polygon-fill-static",
            "type": "fill",
            "filter": ["all", ["==", "$type", "Polygon"], ["==", "mode", "static"]],
            "paint": {
                "fill-color": polygon_fill_color,
                "fill-outline-color": polygon_stroke_color,
                "fill-opacity": polygon_opacity,
            },
        },
        {
            "id": "gl-draw-polygon-stroke-static",
            "type": "line",
            "filter": ["all", ["==", "$type", "Polygon"], ["==", "mode", "static"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": polygon_stroke_color, "line-width": line_width},
        },
        # Midpoint styles (for adding vertices)
        {
            "id": "gl-draw-polygon-midpoint",
            "type": "circle",
            "filter": ["all", ["==", "$type", "Point"], ["==", "meta", "midpoint"]],
            "paint": {"circle-radius": 3, "circle-color": active_color},
        },
        # Vertex styles for editing
        {
            "id": "gl-draw-polygon-and-line-vertex-stroke-inactive",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["==", "meta", "vertex"],
                ["!=", "meta", "midpoint"],
                ["!=", "active", "true"],
            ],
            "paint": {"circle-radius": 5, "circle-color": "#fff"},
        },
        {
            "id": "gl-draw-polygon-and-line-vertex-inactive",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["==", "meta", "vertex"],
                ["!=", "meta", "midpoint"],
                ["!=", "active", "true"],
            ],
            "paint": {"circle-radius": 3, "circle-color": active_color},
        },
        # Active vertex styles
        {
            "id": "gl-draw-point-point-stroke-inactive",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["==", "active", "false"],
                ["!=", "meta", "midpoint"],
            ],
            "paint": {"circle-radius": 5, "circle-color": "#fff"},
        },
        {
            "id": "gl-draw-point-inactive",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["==", "active", "false"],
                ["!=", "meta", "midpoint"],
            ],
            "paint": {"circle-radius": 3, "circle-color": point_color},
        },
        {
            "id": "gl-draw-point-stroke-active",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["!=", "meta", "midpoint"],
                ["==", "active", "true"],
            ],
            "paint": {"circle-radius": 7, "circle-color": "#fff"},
        },
        {
            "id": "gl-draw-polygon-fill-inactive",
            "type": "fill",
            "filter": ["all", ["==", "$type", "Polygon"], ["==", "active", "false"]],
            "paint": {
                "fill-color": polygon_fill_color,
                "fill-outline-color": polygon_stroke_color,
                "fill-opacity": polygon_opacity,
            },
        },
        {
            "id": "gl-draw-polygon-stroke-inactive",
            "type": "line",
            "filter": ["all", ["==", "$type", "Polygon"], ["==", "active", "false"]],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": polygon_stroke_color, "line-width": line_width},
        },
        {
            "id": "gl-draw-line-inactive",
            "type": "line",
            "filter": [
                "all",
                ["==", "$type", "LineString"],
                ["==", "active", "false"],
            ],
            "layout": {"line-cap": "round", "line-join": "round"},
            "paint": {"line-color": line_color, "line-width": line_width},
        },
        # Line vertex styles
        {
            "id": "gl-draw-line-vertex-stroke-active",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["==", "meta", "vertex"],
                ["!=", "meta", "midpoint"],
            ],
            "paint": {"circle-radius": 5, "circle-color": active_color},
        },
        {
            "id": "gl-draw-polygon-vertex-active",
            "type": "circle",
            "filter": [
                "all",
                ["==", "$type", "Point"],
                ["==", "meta", "vertex"],
                ["!=", "meta", "midpoint"],
            ],
            "paint": {"circle-radius": 5, "circle-color": active_color},
        },
    ]
