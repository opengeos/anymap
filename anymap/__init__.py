"""Top-level package for anymap."""

__author__ = """Qiusheng Wu"""
__email__ = "giswqs@gmail.com"
__version__ = "0.4.1"

from .base import MapWidget
from .maplibre import MapLibreMap
from .mapbox import MapboxMap
from .cesium import CesiumMap
from .potree import PotreeMap
from .deckgl import DeckGLMap
from .leaflet import LeafletMap
from .openlayers import OpenLayersMap
from .keplergl import KeplerGLMap
from .compare import MapCompare

__all__ = [
    "MapWidget",
    "MapLibreMap",
    "MapboxMap",
    "CesiumMap",
    "PotreeMap",
    "DeckGLMap",
    "LeafletMap",
    "OpenLayersMap",
    "KeplerGLMap",
    "MapCompare",
]
