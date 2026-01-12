#  Copyright (C) 2021-2023 pytest-qgis Contributors.
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

import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer
from qgis.PyQt import sip

from pytest_qgis.utils import (
    clean_qgis_layer,
    get_common_extent_from_all_layers,
    get_layers_with_different_crs,
    replace_layers_with_reprojected_clones,
    set_map_crs_based_on_layers,
)
from tests.utils import EPSG_3067, EPSG_4326, QGIS_VERSION

QGIS_3_12 = 31200


@pytest.fixture
def crs():
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(EPSG_4326))


@pytest.fixture
def layers_added(qgis_new_project, layer_polygon, layer_polygon_3067, raster_3067):
    QgsProject.instance().addMapLayers([raster_3067, layer_polygon_3067, layer_polygon])


@pytest.mark.skipif(
    QGIS_VERSION < QGIS_3_12,
    reason="QGIS 3.10 test image cannot find correct algorithms",
)
def test_get_common_extent_from_all_layers(
    qgis_new_project, crs, layer_polygon, layer_polygon_3067
):
    QgsProject.instance().addMapLayers([layer_polygon, layer_polygon_3067])
    assert get_common_extent_from_all_layers().toString(0) == "23,61 : 32,68"


@pytest.mark.skipif(
    QGIS_VERSION < QGIS_3_12,
    reason="QGIS 3.10 test image cannot find correct algorithms",
)
def test_set_map_crs_based_on_layers_should_set_4326(qgis_new_project, layer_polygon):
    layer_polygon2 = layer_polygon.clone()
    QgsProject.instance().addMapLayers([layer_polygon, layer_polygon2])
    set_map_crs_based_on_layers()
    assert QgsProject.instance().crs().authid() == EPSG_4326


def test_set_map_crs_based_on_layers_should_set_3067(layers_added):
    set_map_crs_based_on_layers()
    assert QgsProject.instance().crs().authid() == EPSG_3067


def test_get_layers_with_different_crs(
    crs, layers_added, layer_polygon_3067, raster_3067
):
    assert set(get_layers_with_different_crs()) == {layer_polygon_3067, raster_3067}


@pytest.mark.skipif(
    QGIS_VERSION < QGIS_3_12,
    reason="QGIS 3.10 test image cannot find correct algorithms",
)
def test_replace_layers_with_reprojected_clones(  # noqa: PLR0913
    crs, layers_added, qgis_processing, layer_polygon_3067, raster_3067, tmp_path
):
    vector_layer_id = layer_polygon_3067.id()
    raster_layer_id = raster_3067.id()
    vector_layer_name = layer_polygon_3067.name()
    raster_layer_name = raster_3067.name()

    replace_layers_with_reprojected_clones([layer_polygon_3067, raster_3067], tmp_path)

    layers = {
        layer.name(): layer for layer in QgsProject.instance().mapLayers().values()
    }

    assert {vector_layer_name, raster_layer_name}.issubset(set(layers.keys()))
    assert layers[vector_layer_name].id() != vector_layer_id
    assert layers[raster_layer_name].id() != raster_layer_id
    assert layers[vector_layer_name].crs().authid() == EPSG_4326
    assert layers[raster_layer_name].crs().authid() == EPSG_4326
    assert (tmp_path / f"{vector_layer_id}.qml").exists()
    assert (tmp_path / f"{raster_layer_id}.qml").exists()


def test_clean_qgis_layer(layer_polygon):
    layer = QgsVectorLayer(layer_polygon.source(), "another layer")

    @clean_qgis_layer
    def layer_function() -> QgsVectorLayer:
        return layer

    # Using list to trigger yield and the code that runs after it
    list(layer_function())

    assert sip.isdeleted(layer)
