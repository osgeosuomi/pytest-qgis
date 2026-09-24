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
from typing import Any

from qgis.core import (
    QgsFeature,
    QgsFieldConstraints,
    QgsGeometry,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsVectorLayerUtils,
)
from qgis.gui import QgisInterface, QgsAttributeDialog, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QLabel, QWidget

from pytest_qgis import utils


class QgisBot:
    """Class to hold common utility methods for interacting with QIGS."""

    def __init__(  # noqa: QGS105 # Iface has to be passed in order to
        # ensure compatibility with all QGIS versions >= 3.10
        self,
        iface: QgisInterface,
    ) -> None:
        self._iface = iface

    def create_feature_with_attribute_dialog(  # noqa: PLR0913, PLR0917
        self,
        layer: QgsVectorLayer,
        geometry: QgsGeometry,
        attributes: dict[str, Any] | None = None,
        raise_from_warnings: bool = False,  # noqa: FBT001, FBT002
        raise_from_errors: bool = True,  # noqa: FBT001, FBT002
        show_dialog_timeout_milliseconds: int = 0,
    ) -> QgsFeature:
        """Create test feature with default values using QgsAttributeDialog.

        This ensures that all the default values are honored and
        for example boolean fields are either true or false, not null.

        :param layer: QgsVectorLayer to create feature into
        :param geometry: QgsGeometry of the feature
        :param attributes: attributes as a dictionary
        :param raise_from_warnings: Whether to raise error if there are non-enforcing
            constraint warnings with attribute values.
        :param raise_from_errors: Whether to raise error if there are enforcing
            constraint errors with attribute values.
        :param show_dialog_timeout_milliseconds: Shows attribute dialog. Useful for
            debugging.
        :return: Created QgsFeature that can be added to the layer.
        """
        initial_ids = set(layer.allFeatureIds())

        capabilities = layer.dataProvider().capabilities()

        if not capabilities & QgsVectorDataProvider.Capability.AddFeatures:
            msg = f"Could not create feature for the layer {layer.name()}"
            raise ValueError(msg)

        new_feature = QgsVectorLayerUtils.createFeature(
            layer, context=layer.createExpressionContext()
        )
        new_feature.setGeometry(geometry)

        if attributes is not None:
            if capabilities & QgsVectorDataProvider.Capability.ChangeAttributeValues:
                for field_name, value in attributes.items():
                    new_feature[field_name] = value
            else:
                msg = f"Could not change attributes for layer {layer.name()}"
                raise ValueError(msg)

        assert new_feature.isValid()  # noqa: S101

        warnings = {}
        errors = {}
        for field_index, field in enumerate(layer.fields()):
            no_warnings, warning_messages = QgsVectorLayerUtils.validateAttribute(
                layer,
                new_feature,
                field_index,
                QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft,
            )
            no_errors, error_messages = QgsVectorLayerUtils.validateAttribute(
                layer,
                new_feature,
                field_index,
                QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard,
            )
            if not no_warnings:
                warnings[field.name()] = warning_messages
            if not no_errors:
                errors[field.name()] = error_messages

        if raise_from_warnings and warnings:
            msg = (
                "There are non-enforcing constraint warnings in the attribute form: "
                f"{warnings!s}"
            )
            raise ValueError(msg)
        if raise_from_errors and errors:
            msg = (
                "There are enforcing constraint errors in the attribute form: "
                f"{errors!s}"
            )
            raise ValueError(msg)

        context = QgsAttributeEditorContext()
        context.setMapCanvas(self._iface.mapCanvas())

        dialog = QgsAttributeDialog(
            layer,
            new_feature,
            False,  # noqa: FBT003
            self._iface.mainWindow(),
            True,  # noqa: FBT003
            context,
        )
        dialog.show()
        dialog.setMode(QgsAttributeEditorContext.Mode.AddFeatureMode)

        # Process events to ensure all the signals are processed
        utils.wait(show_dialog_timeout_milliseconds)

        # Two accepts to ignore warnings and errors
        dialog.accept()
        dialog.accept()

        feature_ids = set(layer.allFeatureIds())
        feature_id = list(feature_ids.difference(initial_ids))

        assert feature_id, "Creating new feature failed"  # noqa: S101
        return layer.getFeature(feature_id[0])

    @staticmethod
    def get_qgs_attribute_dialog_widgets_by_name(
        widget: QgsAttributeDialog | QWidget,
    ) -> dict[str, QWidget]:
        """Get recursively all attribute dialog widgets by name.

        :param widget: QgsAttributeDialog for the first time, afterwards QWidget.
        :return: Dictionary with field names as keys and corresponding
        QWidgets as values.
        """
        widgets_by_name = {}
        for child in widget.children():
            if (
                isinstance(child, QLabel)
                and child.text() != ""
                and child.buddy() is not None
            ):
                widgets_by_name[child.text()] = child.buddy()
            if hasattr(child, "children"):
                widgets_by_name = {
                    **widgets_by_name,
                    **QgisBot.get_qgs_attribute_dialog_widgets_by_name(child),
                }

        return widgets_by_name
