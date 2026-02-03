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
#
import pytest
from qgis.core import QgsProject, QgsRectangle

from tests.utils import IN_CI

"""
These tests are meant to be tested visually by the developer.

NOTE: if you have pytest-qt installed, you might encounter some
problems with tests in this module.

In that case, run these tests with pytest-qt disabled: "pytest -p no:pytest-qt"
"""

DEFAULT_TIMEOUT = 0.01 if IN_CI else 1

QGIS_3_12 = 31200
QGIS_3_18 = 31800


@pytest.fixture(autouse=True)
def setup(qgis_new_project):
    pass


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT)
def test_show_map(layer_polygon, qgis_canvas, qgis_parent):
    QgsProject.instance().addMapLayers([layer_polygon])
    assert qgis_parent.size() == qgis_canvas.size()


@pytest.mark.qgis_show_map(timeout=0)
def test_show_map_with_zero_timeout(layer_polygon):
    QgsProject.instance().addMapLayers([layer_polygon])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT, extent=QgsRectangle(25, 65, 26, 66))
def test_show_map_custom_extent(layer_polygon):
    QgsProject.instance().addMapLayers([layer_polygon])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT, add_basemap=True)
def test_show_map_with_basemap(layer_polygon):
    QgsProject.instance().addMapLayers([layer_polygon])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT)
def test_show_map_crs_change_to_3067(
    layer_polygon, layer_polygon_3067, raster_3067, qgis_version
):
    layer_polygon_3067.setOpacity(0.3)
    if qgis_version > QGIS_3_18:
        raster_3067.setOpacity(0.9)
    QgsProject.instance().addMapLayers([layer_polygon, layer_polygon_3067, raster_3067])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT)
def test_show_map_crs_change_to_3067_with_different_layer_order(
    layer_polygon, layer_polygon_3067, raster_3067, qgis_version
):
    layer_polygon_3067.setOpacity(0.3)
    if qgis_version > QGIS_3_18:
        raster_3067.setOpacity(0.9)
    QgsProject.instance().addMapLayers([raster_3067, layer_polygon_3067, layer_polygon])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT, add_basemap=True)
def test_show_map_crs_change_to_3067_with_basemap(
    layer_polygon, layer_polygon_3067, raster_3067, qgis_version
):
    layer_polygon_3067.setOpacity(0.3)
    if qgis_version > QGIS_3_18:
        raster_3067.setOpacity(0.9)
    QgsProject.instance().addMapLayers([layer_polygon, layer_polygon_3067, raster_3067])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT)
def test_show_map_crs_change_to_4326(
    layer_polygon, raster_3067, layer_points, qgis_version
):
    if qgis_version > QGIS_3_18:
        raster_3067.setOpacity(0.9)
    QgsProject.instance().addMapLayers([layer_points, layer_polygon, raster_3067])


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT)
def test_show_map_crs_change_to_4326_2(layer_polygon, layer_points, layer_polygon_3067):
    QgsProject.instance().addMapLayers(
        [layer_points, layer_polygon_3067, layer_polygon]
    )


@pytest.mark.qgis_show_map(timeout=DEFAULT_TIMEOUT, zoom_to_common_extent=False)
def test_map_extent_should_not_change_to_layers_extent_when_processing_events(
    layer_polygon_3067, qgis_canvas, qgis_app
):
    extent_smaller_than_layer = QgsRectangle(475804, 7145949.5, 549226, 7219371.5)

    QgsProject.instance().addMapLayer(layer_polygon_3067)
    qgis_canvas.setExtent(extent_smaller_than_layer)

    # This triggers the map to set the extent based on the layer
    # if events are not processed after adding the layer
    qgis_app.processEvents()

    assert qgis_canvas.extent().height() == extent_smaller_than_layer.height()
