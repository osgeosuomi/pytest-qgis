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

from typing import TYPE_CHECKING

import pytest
from qgis.core import QgsProject, QgsVectorLayer

from pytest_qgis_test_utils.utils import EPSG_3067

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from qgis.gui import QgisInterface, QgsMapCanvas

    from pytest_qgis.qgis_bot import QgisBot

# Visible layers of the project file in the layer tree order
VISIBLE_LAYERS = ["db — points", "db — polygon_3067", "db — polygon"]
HIDDEN_LAYERS = ["small_raster", "OpenStreetMap"]


@pytest.fixture(autouse=True)
def _clean_project(qgis_new_project: QgsProject) -> "Iterator[None]":
    yield
    qgis_new_project.clear()


def _layer_names(layers: list) -> list[str]:
    return [layer.name() for layer in layers]


def test_open_project(
    qgis_bot: "QgisBot", qgis_canvas: "QgsMapCanvas", qgis_project_file: "Path"
):
    project = qgis_bot.open_project(qgis_project_file)

    assert project is QgsProject.instance()
    assert project.fileName() == str(qgis_project_file)
    layers = list(project.mapLayers().values())
    assert sorted(_layer_names(layers)) == sorted(VISIBLE_LAYERS + HIDDEN_LAYERS)
    assert all(layer.isValid() for layer in layers)

    assert _layer_names(qgis_canvas.layers()) == VISIBLE_LAYERS
    assert qgis_canvas.mapSettings().destinationCrs().authid() == EPSG_3067
    # Extent stored in the project, width is adjusted to the canvas aspect ratio
    assert qgis_canvas.extent().yMinimum() == pytest.approx(6955657.86, abs=1)
    assert qgis_canvas.extent().yMaximum() == pytest.approx(7149021.30, abs=1)


def test_open_project_clears_previous_project(
    qgis_bot: "QgisBot", qgis_canvas: "QgsMapCanvas", qgis_project_file: "Path"
):
    layer = QgsVectorLayer("Point", "previous", "memory")
    assert QgsProject.instance().addMapLayer(layer)

    qgis_bot.open_project(qgis_project_file)

    assert "previous" not in _layer_names(QgsProject.instance().mapLayers().values())
    assert _layer_names(qgis_canvas.layers()) == VISIBLE_LAYERS


def test_open_project_raises_if_file_is_missing(qgis_bot: "QgisBot", tmp_path: "Path"):
    with pytest.raises(AssertionError, match="Failed to open project"):
        qgis_bot.open_project(tmp_path / "missing.qgs")


def test_layers_added_after_opening_project_are_shown(
    qgis_bot: "QgisBot", qgis_canvas: "QgsMapCanvas", qgis_project_file: "Path"
):
    qgis_bot.open_project(qgis_project_file)
    layer = QgsVectorLayer("Point", "new", "memory")
    assert QgsProject.instance().addMapLayer(layer)

    assert _layer_names(qgis_canvas.layers()) == [*VISIBLE_LAYERS, "new"]


def test_iface_add_project(
    qgis_iface: "QgisInterface", qgis_canvas: "QgsMapCanvas", qgis_project_file: "Path"
):
    assert qgis_iface.addProject(str(qgis_project_file))

    assert _layer_names(qgis_canvas.layers()) == VISIBLE_LAYERS
