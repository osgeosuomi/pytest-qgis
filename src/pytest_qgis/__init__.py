#  Copyright (C) 2021-2026 pytest-qgis Contributors.
#
#
#  This file is part of pytest-qgis.
#
#  pytest-qgis is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  pytest-qgis is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with pytest-qgis.  If not, see <https://www.gnu.org/licenses/>.


import warnings

from pytest_qgis._version import __version__  # noqa: F401

# Deprecated re-exports, kept importable from the package for now.
__all__ = [
    "SHOW_MAP_MARKER",
    "MockMessageBar",
    "QgisBot",
    "QgisInterface",
    "ensure_qgis_layer_fixtures_are_cleaned",
    "get_common_extent_from_all_layers",
    "get_layers_with_different_crs",
    "process_events",
    "replace_layers_with_reprojected_clones",
    "set_map_crs_based_on_layers",
]


def __getattr__(name: str) -> object:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from pytest_qgis import plugin  # noqa: PLC0415

    value = getattr(plugin, name)
    module = value.__module__ if callable(value) else plugin.__name__
    warnings.warn(
        f"Importing {name!r} from 'pytest_qgis' is deprecated and will be "
        f"removed in a future version. Import it from {module!r} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return value
