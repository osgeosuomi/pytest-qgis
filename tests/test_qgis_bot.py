#  Copyright (C) 2021-2022 pytest-qgis Contributors.
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
from typing import TYPE_CHECKING

import pytest
from qgis.core import QgsFieldConstraints, QgsGeometry
from qgis.gui import QgsAttributeDialog

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer
    from qgis.gui import QgisInterface

    from pytest_qgis.qgis_bot import QgisBot


@pytest.fixture
def layer_with_soft_constraint(layer_points: "QgsVectorLayer") -> "QgsVectorLayer":
    """setup the layer"""
    # Set not-null constraint with SOFT strength
    fields = layer_points.fields()
    field_idx = fields.indexOf("text_field")
    layer_points.setFieldConstraint(
        field_idx,
        QgsFieldConstraints.Constraint.ConstraintNotNull,
        QgsFieldConstraints.ConstraintStrengthSoft,
    )

    layer_points.startEditing()

    return layer_points


@pytest.fixture
def layer_with_hard_constraint(layer_points: "QgsVectorLayer") -> "QgsVectorLayer":
    """setup the layer"""
    # Set not-null constraint with SOFT strength
    fields = layer_points.fields()
    field_idx = fields.indexOf("text_field")
    layer_points.setFieldConstraint(
        field_idx,
        QgsFieldConstraints.Constraint.ConstraintNotNull,
        QgsFieldConstraints.ConstraintStrengthHard,
    )

    layer_points.startEditing()

    return layer_points


def test_feature_gets_created_with_check_box_false_when_not_raising_from_warnings(
    layer_with_soft_constraint: "QgsVectorLayer", qgis_bot: "QgisBot"
):
    feature_count_before = layer_with_soft_constraint.featureCount()
    feature = qgis_bot.create_feature_with_attribute_dialog(
        layer_with_soft_constraint,
        QgsGeometry.fromWkt("POINT(0,0)"),
        raise_from_warnings=False,
    )

    assert layer_with_soft_constraint.featureCount() == feature_count_before + 1

    # With normal way of creating, it would be NULL.
    assert feature["bool_field"] is False


def test_should_raise_valueerror_on_soft_constraint_break_when_asked(
    layer_with_soft_constraint: "QgsVectorLayer", qgis_bot: "QgisBot"
):
    with pytest.raises(ValueError, match="value is NULL"):
        qgis_bot.create_feature_with_attribute_dialog(
            layer_with_soft_constraint,
            QgsGeometry.fromWkt("POINT(0,0)"),
            raise_from_warnings=True,
        )


def test_feature_gets_created_with_check_box_false_when_not_raising_from_errors(
    layer_with_hard_constraint: "QgsVectorLayer", qgis_bot: "QgisBot"
):
    feature_count_before = layer_with_hard_constraint.featureCount()
    feature = qgis_bot.create_feature_with_attribute_dialog(
        layer_with_hard_constraint,
        QgsGeometry.fromWkt("POINT(0,0)"),
        raise_from_errors=False,
    )

    assert layer_with_hard_constraint.featureCount() == feature_count_before + 1

    # With normal way of creating, it would be NULL.
    assert feature["bool_field"] is False


def test_should_raise_valueerror_on_hard_constraint_break_when_asked(
    layer_with_hard_constraint: "QgsVectorLayer", qgis_bot: "QgisBot"
):
    with pytest.raises(ValueError, match="value is NULL"):
        qgis_bot.create_feature_with_attribute_dialog(
            layer_with_hard_constraint,
            QgsGeometry.fromWkt("POINT(0,0)"),
            raise_from_errors=True,
        )


def test_create_simple_feature_with_attribute_dialog(
    layer_points: "QgsVectorLayer", qgis_bot: "QgisBot"
):
    layer = layer_points
    count = layer.featureCount()

    layer.startEditing()
    feat = qgis_bot.create_feature_with_attribute_dialog(
        layer, QgsGeometry.fromWkt("POINT(0,0)")
    )
    assert layer.featureCount() == count + 1
    assert feat["bool_field"] is False


def test_get_qgs_attribute_dialog_widgets_by_name(
    qgis_iface: "QgisInterface", layer_points: "QgsVectorLayer", qgis_bot: "QgisBot"
):
    dialog = QgsAttributeDialog(
        layer_points,
        layer_points.getFeature(1),
        False,
        qgis_iface.mainWindow(),
        True,
    )
    widgets_by_name = qgis_bot.get_qgs_attribute_dialog_widgets_by_name(dialog)
    assert {
        name: widget.__class__.__name__ for name, widget in widgets_by_name.items()
    } == {
        "bool_field": "QCheckBox",
        "date_field": "QDateTimeEdit",
        "datetime_field": "QDateTimeEdit",
        "decimal_field": "QgsFilterLineEdit",
        "fid": "QgsFilterLineEdit",
        "text_field": "QgsFilterLineEdit",
    }
