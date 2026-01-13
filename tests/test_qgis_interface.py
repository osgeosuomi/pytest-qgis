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

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtWidgets import QToolBar

if TYPE_CHECKING:
    from qgis.gui import QgisInterface


RASTER_PATH = Path(Path(__file__).parent, "data", "small_raster.tif")


@pytest.fixture(autouse=True)
def _setup(qgis_new_project: None) -> None:
    pass


def test_add_vector_layer():
    layer = QgsVectorLayer("Polygon", "dummy_polygon_layer", "memory")
    assert QgsProject.instance().addMapLayer(layer)
    assert set(QgsProject.instance().mapLayers().values()) == {layer}


def test_add_vector_layer_via_iface(qgis_iface: "QgisInterface"):
    layer = qgis_iface.addVectorLayer("Polygon", "dummy_polygon_layer", "memory")
    assert layer.isValid()
    assert QgsProject.instance().addMapLayer(layer)
    assert set(QgsProject.instance().mapLayers().values()) == {layer}


def test_add_raster_layer_via_iface(qgis_iface: "QgisInterface"):
    layer = qgis_iface.addRasterLayer(
        str(RASTER_PATH),
        "Raster",
    )
    assert QgsProject.instance().addMapLayer(layer)
    assert set(QgsProject.instance().mapLayers().values()) == {layer}


def test_iface_active_layer(
    qgis_iface: "QgisInterface",
    layer_polygon: "QgsVectorLayer",
    layer_points: "QgsVectorLayer",
):
    QgsProject.instance().addMapLayer(layer_polygon)
    QgsProject.instance().addMapLayer(layer_points)

    assert qgis_iface.activeLayer() is None
    qgis_iface.setActiveLayer(layer_polygon)
    assert qgis_iface.activeLayer() == layer_polygon
    qgis_iface.setActiveLayer(layer_points)
    assert qgis_iface.activeLayer() == layer_points


def test_iface_toolbar_str(qgis_iface: "QgisInterface"):
    name = "test_bar"
    toolbar: QToolBar = qgis_iface.addToolBar(name)
    assert toolbar.windowTitle() == name
    assert qgis_iface._toolbars == {name: toolbar}


def test_iface_toolbar_qtoolbar(qgis_iface: "QgisInterface"):
    name = "test_bar"
    toolbar: QToolBar = QToolBar(name)
    qgis_iface.addToolBar(toolbar)
    assert toolbar.windowTitle() == name
    assert qgis_iface._toolbars == {name: toolbar}


def test_iface_mocks_missing_methods(qgis_iface: "QgisInterface"):
    mock_method = qgis_iface.pluginManagerInterface()
    assert isinstance(mock_method, MagicMock)
    qgis_iface.pluginManagerInterface.assert_called_once()

    qgis_iface.pluginManagerInterface()
    assert qgis_iface.pluginManagerInterface.call_count == 2


def test_new_project_clears_mocks(qgis_iface: "QgisInterface"):
    qgis_iface.pluginManagerInterface()
    qgis_iface.pluginManagerInterface()
    assert qgis_iface.pluginManagerInterface.call_count == 2

    qgis_iface.newProject()
    assert qgis_iface.pluginManagerInterface.call_count == 0
