"""QGIS plugin implementation.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

.. note:: This source code was copied from the 'postgis viewer' application
     with original authors:
     Copyright (c) 2010 by Ivan Mincik, ivan.mincik@gista.sk
     Copyright (c) 2011 German Carrillo, geotux_tuxman@linuxmail.org
     Copyright (c) 2014 Tim Sutton, tim@linfiniti.com
     Copyright (c) 2021 pytest-qgis Contributors

"""

__author__ = "tim@linfiniti.com"
__revision__ = "$Format:%H$"
__date__ = "10/01/2011"
__copyright__ = (
    "Copyright (c) 2010 by Ivan Mincik, ivan.mincik@gista.sk and "
    "Copyright (c) 2011 German Carrillo, geotux_tuxman@linuxmail.org"
    "Copyright (c) 2014 Tim Sutton, tim@linfiniti.com"
    "Copyright (c) 2021-2026 pytest-qgis Contributors"
)

import logging
import typing
from unittest.mock import MagicMock

from qgis.core import (
    QgsLayerTree,
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsRelationManager,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot
from qgis.PyQt.QtWidgets import (
    QAction,
    QDockWidget,
    QMainWindow,
    QMenuBar,
    QToolBar,
    QWidget,
)

from pytest_qgis.mock_qgis_classes import MockMessageBar

LOGGER = logging.getLogger("QGIS")


# noinspection PyMethodMayBeStatic,PyPep8Naming
class QgisInterface(QObject):
    """Class to expose QGIS objects and functions to plugins.

    This class is here for enabling us to run unit tests only,
    so most methods are simply stubs.
    """

    currentLayerChanged = pyqtSignal(QgsMapCanvas)  # noqa: N815
    newProjectCreated = pyqtSignal()  # noqa: N815

    def __init__(
        self, canvas: QgsMapCanvas, messageBar: MockMessageBar, mainWindow: QMainWindow
    ) -> None:
        """Constructor
        :param canvas:
        """
        QObject.__init__(self)
        self.canvas = canvas
        self._messageBar = messageBar
        self._mainWindow = mainWindow
        self._active_layer_id: str | None = None

        # Set up slots so we can mimic the behaviour of QGIS when layers
        # are added.
        LOGGER.debug("Initialising canvas...")
        # noinspection PyArgumentList
        QgsProject.instance().layersAdded.connect(self.addLayers)
        # noinspection PyArgumentList
        QgsProject.instance().removeAll.connect(self.removeAllLayers)

        # For processing module
        self.destCrs = None
        self._layers: list[QgsMapLayer] = []

        # Add the MenuBar
        menu_bar = QMenuBar()
        self._mainWindow.setMenuBar(menu_bar)

        # Add the toolbar list
        self._toolbars: dict[str, QToolBar] = {}

        # Store mocks for missing methods to ensure consistency
        self._mock_methods: dict[str, MagicMock] = {}

    def __getattr__(self, name: str) -> MagicMock:
        """
        Return a MagicMock for any method not explicitly implemented.
        """
        if name not in self._mock_methods:
            self._mock_methods[name] = MagicMock(name=name)
        return self._mock_methods[name]

    @pyqtSlot("QList<QgsMapLayer*>")
    def addLayers(self, layers: list[QgsMapLayer]) -> None:
        """Handle layers being added to the registry so they show up in canvas.

        :param layers: list<QgsMapLayer> list of map layers that were added

        .. note:: The QgsInterface api does not include this method,
            it is added here as a helper to facilitate testing.
        """
        # LOGGER.debug('addLayers called on qgis_interface')
        # LOGGER.debug('Number of layers being added: %s' % len(layers))
        # LOGGER.debug('Layer Count Before: %s' % len(self.canvas.layers()))
        current_layers = self.canvas.layers()
        final_layers = []
        for layer in current_layers:
            final_layers.append(layer)
        for layer in layers:
            final_layers.append(layer)
        self._layers = final_layers

        self.canvas.setLayers(final_layers)
        # LOGGER.debug('Layer Count After: %s' % len(self.canvas.layers()))

    @pyqtSlot()
    def removeAllLayers(self) -> None:
        """Remove layers from the canvas before they get deleted."""
        if not sip.isdeleted(self.canvas):
            self.canvas.setLayers([])
        self._layers = []

    def newProject(self, promptToSaveFlag: bool = False) -> bool:  # noqa: ARG002
        """Create new project."""
        # noinspection PyArgumentList
        instance = QgsProject.instance()
        instance.removeAllMapLayers()
        root: QgsLayerTree = instance.layerTreeRoot()
        root.removeAllChildren()
        relation_manager: QgsRelationManager = instance.relationManager()
        for relation in relation_manager.relations():
            relation_manager.removeRelation(relation)
        self._layers.clear()
        self._mock_methods.clear()
        self._messageBar.clear_messages()
        self.newProjectCreated.emit()
        return True

    # ---------------- API Mock for QgsInterface follows -------------------

    def zoomFull(self) -> None:
        """Zoom to the map full extent."""

    def zoomToPrevious(self) -> None:
        """Zoom to previous view extent."""

    def zoomToNext(self) -> None:
        """Zoom to next view extent."""

    def zoomToActiveLayer(self) -> None:
        """Zoom to extent of active layer."""

    def addVectorLayer(
        self, path: str, base_name: str, provider_key: str
    ) -> QgsVectorLayer:
        """Add a vector layer.

        :param path: Path to layer.
        :type path: str

        :param base_name: Base name for layer.
        :type base_name: str

        :param provider_key: Provider key e.g. 'ogr'
        :type provider_key: str
        """
        layer = QgsVectorLayer(path, base_name, provider_key)
        self.addLayers([layer])
        return layer

    @typing.overload
    def addRasterLayer(
        self, rasterLayerPath: str | None, baseName: str | None = None
    ) -> QgsRasterLayer | None:
        pass

    @typing.overload
    def addRasterLayer(
        self, url: str | None, layerName: str | None, providerKey: str | None
    ) -> QgsRasterLayer | None:
        pass

    def addRasterLayer(
        self, *args: str, **kwargs: dict[str, str]
    ) -> QgsRasterLayer | None:
        layer = QgsRasterLayer(*args, **kwargs)
        self.addLayers([layer])
        return layer

    def activeLayer(self) -> QgsMapLayer | None:
        """Get pointer to the active layer (layer selected in the legend)."""
        return (
            QgsProject.instance().mapLayer(self._active_layer_id)
            if self._active_layer_id
            else None
        )

    def addPluginToMenu(self, name: str, action: QAction) -> None:
        """Add plugin item to menu.

        :param name: Name of the menu item
        :type name: str

        :param action: Action to add to menu.
        :type action: QAction
        """

    def addToolBarIcon(self, action: QAction) -> None:
        """Add an icon to the plugins toolbar.

        :param action: Action to add to the toolbar.
        :type action: QAction
        """

    def removeToolBarIcon(self, action: QAction) -> None:
        """Remove an action (icon) from the plugin toolbar.

        :param action: Action to add to the toolbar.
        :type action: QAction
        """

    def addToolBar(self, toolbar: str | QToolBar) -> QToolBar:
        """Add toolbar with specified name.

        :param toolbar: Name for the toolbar or QToolBar object.
        """
        if isinstance(toolbar, str):
            name = toolbar
            _toolbar = QToolBar(name, parent=self._mainWindow)
        else:
            name = toolbar.windowTitle()
            _toolbar = toolbar
        self._toolbars[name] = _toolbar
        return _toolbar

    def mapCanvas(self) -> QgsMapCanvas:
        """Return a pointer to the map canvas."""
        return self.canvas

    def mainWindow(self) -> QWidget:
        """Return a pointer to the main window.

        In case of QGIS it returns an instance of QgisApp.
        """
        return self._mainWindow

    def addDockWidget(self, area: int, dock_widget: QDockWidget) -> None:
        """Add a dock widget to the main window.

        :param area: Where in the ui the dock should be placed.
        :type area: Qt.DockWidgetArea

        :param dock_widget: A dock widget to add to the UI.
        :type dock_widget: QDockWidget
        """

    def legendInterface(self) -> QgsMapCanvas:
        """Get the legend."""
        return self.canvas

    def messageBar(self) -> MockMessageBar:
        """Get the messagebar"""
        return self._messageBar

    def getMockLayers(self) -> list[QgsMapLayer]:
        return self._layers

    def setActiveLayer(self, layer: QgsMapLayer) -> None:
        """
        Set the active layer (layer gets selected in the legend)
        """
        self._active_layer_id = layer.id()
