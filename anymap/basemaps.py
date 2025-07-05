"""Basemap utilities for anymap library.

This module provides utilities for working with basemaps from xyzservices,
a registry of XYZ tile services. It includes functions to get available
basemaps and filter them based on various criteria.

Functions:
    get_xyz_dict: Get a dictionary of available XYZ tile services.

Variables:
    available_basemaps: Dictionary of available basemap providers.

Example:
    Using available basemaps:

    >>> from anymap.basemaps import available_basemaps
    >>> list(available_basemaps.keys())[:5]
    ['CartoDB.DarkMatter', 'CartoDB.Positron', 'Esri.WorldImagery', ...]
"""

import collections
import xyzservices
from typing import Dict, Any


def get_xyz_dict(free_only: bool = True, france: bool = False) -> Dict[str, Any]:
    """Returns a dictionary of XYZ tile services.

    Retrieves XYZ tile services from the xyzservices library with optional
    filtering to include only free services and/or exclude France-specific
    services.

    Args:
        free_only: Whether to return only free XYZ tile services that do not
                  require an access token. Defaults to True.
        france: Whether to include Geoportail France basemaps. These are
               often restricted to France and may not work globally.
               Defaults to False.

    Returns:
        Dictionary mapping basemap names to their TileProvider configurations.
        Each configuration includes properties like URL template, attribution,
        and other metadata.

    Example:
        >>> basemaps = get_xyz_dict(free_only=True, france=False)
        >>> 'OpenStreetMap.Mapnik' in basemaps
        True
        >>> len(basemaps) > 100
        True
    """
    xyz_bunch = xyzservices.providers

    if free_only:
        xyz_bunch = xyz_bunch.filter(requires_token=False)
    if not france:
        xyz_bunch = xyz_bunch.filter(
            function=lambda tile: "france" not in dict(tile)["name"].lower()
        )

    xyz_dict = xyz_bunch.flatten()

    for key, value in xyz_dict.items():
        tile = xyzservices.TileProvider(value)
        if "type" not in tile:
            tile["type"] = "xyz"
        xyz_dict[key] = tile

    xyz_dict = collections.OrderedDict(sorted(xyz_dict.items()))
    return xyz_dict


available_basemaps: Dict[str, Any] = get_xyz_dict()
"""Dictionary of available basemap providers.

This variable contains all available basemap providers from xyzservices,
filtered to include only free services and exclude France-specific services
by default. Each key is a basemap name (e.g., 'OpenStreetMap.Mapnik') and
each value is a TileProvider configuration object.

Example:
    >>> from anymap.basemaps import available_basemaps
    >>> basemap = available_basemaps['OpenStreetMap.Mapnik']
    >>> url = basemap.build_url()
    >>> print(url)
    https://tile.openstreetmap.org/{z}/{x}/{y}.png
"""
