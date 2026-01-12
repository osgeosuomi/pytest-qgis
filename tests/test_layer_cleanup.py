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
from unittest.mock import MagicMock

import pytest
from qgis.core import QgsMapLayer, QgsProject, QgsVectorLayer

"""
Tests in this module will cause Segmentation fault error if
non-memory layer is not cleaned properly.

Tests are not parametrized since the problem cannot be observed with
parametrized tests.
"""


@pytest.fixture
def stub_layer() -> MagicMock:
    return MagicMock(
        spec=QgsVectorLayer,
        autospec=True,
    )


def test_layer_fixture_should_be_cleaned(layer_polygon_function):
    _test(layer_polygon_function)


def test_layer_fixture_should_be_cleaned_module(lyr_polygon_module):
    _test(lyr_polygon_module)


def test_layer_fixture_should_be_cleaned_2(layer_polygon_function):
    _test(layer_polygon_function)


def test_layer_fixture_should_be_cleaned_session(layer_polygon_session):
    _test(layer_polygon_session)


def test_layer_fixture_should_be_cleaned_module_2(lyr_polygon_module):
    _test(lyr_polygon_module)


def test_layer_fixture_should_be_cleaned_session_2(layer_polygon_session):
    _test(layer_polygon_session)


def test_raster_layer_fixture_should_be_cleaned(raster_3067):
    _test(raster_3067)


def _test(layer: QgsMapLayer) -> None:
    # Check that the layer is not in the project
    assert not QgsProject.instance().mapLayer(layer.id())


def test_mocked_layer_should_not_mess_with_cleaning_layers(stub_layer):
    assert isinstance(stub_layer, QgsVectorLayer)
