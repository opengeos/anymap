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
import warnings
from typing import Optional, Dict, Any, Union, List, Tuple


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


def replace_top_level_hyphens(d: Union[Dict, Any]) -> Union[Dict, Any]:
    """
    Replaces hyphens with underscores in top-level dictionary keys.

    Args:
        d (Union[Dict, Any]): The input dictionary or any other data type.

    Returns:
        Union[Dict, Any]: The modified dictionary with top-level keys having hyphens replaced with underscores,
        or the original input if it's not a dictionary.
    """
    if isinstance(d, dict):
        return {k.replace("-", "_"): v for k, v in d.items()}
    return d


def replace_hyphens_in_keys(d: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """
    Recursively replaces hyphens with underscores in dictionary keys.

    Args:
        d (Union[Dict, List, Any]): The input dictionary, list or any other data type.

    Returns:
        Union[Dict, List, Any]: The modified dictionary or list with keys having hyphens replaced with underscores,
        or the original input if it's not a dictionary or list.
    """
    if isinstance(d, dict):
        return {k.replace("-", "_"): replace_hyphens_in_keys(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [replace_hyphens_in_keys(i) for i in d]
    else:
        return d


def replace_underscores_in_keys(d: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """
    Recursively replaces underscores with hyphens in dictionary keys.

    Args:
        d (Union[Dict, List, Any]): The input dictionary, list or any other data type.

    Returns:
        Union[Dict, List, Any]: The modified dictionary or list with keys having underscores replaced with hyphens,
        or the original input if it's not a dictionary or list.
    """
    if isinstance(d, dict):
        return {
            k.replace("_", "-"): replace_underscores_in_keys(v) for k, v in d.items()
        }
    elif isinstance(d, list):
        return [replace_underscores_in_keys(i) for i in d]
    else:
        return d


def get_unique_name(name: str, names: list, overwrite: bool = False) -> str:
    """
    Generates a unique name based on the input name and existing names.

    Args:
        name (str): The base name to generate a unique name from.
        names (list): A list of existing names to check against.
        overwrite (bool, optional): If True, the function will return the original name even if it exists in the list. Defaults to False.

    Returns:
        str: A unique name based on the input name.
    """
    if overwrite or name not in names:
        return name
    else:
        counter = 1
        while True:
            unique_name = f"{name}_{counter}"
            if unique_name not in names:
                return unique_name
            counter += 1


def check_color(in_color: Union[str, Tuple, List]) -> str:
    """Checks the input color and returns the corresponding hex color code.

    Args:
        in_color (str or tuple or list): It can be a string (e.g., 'red', '#ffff00', 'ffff00', 'ff0') or RGB tuple/list (e.g., (255, 127, 0)).

    Returns:
        str: A hex color code.
    """
    from matplotlib import colors

    out_color = "#000000"  # default black color
    # Handle RGB tuple or list
    if isinstance(in_color, (tuple, list)) and len(in_color) == 3:
        # rescale color if necessary
        if all(isinstance(item, int) for item in in_color):
            # Ensure values are floats between 0 and 1 for to_hex
            in_color = [c / 255.0 for c in in_color]
        try:
            return colors.to_hex(in_color)
        except ValueError:
            print(
                f"The provided RGB color ({in_color}) is invalid. Using the default black color."
            )
            return out_color

    # Handle string color input
    elif isinstance(in_color, str):
        try:
            # Try converting directly (handles color names and hex with #)
            return colors.to_hex(in_color)
        except ValueError:
            try:
                # Try again by adding an extra # (handles hex without #)
                return colors.to_hex(f"#{in_color}")
            except ValueError:
                print(
                    f"The provided color string ({in_color}) is invalid. Using the default black color."
                )
                return out_color
    else:
        print(
            f"The provided color type ({type(in_color)}) is invalid. Using the default black color."
        )
        return out_color


def get_cog_metadata(url: str, crs: str = "EPSG:4326") -> Optional[Dict[str, Any]]:
    """Retrieve metadata from a Cloud Optimized GeoTIFF (COG) file.

    This function fetches metadata from a COG file using rasterio.
    The metadata includes information such as offset, scale, NoData value, and bounding box.

    Note:
        This feature corresponds to the getCogMetadata function in maplibre-cog-protocol,
        which is marked as [unstable] in the library documentation. Some metadata internals
        may change in future releases.

    Args:
        url (str): The URL of the COG file to retrieve metadata from.
        crs (str, optional): The coordinate reference system to use for the output bbox.
            Defaults to "EPSG:4326" (WGS84 lat/lon). Set to None to use the COG's native CRS.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing COG metadata with keys such as:
            - bounds: BoundingBox in the specified CRS
            - bbox: Bounding box coordinates [west, south, east, north] in the specified CRS
            - width: Width of the raster in pixels
            - height: Height of the raster in pixels
            - crs: Original coordinate reference system of the COG
            - output_crs: CRS of the returned bbox (if reprojected)
            - transform: Affine transformation matrix
            - count: Number of bands
            - dtypes: Data types for each band
            - nodata: NoData value
            - scale: Scale value (if available)
            - offset: Offset value (if available)
        Returns None if metadata retrieval fails.

    Example:
        >>> from anymap.utils import get_cog_metadata
        >>> url = "https://example.com/data.tif"
        >>> # Get metadata with bbox in WGS84 (default)
        >>> metadata = get_cog_metadata(url)
        >>> if metadata:
        ...     print(f"Bounding box (WGS84): {metadata.get('bbox')}")
        >>>
        >>> # Get metadata in native CRS
        >>> metadata = get_cog_metadata(url, crs=None)
        >>> if metadata:
        ...     print(f"Bounding box (native): {metadata.get('bbox')}")

    Raises:
        ImportError: If rasterio is not installed.
    """
    try:
        import rasterio
        from rasterio.errors import RasterioIOError
        from rasterio.warp import transform_bounds

        with rasterio.open(url) as src:
            # Get bounds in native CRS
            native_bounds = src.bounds
            native_crs = src.crs

            # Determine output CRS and bbox
            if crs and native_crs and str(native_crs) != crs:
                # Reproject bounds to target CRS
                try:
                    reprojected_bounds = transform_bounds(
                        native_crs,
                        crs,
                        native_bounds.left,
                        native_bounds.bottom,
                        native_bounds.right,
                        native_bounds.top,
                    )
                    output_bbox = [
                        reprojected_bounds[0],  # west
                        reprojected_bounds[1],  # south
                        reprojected_bounds[2],  # east
                        reprojected_bounds[3],  # north
                    ]
                    output_crs = crs
                except Exception as e:
                    print(f"Warning: Failed to reproject bounds to {crs}: {e}")
                    print(f"Using native CRS {native_crs} instead.")
                    output_bbox = [
                        native_bounds.left,
                        native_bounds.bottom,
                        native_bounds.right,
                        native_bounds.top,
                    ]
                    output_crs = str(native_crs)
            else:
                # Use native CRS
                output_bbox = [
                    native_bounds.left,
                    native_bounds.bottom,
                    native_bounds.right,
                    native_bounds.top,
                ]
                output_crs = str(native_crs) if native_crs else None

            metadata = {
                "bounds": native_bounds,
                "bbox": output_bbox,
                "width": src.width,
                "height": src.height,
                "crs": str(native_crs) if native_crs else None,
                "output_crs": output_crs,
                "transform": list(src.transform),
                "count": src.count,
                "dtypes": src.dtypes,
                "nodata": src.nodata,
            }

            # Add scale and offset if available
            if src.scales and len(src.scales) > 0:
                metadata["scale"] = src.scales[0]
            if src.offsets and len(src.offsets) > 0:
                metadata["offset"] = src.offsets[0]

            return metadata

    except ImportError:
        # If rasterio is not available, provide a helpful message
        print(
            "COG metadata retrieval requires rasterio. Install it with: pip install rasterio"
        )
        print(
            "Alternatively, use the get_cog_metadata method on a MapLibreMap instance "
            "which uses the JavaScript maplibre-cog-protocol library."
        )
        return None
    except RasterioIOError as e:
        print(f"Failed to open COG file: {e}")
        return None
    except Exception as e:
        print(f"Failed to retrieve COG metadata: {e}")
        return None


def get_local_tile_url(
    source,
    port="default",
    indexes=None,
    colormap=None,
    vmin=None,
    vmax=None,
    nodata=None,
    client_args={"cors_all": True},
    return_client=False,
    **kwargs: Any,
):
    """Generate an ipyleaflet/folium TileLayer from a local raster dataset or remote Cloud Optimized GeoTIFF (COG).
        If you are using this function in JupyterHub on a remote server and the raster does not render properly, try
        running the following two lines before calling this function:

        import os
        os.environ['LOCALTILESERVER_CLIENT_PREFIX'] = 'proxy/{port}'

    Args:
        source (str): The path to the GeoTIFF file or the URL of the Cloud Optimized GeoTIFF.
        port (str, optional): The port to use for the server. Defaults to "default".
        indexes (int, optional): The band(s) to use. Band indexing starts at 1. Defaults to None.
        colormap (str, optional): The name of the colormap from `matplotlib` to use when plotting a single band. See
          `https://matplotlib.org/stable/gallery/color/colormap_reference.html` Default is greyscale.
        vmin (float, optional): The minimum value to use when colormapping the colormap when plotting a single band. Defaults to None.
        vmax (float, optional): The maximum value to use when colormapping the colormap when plotting a single band. Defaults to None.
        nodata (float, optional): The value from the band to use to interpret as not valid data. Defaults to None.
        client_args (dict, optional): Additional arguments to pass to the TileClient. Defaults to {}.
        return_client (bool, optional): If True, the tile client will be returned. Defaults to False.

    Returns:
        An ipyleaflet.TileLayer or folium.TileLayer.
    """
    import rasterio
    from localtileserver import TileClient

    # Handle legacy localtileserver kwargs
    if "cmap" in kwargs:
        warnings.warn(
            "`cmap` is a deprecated keyword argument for get_local_tile_layer. Please use `colormap`."
        )
    if "palette" in kwargs:
        warnings.warn(
            "`palette` is a deprecated keyword argument for get_local_tile_layer. Please use `colormap`."
        )
    if "band" in kwargs or "bands" in kwargs:
        warnings.warn(
            "`band` and `bands` are deprecated keyword arguments for get_local_tile_layer. Please use `indexes`."
        )
    if "projection" in kwargs:
        warnings.warn(
            "`projection` is a deprecated keyword argument for get_local_tile_layer and will be ignored."
        )
    if "style" in kwargs:
        warnings.warn(
            "`style` is a deprecated keyword argument for get_local_tile_layer and will be ignored."
        )

    if "max_zoom" not in kwargs:
        kwargs["max_zoom"] = 30
    if "max_native_zoom" not in kwargs:
        kwargs["max_native_zoom"] = 30
    if "cmap" in kwargs:
        colormap = kwargs.pop("cmap")
    if "palette" in kwargs:
        colormap = kwargs.pop("palette")
    if "band" in kwargs:
        indexes = kwargs.pop("band")
    if "bands" in kwargs:
        indexes = kwargs.pop("bands")

    for key in client_args:
        kwargs[key] = client_args[key]

    # Make it compatible with binder and JupyterHub
    if os.environ.get("JUPYTERHUB_SERVICE_PREFIX") is not None:
        os.environ["LOCALTILESERVER_CLIENT_PREFIX"] = (
            f"{os.environ['JUPYTERHUB_SERVICE_PREFIX'].lstrip('/')}/proxy/{{port}}"
        )

    if "prefix" in kwargs:
        os.environ["LOCALTILESERVER_CLIENT_PREFIX"] = kwargs["prefix"]
        kwargs.pop("prefix")

    # if "show_loading" not in kwargs:
    #     kwargs["show_loading"] = False

    if isinstance(source, str):
        if not source.startswith("http"):
            if source.startswith("~"):
                source = os.path.expanduser(source)
    elif isinstance(source, TileClient) or isinstance(
        source, rasterio.io.DatasetReader
    ):
        pass

    else:
        raise ValueError("The source must either be a string or TileClient")

    if nodata is None:
        nodata = get_api_key("NODATA")
        if isinstance(nodata, str):
            nodata = float(nodata)

    if isinstance(colormap, str):
        colormap = colormap.lower()

    client = TileClient(source, port=port, **client_args)
    url = client.get_tile_url(
        indexes=indexes,
        colormap=colormap,
        vmin=vmin,
        vmax=vmax,
        nodata=nodata,
    )

    if return_client:
        return url, client
    else:
        return url


def get_api_key(name: Optional[str] = None, key: Optional[str] = None) -> Optional[str]:
    """
    Retrieves an API key. If a key is provided, it is returned directly. If a
    name is provided, the function attempts to retrieve the key from user data
    (if running in Google Colab) or from environment variables.

    Args:
        name (Optional[str], optional): The name of the key to retrieve. Defaults to None.
        key (Optional[str], optional): The key to return directly. Defaults to None.

    Returns:
        The retrieved key, or None if no key was found.
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


def write_image_colormap(image, colormap, output_path=None):
    """
    Apply or update a colormap to a raster image.

    Args:
        image (str, rasterio.io.DatasetReader, rioxarray.DataArray):
            The input image. It can be:
            - A file path to a raster image (string).
            - A rasterio dataset.
            - A rioxarray DataArray.
        colormap (dict): A dictionary defining the colormap (value: (R, G, B, A)).
        output_path (str, optional): Path to save the updated raster image.
            If None, the original file is updated in-memory.

    Returns:
        Path to the updated raster image.

    Raises:
        ValueError: If the input image type is unsupported.
    """
    import rasterio
    import rioxarray
    import xarray as xr

    dataset = None
    src_profile = None
    src_data = None

    if isinstance(image, str):  # File path
        with rasterio.open(image) as ds:
            dataset = ds
            src_profile = ds.profile
            src_data = ds.read(1)  # Assuming single-band
    elif isinstance(image, rasterio.io.DatasetReader):  # rasterio dataset
        dataset = image
        src_profile = dataset.profile
        src_data = dataset.read(1)  # Assuming single-band
    elif isinstance(image, xr.DataArray):  # rioxarray DataArray
        source = image.encoding.get("source")
        if source:
            with rasterio.open(source) as ds:
                dataset = ds
                src_profile = ds.profile
                src_data = ds.read(1)  # Assuming single-band
        else:
            raise ValueError("Cannot apply colormap: DataArray does not have a source.")
    else:
        raise ValueError(
            "Unsupported input type. Provide a file path, rasterio dataset, or rioxarray DataArray."
        )

    # Ensure the dataset is single-band
    if dataset.count != 1:
        raise ValueError(
            "Colormaps can only be applied to single-band raster datasets."
        )

    # Update the profile and colormap
    src_profile.update(dtype=src_data.dtype, count=1)

    if not output_path:
        output_path = "output_with_colormap.tif"

    # Check and sanitize colormap
    fixed_colormap = {}
    for k, v in colormap.items():
        if not isinstance(k, int):
            k = int(k)
        if len(v) == 3:  # RGB
            fixed_colormap[k] = tuple(int(c) for c in v)
        elif len(v) == 4:  # RGBA
            fixed_colormap[k] = tuple(
                int(c) for c in v[:3]
            )  # Drop alpha for compatibility
        else:
            raise ValueError(f"Invalid colormap value: {v}")

    # Write the updated dataset with the colormap
    with rasterio.open(output_path, "w", **src_profile) as dst:
        dst.write(src_data, 1)
        dst.write_colormap(1, fixed_colormap)

    return output_path


def array_to_memory_file(
    array,
    source: str = None,
    dtype: str = None,
    compress: str = "deflate",
    transpose: bool = True,
    cellsize: float = None,
    crs: str = None,
    transform: tuple = None,
    driver="COG",
    colormap: dict = None,
    **kwargs: Any,
) -> Any:
    """Convert a NumPy array to a memory file.

    Args:
        array (numpy.ndarray): The input NumPy array.
        source (str, optional): Path to the source file to extract metadata from. Defaults to None.
        dtype (str, optional): The desired data type of the array. Defaults to None.
        compress (str, optional): The compression method for the output file. Defaults to "deflate".
        transpose (bool, optional): Whether to transpose the array from (bands, rows, columns) to (rows, columns, bands). Defaults to True.
        cellsize (float, optional): The cell size of the array if source is not provided. Defaults to None.
        crs (str, optional): The coordinate reference system of the array if source is not provided. Defaults to None.
        transform (tuple, optional): The affine transformation matrix if source is not provided.
            Can be rio.transform() or a tuple like (0.5, 0.0, -180.25, 0.0, -0.5, 83.780361). Defaults to None.
        driver (str, optional): The driver to use for creating the output file, such as 'GTiff'. Defaults to "COG".
        colormap (dict, optional): A dictionary defining the colormap (value: (R, G, B, A)).
        **kwargs (Any): Additional keyword arguments to be passed to the rasterio.open() function.

    Returns:
        The rasterio dataset reader object for the converted array.
    """
    import numpy as np
    import rasterio
    import xarray as xr
    from rasterio.transform import Affine

    if isinstance(array, xr.DataArray):
        coords = [coord for coord in array.coords]
        if coords[0] == "time":
            x_dim = coords[1]
            y_dim = coords[2]
            array = (
                array.isel(time=0).rename({y_dim: "y", x_dim: "x"}).transpose("y", "x")
            )
        if hasattr(array, "rio"):
            if hasattr(array.rio, "crs"):
                if array.rio.crs is not None:
                    crs = array.rio.crs
            if transform is None and hasattr(array.rio, "transform"):
                transform = array.rio.transform()
        elif source is None:
            if hasattr(array, "encoding"):
                if "source" in array.encoding:
                    source = array.encoding["source"]
        array = array.values

    if array.ndim == 3 and transpose:
        array = np.transpose(array, (1, 2, 0))
    if source is not None:
        with rasterio.open(source) as src:
            crs = src.crs
            transform = src.transform
            if compress is None:
                compress = src.compression
    else:
        if crs is None:
            raise ValueError(
                "crs must be provided if source is not provided, such as EPSG:3857"
            )

        if transform is None:
            if cellsize is None:
                raise ValueError("cellsize must be provided if source is not provided")
            # Define the geotransformation parameters
            xmin, ymin, xmax, ymax = (
                0,
                0,
                cellsize * array.shape[1],
                cellsize * array.shape[0],
            )
            # (west, south, east, north, width, height)
            transform = rasterio.transform.from_bounds(
                xmin, ymin, xmax, ymax, array.shape[1], array.shape[0]
            )
        elif isinstance(transform, Affine):
            pass
        elif isinstance(transform, (tuple, list)):
            transform = Affine(*transform)

        kwargs["transform"] = transform

    if dtype is None:
        # Determine the minimum and maximum values in the array
        min_value = np.min(array)
        max_value = np.max(array)
        # Determine the best dtype for the array
        if min_value >= 0 and max_value <= 1:
            dtype = np.float32
        elif min_value >= 0 and max_value <= 255:
            dtype = np.uint8
        elif min_value >= -128 and max_value <= 127:
            dtype = np.int8
        elif min_value >= 0 and max_value <= 65535:
            dtype = np.uint16
        elif min_value >= -32768 and max_value <= 32767:
            dtype = np.int16
        else:
            dtype = np.float64

    # Convert the array to the best dtype
    array = array.astype(dtype)
    # Define the GeoTIFF metadata
    metadata = {
        "driver": driver,
        "height": array.shape[0],
        "width": array.shape[1],
        "dtype": array.dtype,
        "crs": crs,
        "transform": transform,
    }

    if array.ndim == 2:
        metadata["count"] = 1
    elif array.ndim == 3:
        metadata["count"] = array.shape[2]
    if compress is not None:
        metadata["compress"] = compress

    metadata.update(**kwargs)

    # Create a new memory file and write the array to it
    memory_file = rasterio.MemoryFile()
    dst = memory_file.open(**metadata)

    # Check and sanitize colormap
    fixed_colormap = {}

    if colormap is None:
        colormap = {}

    for k, v in colormap.items():
        if not isinstance(k, int):
            k = int(k)
        if len(v) == 3:  # RGB
            fixed_colormap[k] = tuple(int(c) for c in v)
        elif len(v) == 4:  # RGBA
            fixed_colormap[k] = tuple(
                int(c) for c in v[:3]
            )  # Drop alpha for compatibility
        else:
            raise ValueError(f"Invalid colormap value: {v}")

    if array.ndim == 2:
        dst.write(array, 1)
        if colormap:
            dst.write_colormap(1, fixed_colormap)
    elif array.ndim == 3:
        for i in range(array.shape[2]):
            dst.write(array[:, :, i], i + 1)
            if colormap:
                dst.write_colormap(i + 1, fixed_colormap)

    dst.close()
    # Read the dataset from memory
    dataset_reader = rasterio.open(dst.name, mode="r")

    return dataset_reader


def array_to_image(
    array,
    output: str = None,
    source: str = None,
    dtype: str = None,
    compress: str = "deflate",
    transpose: bool = True,
    cellsize: float = None,
    crs: str = None,
    transform: tuple = None,
    driver: str = "COG",
    colormap: dict = None,
    **kwargs: Any,
) -> str:
    """Save a NumPy array as a GeoTIFF using the projection information from an existing GeoTIFF file.

    Args:
        array (np.ndarray): The NumPy array to be saved as a GeoTIFF.
        output (str): The path to the output image. If None, a temporary file will be created. Defaults to None.
        source (str, optional): The path to an existing GeoTIFF file with map projection information. Defaults to None.
        dtype (np.dtype, optional): The data type of the output array. Defaults to None.
        compress (str, optional): The compression method. Can be one of the following: "deflate", "lzw", "packbits", "jpeg". Defaults to "deflate".
        transpose (bool, optional): Whether to transpose the array from (bands, rows, columns) to (rows, columns, bands). Defaults to True.
        cellsize (float, optional): The resolution of the output image in meters. Defaults to None.
        crs (str, optional): The CRS of the output image. Defaults to None.
        transform (tuple, optional): The affine transformation matrix, can be rio.transform() or a tuple like (0.5, 0.0, -180.25, 0.0, -0.5, 83.780361).
            Defaults to None.
        driver (str, optional): The driver to use for creating the output file, such as 'GTiff'. Defaults to "COG".
        colormap (dict, optional): A dictionary defining the colormap (value: (R, G, B, A)).
        **kwargs (Any): Additional keyword arguments to be passed to the rasterio.open() function.
    """

    import numpy as np
    import rasterio
    import rioxarray
    import xarray as xr
    from rasterio.transform import Affine

    if output is None:
        return array_to_memory_file(
            array,
            source,
            dtype,
            compress,
            transpose,
            cellsize,
            crs=crs,
            transform=transform,
            driver=driver,
            colormap=colormap,
            **kwargs,
        )

    if isinstance(array, xr.DataArray):
        if (
            hasattr(array, "rio")
            and (array.rio.crs is not None)
            and (array.rio.transform() is not None)
        ):

            if "latitude" in array.dims and "longitude" in array.dims:
                array = array.rename({"latitude": "y", "longitude": "x"})
            elif "lat" in array.dims and "lon" in array.dims:
                array = array.rename({"lat": "y", "lon": "x"})

            if array.ndim == 2 and ("x" in array.dims) and ("y" in array.dims):
                array = array.transpose("y", "x")
            elif array.ndim == 3 and ("x" in array.dims) and ("y" in array.dims):
                dims = list(array.dims)
                dims.remove("x")
                dims.remove("y")
                array = array.transpose(dims[0], "y", "x")
            if "long_name" in array.attrs:
                array.attrs.pop("long_name")

            array.rio.to_raster(
                output, driver=driver, compress=compress, dtype=dtype, **kwargs
            )
            if colormap:
                write_image_colormap(output, colormap, output)
            return output

    if array.ndim == 3 and transpose:
        array = np.transpose(array, (1, 2, 0))

    out_dir = os.path.dirname(os.path.abspath(output))
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    ext = os.path.splitext(output)[-1].lower()
    if ext == "":
        output += ".tif"
        driver = "COG"
    elif ext == ".png":
        driver = "PNG"
    elif ext == ".jpg" or ext == ".jpeg":
        driver = "JPEG"
    elif ext == ".jp2":
        driver = "JP2OpenJPEG"
    elif ext == ".tiff":
        driver = "GTiff"
    else:
        driver = "COG"

    if source is not None:
        with rasterio.open(source) as src:
            crs = src.crs
            transform = src.transform
            if compress is None:
                compress = src.compression
    else:
        if cellsize is None:
            raise ValueError("resolution must be provided if source is not provided")
        if crs is None:
            raise ValueError(
                "crs must be provided if source is not provided, such as EPSG:3857"
            )

        if transform is None:
            # Define the geotransformation parameters
            xmin, ymin, xmax, ymax = (
                0,
                0,
                cellsize * array.shape[1],
                cellsize * array.shape[0],
            )
            transform = rasterio.transform.from_bounds(
                xmin, ymin, xmax, ymax, array.shape[1], array.shape[0]
            )
        elif isinstance(transform, Affine):
            pass
        elif isinstance(transform, (tuple, list)):
            transform = Affine(*transform)

        kwargs["transform"] = transform

    if dtype is None:
        # Determine the minimum and maximum values in the array
        min_value = np.min(array)
        max_value = np.max(array)
        # Determine the best dtype for the array
        if min_value >= 0 and max_value <= 1:
            dtype = np.float32
        elif min_value >= 0 and max_value <= 255:
            dtype = np.uint8
        elif min_value >= -128 and max_value <= 127:
            dtype = np.int8
        elif min_value >= 0 and max_value <= 65535:
            dtype = np.uint16
        elif min_value >= -32768 and max_value <= 32767:
            dtype = np.int16
        else:
            dtype = np.float64

    # Convert the array to the best dtype
    array = array.astype(dtype)

    # Define the GeoTIFF metadata
    metadata = {
        "driver": driver,
        "height": array.shape[0],
        "width": array.shape[1],
        "dtype": array.dtype,
        "crs": crs,
        "transform": transform,
    }

    if array.ndim == 2:
        metadata["count"] = 1
    elif array.ndim == 3:
        metadata["count"] = array.shape[2]
    if compress is not None and (driver in ["GTiff", "COG"]):
        metadata["compress"] = compress

    metadata.update(**kwargs)
    # Create a new GeoTIFF file and write the array to it
    with rasterio.open(output, "w", **metadata) as dst:
        if array.ndim == 2:
            dst.write(array, 1)
            if colormap:
                dst.write_colormap(1, colormap)
        elif array.ndim == 3:
            for i in range(array.shape[2]):
                dst.write(array[:, :, i], i + 1)
                if colormap:
                    dst.write_colormap(i + 1, colormap)
    return output


def github_raw_url(url):
    """Get the raw URL for a GitHub file.

    Args:
        url (str): The GitHub URL.
    Returns:
        The raw URL.
    """
    if isinstance(url, str) and url.startswith("https://github.com/") and "blob" in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace(
            "blob/", ""
        )
    return url


def download_file(
    url=None,
    output=None,
    quiet=False,
    proxy=None,
    speed=None,
    use_cookies=True,
    verify=True,
    id=None,
    fuzzy=False,
    resume=False,
    unzip=True,
    overwrite=False,
    subfolder=False,
) -> str:
    """Download a file from URL, including Google Drive shared URL.

    Args:
        url (str, optional): Google Drive URL is also supported. Defaults to None.
        output (str, optional): Output filename. Default is basename of URL.
        quiet (bool, optional): Suppress terminal output. Default is False.
        proxy (str, optional): Proxy. Defaults to None.
        speed (float, optional): Download byte size per second (e.g., 256KB/s = 256 * 1024). Defaults to None.
        use_cookies (bool, optional): Flag to use cookies. Defaults to True.
        verify (bool | str, optional): Either a bool, in which case it controls whether the server's TLS certificate is verified, or a string,
            in which case it must be a path to a CA bundle to use. Default is True.. Defaults to True.
        id (str, optional): Google Drive's file ID. Defaults to None.
        fuzzy (bool, optional): Fuzzy extraction of Google Drive's file Id. Defaults to False.
        resume (bool, optional): Resume the download from existing tmp file if possible. Defaults to False.
        unzip (bool, optional): Unzip the file. Defaults to True.
        overwrite (bool, optional): Overwrite the file if it already exists. Defaults to False.
        subfolder (bool, optional): Create a subfolder with the same name as the file. Defaults to False.

    Returns:
        The output file path.
    """
    import tarfile
    import zipfile

    try:
        import gdown
    except ImportError:
        print(
            "The gdown package is required for this function. Use `pip install gdown` to install it."
        )
        return

    if output is None:
        if isinstance(url, str) and url.startswith("http"):
            output = os.path.basename(url)

    out_dir = os.path.abspath(os.path.dirname(output))
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if isinstance(url, str):
        if os.path.exists(os.path.abspath(output)) and (not overwrite):
            print(
                f"{output} already exists. Skip downloading. Set overwrite=True to overwrite."
            )
            return os.path.abspath(output)
        else:
            url = github_raw_url(url)

    if "https://drive.google.com/file/d/" in url:
        fuzzy = True

    output = gdown.download(
        url, output, quiet, proxy, speed, use_cookies, verify, id, fuzzy, resume
    )

    if unzip:
        if output.endswith(".zip"):
            with zipfile.ZipFile(output, "r") as zip_ref:
                if not quiet:
                    print("Extracting files...")
                if subfolder:
                    basename = os.path.splitext(os.path.basename(output))[0]

                    output = os.path.join(out_dir, basename)
                    if not os.path.exists(output):
                        os.makedirs(output)
                    zip_ref.extractall(output)
                else:
                    zip_ref.extractall(os.path.dirname(output))
        elif output.endswith(".tar.gz") or output.endswith(".tar"):
            if output.endswith(".tar.gz"):
                mode = "r:gz"
            else:
                mode = "r"

            with tarfile.open(output, mode) as tar_ref:
                if not quiet:
                    print("Extracting files...")
                if subfolder:
                    basename = os.path.splitext(os.path.basename(output))[0]
                    output = os.path.join(out_dir, basename)
                    if not os.path.exists(output):
                        os.makedirs(output)
                    tar_ref.extractall(output)
                else:
                    tar_ref.extractall(os.path.dirname(output))

    return os.path.abspath(output)
