"""Utility functions for anymap library.

This module contains common utility functions used across the anymap library,
including functions for constructing map style URLs, handling API keys,
and working with different mapping service providers.

Functions:
    get_env_var: Retrieve environment variables or user data keys.
    construct_carto_style: Construct URL for Carto style.
    construct_amazon_style: Construct URL for Amazon Map style.
    construct_maptiler_style: Construct URL for MapTiler style.
    maptiler_3d_style: Generate 3D terrain style configuration.
    construct_maplibre_style: Construct MapLibre style configuration.

Example:
    Getting an environment variable:

    >>> from anymap.utils import get_env_var
    >>> api_key = get_env_var("MAPTILER_KEY")

    Constructing a style URL:

    >>> from anymap.utils import construct_maplibre_style
    >>> style = construct_maplibre_style("dark-matter")
"""

import json
import os
import requests
from typing import Optional, Dict, Any


def _in_colab_shell() -> bool:
    """Check if the code is running in a Google Colab shell."""
    import sys

    return "google.colab" in sys.modules


def get_env_var(name: Optional[str] = None, key: Optional[str] = None) -> Optional[str]:
    """
    Retrieves an environment variable. If a key is provided, it is returned directly. If a
    name is provided, the function attempts to retrieve the key from user data
    (if running in Google Colab) or from environment variables.

    Args:
        name (Optional[str], optional): The name of the key to retrieve. Defaults to None.
        key (Optional[str], optional): The key to return directly. Defaults to None.

    Returns:
        Optional[str]: The retrieved key, or None if no key was found.
    """
    if key is not None:
        return key
    if name is not None:
        try:
            if _in_colab_shell():
                from google.colab import userdata  # pylint: disable=E0611

                return userdata.get(name)
        except Exception:
            pass
        return os.environ.get(name)
    return None


def construct_carto_style(style: str) -> str:
    """
    Constructs a URL for a Carto style with an optional API key.
    The URL looks like this:
    https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json
    https://basemaps.cartocdn.com/gl/positron-gl-style/style.json
    """

    return f"https://basemaps.cartocdn.com/gl/{style.lower()}-gl-style/style.json"


def construct_amazon_style(
    map_style: str = "standard",
    region: str = "us-east-1",
    api_key: str = None,
    token: str = "AWS_MAPS_API_KEY",
) -> str:
    """
    Constructs a URL for an Amazon Map style.

    Args:
        map_style (str): The name of the MapTiler style to be accessed. It can be one of the following:
            standard, monochrome, satellite, hybrid.
        region (str): The region of the Amazon Map. It can be one of the following:
            us-east-1, us-west-2, eu-central-1, eu-west-1, ap-northeast-1, ap-northeast-2, ap-southeast-1, etc.
        api_key (str): The API key for the Amazon Map. If None, the function attempts to retrieve the API key using a predefined method.
        token (str): The token for the Amazon Map. If None, the function attempts to retrieve the API key using a predefined method.

    Returns:
        str: The URL for the requested Amazon Map style.
    """

    if map_style.lower() not in ["standard", "monochrome", "satellite", "hybrid"]:
        print(
            "Invalid map style. Please choose from amazon-standard, amazon-monochrome, amazon-satellite, or amazon-hybrid."
        )
        return None

    if api_key is None:
        api_key = get_env_var(token)
        if api_key is None:
            print("An API key is required to use the Amazon Map style.")
            return None

    url = f"https://maps.geo.{region}.amazonaws.com/v2/styles/{map_style.title()}/descriptor?key={api_key}"
    return url


def construct_maptiler_style(style: str, api_key: Optional[str] = None) -> str:
    """
    Constructs a URL for a MapTiler style with an optional API key.

    This function generates a URL for accessing a specific MapTiler map style. If an API key is not provided,
    it attempts to retrieve one using a predefined method. If the request to MapTiler fails, it defaults to
    a "liberty" style.

    Args:
        style (str): The name of the MapTiler style to be accessed. It can be one of the following:
            aquarelle, backdrop, basic, bright, dataviz, landscape, ocean, openstreetmap, outdoor,
            satellite, streets, toner, topo, winter, etc.
        api_key (Optional[str]): An optional API key for accessing MapTiler services. If None, the function
            attempts to retrieve the API key using a predefined method. Defaults to None.

    Returns:
        str: The URL for the requested MapTiler style. If the request fails, returns a URL for the "liberty" style.

    Raises:
        requests.exceptions.RequestException: If the request to the MapTiler API fails.
    """

    if api_key is None:
        api_key = get_env_var("MAPTILER_KEY")

    url = f"https://api.maptiler.com/maps/{style}/style.json?key={api_key}"

    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        # print(
        #     "Failed to retrieve the MapTiler style. Defaulting to OpenFreeMap 'liberty' style."
        # )
        url = "https://tiles.openfreemap.org/styles/liberty"

    return url


def maptiler_3d_style(
    style="satellite",
    exaggeration: float = 1,
    tile_size: int = 512,
    tile_type: str = None,
    max_zoom: int = 24,
    hillshade: bool = True,
    token: str = "MAPTILER_KEY",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get the 3D terrain style for the map.

    This function generates a style dictionary for the map that includes 3D terrain features.
    The terrain exaggeration and API key can be specified. If the API key is not provided,
    it will be retrieved using the specified token.

    Args:
        style (str): The name of the MapTiler style to be accessed. It can be one of the following:
            aquarelle, backdrop, basic, bright, dataviz, hillshade, landscape, ocean, openstreetmap, outdoor,
            satellite, streets, toner, topo, winter, etc.
        exaggeration (float, optional): The terrain exaggeration. Defaults to 1.
        tile_size (int, optional): The size of the tiles. Defaults to 512.
        tile_type (str, optional): The type of the tiles. It can be one of the following:
            webp, png, jpg. Defaults to None.
        max_zoom (int, optional): The maximum zoom level. Defaults to 24.
        hillshade (bool, optional): Whether to include hillshade. Defaults to True.
        token (str, optional): The token to use to retrieve the API key. Defaults to "MAPTILER_KEY".
        api_key (Optional[str], optional): The API key. If not provided, it will be retrieved using the token.

    Returns:
        Dict[str, Any]: The style dictionary for the map.

    Raises:
        ValueError: If the API key is not provided and cannot be retrieved using the token.
    """

    if api_key is None:
        api_key = get_env_var(token)

    if api_key is None:
        print("An API key is required to use the 3D terrain feature.")
        return "dark-matter"

    if style == "terrain":
        style = "satellite"
    elif style == "hillshade":
        style = None

    if tile_type is None:

        image_types = {
            "aquarelle": "webp",
            "backdrop": "png",
            "basic": "png",
            "basic-v2": "png",
            "bright": "png",
            "bright-v2": "png",
            "dataviz": "png",
            "hybrid": "jpg",
            "landscape": "png",
            "ocean": "png",
            "openstreetmap": "jpg",
            "outdoor": "png",
            "outdoor-v2": "png",
            "satellite": "jpg",
            "toner": "png",
            "toner-v2": "png",
            "topo": "png",
            "topo-v2": "png",
            "winter": "png",
            "winter-v2": "png",
        }
        if style in image_types:
            tile_type = image_types[style]
        else:
            tile_type = "png"

    layers = []

    if isinstance(style, str):
        layers.append({"id": style, "type": "raster", "source": style})

    if hillshade:
        layers.append(
            {
                "id": "hillshade",
                "type": "hillshade",
                "source": "hillshadeSource",
                "layout": {"visibility": "visible"},
                "paint": {"hillshade-shadow-color": "#473B24"},
            }
        )

    if style == "ocean":
        sources = {
            "terrainSource": {
                "type": "raster-dem",
                "url": f"https://api.maptiler.com/tiles/ocean-rgb/tiles.json?key={api_key}",
                "tileSize": tile_size,
            },
            "hillshadeSource": {
                "type": "raster-dem",
                "url": f"https://api.maptiler.com/tiles/ocean-rgb/tiles.json?key={api_key}",
                "tileSize": tile_size,
            },
        }
    else:
        sources = {
            "terrainSource": {
                "type": "raster-dem",
                "url": f"https://api.maptiler.com/tiles/terrain-rgb-v2/tiles.json?key={api_key}",
                "tileSize": tile_size,
            },
            "hillshadeSource": {
                "type": "raster-dem",
                "url": f"https://api.maptiler.com/tiles/terrain-rgb-v2/tiles.json?key={api_key}",
                "tileSize": tile_size,
            },
        }
    if isinstance(style, str):
        sources[style] = {
            "type": "raster",
            "tiles": [
                "https://api.maptiler.com/maps/"
                + style
                + "/{z}/{x}/{y}."
                + tile_type
                + "?key="
                + api_key
            ],
            "tileSize": tile_size,
            "attribution": "&copy; MapTiler",
            "maxzoom": max_zoom,
        }

    style = {
        "version": 8,
        "sources": sources,
        "layers": layers,
        "terrain": {"source": "terrainSource", "exaggeration": exaggeration},
    }

    return style


def construct_maplibre_style(style: str, **kwargs) -> str:
    """
    Constructs a URL for a MapLibre style.

    Args:
        style (str): The name of the MapLibre style to be accessed.
    """
    carto_basemaps = [
        "dark-matter",
        "positron",
        "voyager",
        "positron-nolabels",
        "dark-matter-nolabels",
        "voyager-nolabels",
    ]
    openfreemap_basemaps = [
        "liberty",
        "bright",
        "positron2",
    ]

    if isinstance(style, str):

        if style.startswith("https"):
            response = requests.get(style, timeout=10)
            if response.status_code != 200:
                print(
                    "The provided style URL is invalid. Falling back to 'dark-matter'."
                )
                style = "dark-matter"
            else:
                style = json.loads(response.text)
        elif style.startswith("3d-"):
            style = maptiler_3d_style(
                style=style.replace("3d-", "").lower(),
                exaggeration=kwargs.pop("exaggeration", 1),
                tile_size=kwargs.pop("tile_size", 512),
                hillshade=kwargs.pop("hillshade", True),
            )
        elif style.startswith("amazon-"):
            style = construct_amazon_style(
                map_style=style.replace("amazon-", "").lower(),
                region=kwargs.pop("region", "us-east-1"),
                api_key=kwargs.pop("api_key", None),
                token=kwargs.pop("token", "AWS_MAPS_API_KEY"),
            )

        elif style.lower() in carto_basemaps:
            style = construct_carto_style(style.lower())
        elif style.lower() in openfreemap_basemaps:
            if style == "positron2":
                style = "positron"
            style = f"https://tiles.openfreemap.org/styles/{style.lower()}"
        elif style == "demotiles":
            style = "https://demotiles.maplibre.org/style.json"
        else:
            style = construct_maptiler_style(style)

        if style in carto_basemaps:
            style = construct_carto_style(style)

    return style
