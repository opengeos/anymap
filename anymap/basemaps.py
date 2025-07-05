import collections
import xyzservices


def get_xyz_dict(free_only=True, france=False):
    """Returns a dictionary of xyz services.

    Args:
        free_only (bool, optional): Whether to return only free xyz tile
            services that do not require an access token. Defaults to True.
        france (bool, optional): Whether to include Geoportail France basemaps.
            Defaults to False.

    Returns:
        dict: A dictionary of xyz services.
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


available_basemaps = get_xyz_dict()
