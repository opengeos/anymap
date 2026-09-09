"""Tests for Plotly Dash map implementation."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys

from anymap import DashMap
import anymap


class TestDashMap(unittest.TestCase):
    """Test cases for the DashMap class."""

    def test_import(self):
        """Test importing DashMap from anymap and anymap.dash."""
        self.assertTrue(hasattr(anymap, "DashMap"))
        from anymap.dash import DashMap as DirectDashMap

        self.assertIs(DashMap, DirectDashMap)

    def test_issue_example(self):
        """Test the exact snippet requested in the issue."""
        m = DashMap(
            center=[-74.0060, 40.7128],  # New York City
            zoom=13,
            height="500px",
            bearing=45,  # Map rotation
            pitch=60,  # 3D tilt
        )

        self.assertEqual(m.center, [-74.0060, 40.7128])
        self.assertEqual(m.zoom, 13)
        self.assertEqual(m.height, "500px")
        self.assertEqual(m.bearing, 45)
        self.assertEqual(m.pitch, 60)

    def test_default_initialization(self):
        """Test default DashMap initialization."""
        m = DashMap()
        self.assertEqual(m.center, [0.0, 20.0])
        self.assertEqual(m.zoom, 1.0)
        self.assertEqual(m.width, "100%")
        self.assertEqual(m.height, "500px")
        self.assertEqual(m.bearing, 0.0)
        self.assertEqual(m.pitch, 0.0)
        self.assertIn("dark-matter", m.style)

    def test_custom_initialization(self):
        """Test custom initialization parameters."""
        m = DashMap(
            center=[-122.4194, 37.7749],
            zoom=10,
            style="osm",
            width="800px",
            height="400px",
            bearing=30,
            pitch=45,
        )
        self.assertEqual(m.center, [-122.4194, 37.7749])
        self.assertEqual(m.zoom, 10)
        self.assertIn("openfreemap", m.style)
        self.assertEqual(m.width, "800px")
        self.assertEqual(m.height, "400px")
        self.assertEqual(m.bearing, 30)
        self.assertEqual(m.pitch, 45)

    def test_maplibre_methods(self):
        """Test that inherited MapLibre methods work properly on DashMap."""
        m = DashMap(center=[-74.0060, 40.7128], zoom=12)

        # set_center and set_zoom
        m.set_center(-0.1278, 51.5074)
        self.assertEqual(m.center, [-0.1278, 51.5074])

        m.set_zoom(15)
        self.assertEqual(m.zoom, 15)

        # fly_to
        m.fly_to(2.3522, 48.8566, zoom=14)
        self.assertTrue(len(m._js_calls) > 0)

        # add_marker
        m.add_marker(-74.0060, 40.7128, popup="NYC")
        self.assertTrue(any(call["method"] == "addMarker" for call in m._js_calls))

    def test_to_html(self):
        """Test HTML export for DashMap."""
        m = DashMap(center=[-74.0060, 40.7128], zoom=13, height="500px")
        html_str = m.to_html(title="DashMap Test")
        self.assertIsInstance(html_str, str)
        self.assertIn("<!DOCTYPE html>", html_str)
        self.assertIn("DashMap Test", html_str)

    def test_to_dash_component_without_dash(self):
        """Test error when dash is not installed."""
        m = DashMap()
        with patch.dict(sys.modules, {"dash": None, "dash.html": None}):
            with self.assertRaises(ImportError):
                m.to_dash_component()

    def test_to_dash_component_with_dash(self):
        """Test exporting DashMap as a Dash component."""
        m = DashMap(center=[-74.0060, 40.7128], zoom=13, height="500px")

        mock_dash = MagicMock()
        mock_html = MagicMock()
        mock_dash.html = mock_html
        mock_iframe = MagicMock()
        mock_html.Iframe = mock_iframe

        with patch.dict(sys.modules, {"dash": mock_dash, "dash.html": mock_html}):
            comp = m.to_dash_component(id="test-map", width="600px", height="400px")
            mock_iframe.assert_called_once()
            args, kwargs = mock_iframe.call_args
            self.assertEqual(kwargs["id"], "test-map")
            self.assertEqual(kwargs["style"]["width"], "600px")
            self.assertEqual(kwargs["style"]["height"], "400px")
            self.assertIn("srcDoc", kwargs)

            # Test alias to_component
            comp2 = m.to_component(id="test-map-2")
            self.assertEqual(mock_iframe.call_count, 2)

    def test_to_dash_without_dash(self):
        """Test error when dash is not installed for to_dash."""
        m = DashMap()
        with patch.dict(sys.modules, {"dash": None, "dash.html": None}):
            with self.assertRaises(ImportError):
                m.to_dash()

    def test_to_dash_with_dash(self):
        """Test to_dash app creation."""
        m = DashMap(center=[-74.0060, 40.7128], zoom=13, height="500px")

        mock_dash = MagicMock()
        mock_dash_app = MagicMock()
        mock_dash.Dash.return_value = mock_dash_app
        mock_html = MagicMock()
        mock_dash.html = mock_html

        with patch.dict(sys.modules, {"dash": mock_dash, "dash.html": mock_html}):
            app = m.to_dash(title="Custom Title")
            mock_dash.Dash.assert_called_once()
            self.assertEqual(app, mock_dash_app)

    def test_to_plotly_without_plotly(self):
        """Test error when plotly is not installed for to_plotly."""
        m = DashMap()
        with patch.dict(sys.modules, {"plotly": None, "plotly.graph_objects": None}):
            with self.assertRaises(ImportError):
                m.to_plotly()

    def test_to_plotly_with_plotly(self):
        """Test to_plotly conversion."""
        m = DashMap(
            center=[-74.0060, 40.7128], zoom=13, height="500px", bearing=45, pitch=60
        )

        mock_plotly = MagicMock()
        mock_go = MagicMock()
        mock_plotly.graph_objects = mock_go
        mock_fig = MagicMock()
        mock_go.Figure.return_value = mock_fig

        with patch.dict(
            sys.modules, {"plotly": mock_plotly, "plotly.graph_objects": mock_go}
        ):
            fig = m.to_plotly()
            mock_go.Figure.assert_called_once()
            mock_fig.update_layout.assert_called_once()
            self.assertEqual(fig, mock_fig)

            # Test alias to_figure
            fig2 = m.to_figure()
            self.assertEqual(fig2, mock_fig)

    def test_run_dash(self):
        """Test run_dash method."""
        m = DashMap()
        mock_app = MagicMock()
        with patch.object(m, "to_dash", return_value=mock_app):
            m.run_dash(port=8050, host="127.0.0.1", debug=False)
            mock_app.run.assert_called_once_with(
                port=8050, host="127.0.0.1", debug=False
            )


if __name__ == "__main__":
    unittest.main()
