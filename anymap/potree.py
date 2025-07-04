"""Potree point cloud viewer implementation of the map widget."""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional

from .base import MapWidget

# Load Potree-specific js and css
with open(pathlib.Path(__file__).parent / "static" / "potree_widget.js", "r") as f:
    _esm_potree = f.read()

with open(pathlib.Path(__file__).parent / "static" / "potree_widget.css", "r") as f:
    _css_potree = f.read()


class PotreeMap(MapWidget):
    """Potree point cloud viewer implementation of the map widget."""

    # Potree-specific traits
    point_cloud_url = traitlets.Unicode("").tag(sync=True)
    point_size = traitlets.Float(1.0).tag(sync=True)
    point_size_type = traitlets.Unicode("adaptive").tag(
        sync=True
    )  # "fixed", "adaptive", "attenuation"
    point_shape = traitlets.Unicode("square").tag(sync=True)  # "square", "circle"
    min_node_size = traitlets.Float(100.0).tag(sync=True)
    show_grid = traitlets.Bool(False).tag(sync=True)
    grid_size = traitlets.Float(10.0).tag(sync=True)
    grid_color = traitlets.Unicode("#aaaaaa").tag(sync=True)
    background_color = traitlets.Unicode("#000000").tag(sync=True)
    edl_enabled = traitlets.Bool(True).tag(sync=True)  # Eye Dome Lighting
    edl_radius = traitlets.Float(1.0).tag(sync=True)
    edl_strength = traitlets.Float(1.0).tag(sync=True)

    # Camera controls
    camera_position = traitlets.List([0.0, 0.0, 10.0]).tag(sync=True)
    camera_target = traitlets.List([0.0, 0.0, 0.0]).tag(sync=True)
    fov = traitlets.Float(60.0).tag(sync=True)
    near_clip = traitlets.Float(0.1).tag(sync=True)
    far_clip = traitlets.Float(1000.0).tag(sync=True)

    # Define the JavaScript module path
    _esm = _esm_potree
    _css = _css_potree

    def __init__(
        self,
        point_cloud_url: str = "",
        width: str = "100%",
        height: str = "600px",
        point_size: float = 1.0,
        point_size_type: str = "adaptive",
        point_shape: str = "square",
        camera_position: List[float] = [0.0, 0.0, 10.0],
        camera_target: List[float] = [0.0, 0.0, 0.0],
        fov: float = 60.0,
        background_color: str = "#000000",
        edl_enabled: bool = True,
        show_grid: bool = False,
        **kwargs,
    ):
        """Initialize Potree map widget.

        Args:
            point_cloud_url: URL to the point cloud metadata.json file
            width: Widget width
            height: Widget height
            point_size: Size of rendered points
            point_size_type: How point size is calculated ("fixed", "adaptive", "attenuation")
            point_shape: Shape of rendered points ("square", "circle")
            camera_position: Initial camera position [x, y, z]
            camera_target: Camera look-at target [x, y, z]
            fov: Field of view in degrees
            background_color: Background color of the viewer
            edl_enabled: Enable Eye Dome Lighting for better depth perception
            show_grid: Show coordinate grid
        """
        super().__init__(
            width=width,
            height=height,
            point_cloud_url=point_cloud_url,
            point_size=point_size,
            point_size_type=point_size_type,
            point_shape=point_shape,
            camera_position=camera_position,
            camera_target=camera_target,
            fov=fov,
            background_color=background_color,
            edl_enabled=edl_enabled,
            show_grid=show_grid,
            **kwargs,
        )

    def load_point_cloud(
        self, point_cloud_url: str, point_cloud_name: Optional[str] = None
    ) -> None:
        """Load a point cloud from URL.

        Args:
            point_cloud_url: URL to the point cloud metadata.json file
            point_cloud_name: Optional name for the point cloud
        """
        self.point_cloud_url = point_cloud_url
        options = {"url": point_cloud_url}
        if point_cloud_name:
            options["name"] = point_cloud_name
        self.call_js_method("loadPointCloud", options)

    def set_point_size(self, size: float) -> None:
        """Set the point size."""
        self.point_size = size

    def set_point_size_type(self, size_type: str) -> None:
        """Set the point size type.

        Args:
            size_type: "fixed", "adaptive", or "attenuation"
        """
        if size_type not in ["fixed", "adaptive", "attenuation"]:
            raise ValueError("size_type must be 'fixed', 'adaptive', or 'attenuation'")
        self.point_size_type = size_type

    def set_point_shape(self, shape: str) -> None:
        """Set the point shape.

        Args:
            shape: "square" or "circle"
        """
        if shape not in ["square", "circle"]:
            raise ValueError("shape must be 'square' or 'circle'")
        self.point_shape = shape

    def set_camera_position(
        self, position: List[float], target: Optional[List[float]] = None
    ) -> None:
        """Set camera position and optionally target.

        Args:
            position: Camera position [x, y, z]
            target: Camera target [x, y, z] (optional)
        """
        self.camera_position = position
        if target:
            self.camera_target = target

    def fit_to_screen(self) -> None:
        """Fit the point cloud to the screen."""
        self.call_js_method("fitToScreen")

    def enable_edl(self, enabled: bool = True) -> None:
        """Enable or disable Eye Dome Lighting.

        Args:
            enabled: Whether to enable EDL
        """
        self.edl_enabled = enabled

    def set_edl_settings(self, radius: float = 1.0, strength: float = 1.0) -> None:
        """Set Eye Dome Lighting parameters.

        Args:
            radius: EDL radius
            strength: EDL strength
        """
        self.edl_radius = radius
        self.edl_strength = strength

    def show_coordinate_grid(
        self, show: bool = True, size: float = 10.0, color: str = "#aaaaaa"
    ) -> None:
        """Show or hide coordinate grid.

        Args:
            show: Whether to show the grid
            size: Grid size
            color: Grid color
        """
        self.show_grid = show
        self.grid_size = size
        self.grid_color = color

    def set_background_color(self, color: str) -> None:
        """Set the background color.

        Args:
            color: Background color (hex format like "#000000")
        """
        self.background_color = color

    def clear_point_clouds(self) -> None:
        """Clear all point clouds from the viewer."""
        self.call_js_method("clearPointClouds")

    def get_camera_position(self) -> List[float]:
        """Get current camera position."""
        return list(self.camera_position)

    def get_camera_target(self) -> List[float]:
        """Get current camera target."""
        return list(self.camera_target)

    def take_screenshot(self) -> None:
        """Take a screenshot of the current view."""
        self.call_js_method("takeScreenshot")

    def set_fov(self, fov: float) -> None:
        """Set field of view.

        Args:
            fov: Field of view in degrees
        """
        self.fov = fov

    def set_clip_distances(self, near: float, far: float) -> None:
        """Set near and far clipping distances.

        Args:
            near: Near clipping distance
            far: Far clipping distance
        """
        self.near_clip = near
        self.far_clip = far

    def add_measurement(self, measurement_type: str = "distance") -> None:
        """Add measurement tool.

        Args:
            measurement_type: Type of measurement ("distance", "area", "volume", "angle")
        """
        self.call_js_method("addMeasurement", measurement_type)

    def clear_measurements(self) -> None:
        """Clear all measurements."""
        self.call_js_method("clearMeasurements")

    def set_quality(self, quality: str = "medium") -> None:
        """Set rendering quality.

        Args:
            quality: Rendering quality ("low", "medium", "high")
        """
        if quality not in ["low", "medium", "high"]:
            raise ValueError("quality must be 'low', 'medium', or 'high'")
        self.call_js_method("setQuality", quality)

    def load_multiple_point_clouds(self, point_clouds: List[Dict[str, str]]) -> None:
        """Load multiple point clouds.

        Args:
            point_clouds: List of point cloud configs with 'url' and optional 'name' keys
        """
        self.call_js_method("loadMultiplePointClouds", point_clouds)

    def set_classification_visibility(self, classifications: Dict[int, bool]) -> None:
        """Set visibility of point classifications.

        Args:
            classifications: Dict mapping classification codes to visibility
        """
        self.call_js_method("setClassificationVisibility", classifications)

    def filter_by_elevation(
        self,
        min_elevation: Optional[float] = None,
        max_elevation: Optional[float] = None,
    ) -> None:
        """Filter points by elevation.

        Args:
            min_elevation: Minimum elevation to show
            max_elevation: Maximum elevation to show
        """
        options = {}
        if min_elevation is not None:
            options["min"] = min_elevation
        if max_elevation is not None:
            options["max"] = max_elevation
        self.call_js_method("filterByElevation", options)

    def clear_filters(self) -> None:
        """Clear all filters."""
        self.call_js_method("clearFilters")
