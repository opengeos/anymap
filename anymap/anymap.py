"""Main module for anymap interactive mapping widgets.

This module provides backward compatibility by re-exporting all classes
from their new dedicated modules. All classes have been moved to separate
modules for better organization and maintainability.

For new code, consider importing directly from the specific modules:
- from anymap.base import MapWidget
- from anymap.maplibre import MapLibreMap
- from anymap.mapbox import MapboxMap
- from anymap.cesium import CesiumMap
- from anymap.potree import PotreeMap
- from anymap.deckgl import DeckGLMap
- from anymap.compare import MapCompare
"""

# Import all classes from their new dedicated modules
from .base import MapWidget
from .maplibre import MapLibreMap
from .mapbox import MapboxMap
from .cesium import CesiumMap
from .potree import PotreeMap
from .deckgl import DeckGLMap
from .compare import MapCompare

# Make all classes available when importing from this module
__all__ = [
    "MapWidget",
    "MapLibreMap",
    "MapboxMap",
    "CesiumMap",
    "PotreeMap",
    "DeckGLMap",
    "MapCompare",
]
