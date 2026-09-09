"""Plotly Dash implementation of the map widget.

This module provides the DashMap class which implements an interactive map
widget with Plotly Dash integration and MapLibre GL JS rendering.
"""

import pathlib
import traitlets
from typing import Dict, List, Any, Optional, Union, Sequence, Tuple, Callable
import json

from .maplibre import MapLibreMap

# Load widget js and css
try:
    with open(
        pathlib.Path(__file__).parent / "static" / "dash_widget.js",
        "r",
        encoding="utf-8",
    ) as f:
        _esm_dash = f.read()
except FileNotFoundError:
    try:
        with open(
            pathlib.Path(__file__).parent / "static" / "maplibre_widget.js",
            "r",
            encoding="utf-8",
        ) as f:
            _esm_dash = f.read()
    except FileNotFoundError:
        _esm_dash = "console.error('Dash widget JS not found');"

try:
    with open(
        pathlib.Path(__file__).parent / "static" / "dash_widget.css",
        "r",
        encoding="utf-8",
    ) as f:
        _css_dash = f.read()
except FileNotFoundError:
    try:
        with open(
            pathlib.Path(__file__).parent / "static" / "maplibre_widget.css",
            "r",
            encoding="utf-8",
        ) as f:
            _css_dash = f.read()
    except FileNotFoundError:
        _css_dash = "/* Dash widget CSS not found */"


class DashMap(MapLibreMap):
    """Plotly Dash map widget implementation.

    This class provides an interactive map widget with Plotly Dash integration.
    It supports MapLibre GL JS rendering in Jupyter notebooks as well as
    seamless integration into Plotly Dash web applications.

    Attributes:
        center: Map center coordinates as [longitude, latitude] or [latitude, longitude].
        zoom: Map zoom level.
        style: Map style configuration (URL string or style object).
        width: Map container width as CSS string.
        height: Map container height as CSS string.
        bearing: Map rotation in degrees (0-360).
        pitch: Map tilt in degrees (0-60).

    Example:
        >>> from anymap import DashMap
        >>> m = DashMap(
        ...     center=[-74.0060, 40.7128],  # New York City
        ...     zoom=13,
        ...     height="500px",
        ...     bearing=45,  # Map rotation
        ...     pitch=60     # 3D tilt
        ... )
        >>> m
    """

    _esm = _esm_dash
    _css = _css_dash

    def __init__(
        self,
        center: List[float] = [0.0, 20.0],
        zoom: float = 1.0,
        style: Union[str, Dict[str, Any]] = "dark-matter",
        width: str = "100%",
        height: str = "500px",
        bearing: float = 0.0,
        pitch: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """Initialize Plotly Dash map widget.

        Args:
            center: Map center coordinates as [longitude, latitude] or [latitude, longitude]. Default is [0, 20].
            zoom: Initial zoom level (typically 0-20). Default is 1.0.
            style: MapLibre style URL string or style object dictionary. Default is "dark-matter".
            width: Widget width as CSS string (e.g., "100%", "800px"). Default is "100%".
            height: Widget height as CSS string (e.g., "500px", "600px"). Default is "500px".
            bearing: Map bearing (rotation) in degrees (0-360). Default is 0.0.
            pitch: Map pitch (tilt) in degrees (0-60). Default is 0.0.
            **kwargs: Additional keyword arguments passed to MapLibreMap.
        """
        super().__init__(
            center=center,
            zoom=zoom,
            style=style,
            width=width,
            height=height,
            bearing=bearing,
            pitch=pitch,
            **kwargs,
        )

    def to_dash(
        self,
        app: Optional[Any] = None,
        title: str = "AnyMap Dash App",
        port: int = 8050,
        host: str = "127.0.0.1",
        debug: bool = True,
        inline: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Create or configure a Plotly Dash application with the map.

        Args:
            app: Optional existing dash.Dash instance. If None, a new Dash app is created.
            title: Title for the Dash application. Default is "AnyMap Dash App".
            port: Port to run the server on when running. Default is 8050.
            host: Host address to run the server on. Default is "127.0.0.1".
            debug: Whether to run Dash in debug mode. Default is True.
            inline: Whether to display inline in Jupyter notebooks. Default is False.
            **kwargs: Additional arguments passed to dash.Dash().

        Returns:
            The dash.Dash application instance.
        """
        try:
            import dash
            from dash import html
        except ImportError:
            raise ImportError(
                "The 'dash' package is required for this feature. "
                "Please install it using 'pip install dash'."
            )

        if app is None:
            app = dash.Dash(__name__, title=title, **kwargs)
            app.layout = html.Div(
                [
                    html.H1(
                        title,
                        style={"textAlign": "center", "fontFamily": "sans-serif"},
                    ),
                    self.to_dash_component(id="anymap-dash-component"),
                ],
                style={"padding": "10px", "height": "100vh", "boxSizing": "border-box"},
            )

        if inline:
            if hasattr(app, "run"):
                app.run(jupyter_mode="inline", port=port, host=host, debug=debug)
            elif hasattr(app, "run_server"):
                app.run_server(port=port, host=host, debug=debug)

        return app

    def to_dash_component(
        self,
        id: str = "dash-map",
        width: Optional[str] = None,
        height: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Export the map as a Plotly Dash component (html.Iframe).

        Args:
            id: HTML element ID for the component. Default is "dash-map".
            width: Width of the map component (CSS string). Defaults to widget width.
            height: Height of the map component (CSS string). Defaults to widget height.
            **kwargs: Additional HTML iframe attributes or styling.

        Returns:
            dash.html.Iframe component.
        """
        try:
            from dash import html
        except ImportError:
            raise ImportError(
                "The 'dash' package is required for this feature. "
                "Please install it using 'pip install dash'."
            )

        comp_width = width or self.width or "100%"
        comp_height = height or self.height or "500px"

        style = {
            "width": comp_width,
            "height": comp_height,
            "border": "none",
        }
        if "style" in kwargs:
            style.update(kwargs.pop("style"))

        html_content = self.to_html(width=comp_width, height=comp_height)
        return html.Iframe(
            id=id,
            srcDoc=html_content,
            style=style,
            **kwargs,
        )

    to_component = to_dash_component

    def to_plotly(self) -> Any:
        """Convert the current map into a Plotly Figure object.

        Returns:
            plotly.graph_objects.Figure instance.
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            raise ImportError(
                "The 'plotly' package is required for this feature. "
                "Please install it using 'pip install plotly'."
            )

        fig = go.Figure()

        # Parse style
        mapbox_style = "open-street-map"
        if isinstance(self.style, str):
            if "carto" in self.style.lower():
                mapbox_style = (
                    "carto-positron"
                    if "light" in self.style.lower() or "positron" in self.style.lower()
                    else "carto-darkmatter"
                )
            elif "osm" in self.style.lower() or "openstreetmap" in self.style.lower():
                mapbox_style = "open-street-map"
            elif "satellite" in self.style.lower():
                mapbox_style = "white-bg"

        # Height integer if possible
        fig_height = None
        if isinstance(self.height, str) and self.height.endswith("px"):
            try:
                fig_height = int(self.height[:-2])
            except ValueError:
                pass

        fig.update_layout(
            mapbox=dict(
                style=mapbox_style,
                center=dict(lat=self.center[1], lon=self.center[0]),
                zoom=self.zoom,
                bearing=self.bearing,
                pitch=self.pitch,
            ),
            margin=dict(r=0, t=0, b=0, l=0),
            height=fig_height or 500,
        )
        return fig

    to_figure = to_plotly

    def run_dash(
        self,
        port: int = 8050,
        host: str = "127.0.0.1",
        debug: bool = True,
        **kwargs: Any,
    ) -> None:
        """Run the map as a standalone Plotly Dash web application.

        Args:
            port: Port to run the server on. Default is 8050.
            host: Host address. Default is "127.0.0.1".
            debug: Whether to run in debug mode. Default is True.
            **kwargs: Additional keyword arguments passed to app.run() or app.run_server().
        """
        app = self.to_dash()
        if hasattr(app, "run"):
            app.run(port=port, host=host, debug=debug, **kwargs)
        elif hasattr(app, "run_server"):
            app.run_server(port=port, host=host, debug=debug, **kwargs)
