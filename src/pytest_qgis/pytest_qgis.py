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

import contextlib
import logging
import os.path
import shutil
import sys
import time
import warnings
from collections import namedtuple
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProject,
    QgsRectangle,
    QgsSettings,
    QgsVectorLayer,
)
from qgis.gui import QgisInterface as QgisInterfaceOrig
from qgis.gui import QgsGui, QgsLayerTreeMapCanvasBridge, QgsMapCanvas
from qgis.PyQt import QtCore, QtWidgets, sip
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt
from qgis.PyQt.QtWidgets import QMainWindow, QMessageBox, QWidget

from pytest_qgis.mock_qgis_classes import MockMessageBar
from pytest_qgis.qgis_bot import QgisBot
from pytest_qgis.qgis_interface import QgisInterface
from pytest_qgis.utils import (
    MessageLogCapture,
    ensure_qgis_layer_fixtures_are_cleaned,
    get_common_extent_from_all_layers,
    get_layers_with_different_crs,
    replace_layers_with_reprojected_clones,
    set_map_crs_based_on_layers,
)

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.fixtures import SubRequest
    from _pytest.mark import Mark

QGIS_V4_INT = 40000

LOGGER = logging.getLogger("QGIS")

Settings = namedtuple(
    "Settings",
    [
        "gui_enabled",
        "qgis_init_disabled",
        "qgis_exit_disabled",
        "qgis_server",
        "canvas_width",
        "canvas_height",
    ],
)
ShowMapSettings = namedtuple(
    "ShowMapSettings", ["timeout", "add_basemap", "zoom_to_common_extent", "extent"]
)

GUI_DISABLE_KEY = "qgis_disable_gui"
GUI_ENABLED_KEY = "qgis_gui_enabled"
GUI_DESCRIPTION = "Set whether the graphical user interface is wanted or not."
GUI_ENABLED_DEFAULT = True

EXIT_DISABLED_KEY = "qgis_disable_exit"
EXIT_DISABLED_DEFAULT = False
EXIT_DISABLED_DESCRIPTION = "Set wether exitQgis() is called at the end of the session"

SERVER_KEY = "qgis_server"
SERVER_DEFAULT = False

CANVAS_HEIGHT_KEY = "qgis_canvas_height"
CANVAS_WIDTH_KEY = "qgis_canvas_width"
CANVAS_DESCRIPTION = "Set canvas height and width."
CANVAS_SIZE_DEFAULT = (600, 600)

DISABLE_QGIS_INIT_KEY = "qgis_disable_init"
DISABLE_QGIS_INIT_DESCRIPTION = "Prevent QGIS (QgsApplication) from initializing."

SHOW_MAP_MARKER = "qgis_show_map"
SHOW_MAP_VISIBILITY_TIMEOUT_DEFAULT = 30
SHOW_MAP_MARKER_DESCRIPTION = (
    f"{SHOW_MAP_MARKER}(timeout={SHOW_MAP_VISIBILITY_TIMEOUT_DEFAULT}, add_basemap=False, zoom_to_common_extent=True, extent=None): "  # noqa: E501
    f"Show QGIS map for a short amount of time. The first keyword, *timeout*, is the "
    f"timeout in seconds until the map closes. The second keyword *add_basemap*, "
    f"when set to True, adds Natural Earth countries layer as the basemap for the map. "
    f"The third keyword *zoom_to_common_extent*, when set to True, centers the map "
    f"around all layers in the project. Alternatively the fourth keyword *extent* "
    f"can be provided as QgsRectangle."
)

_APP: QgsApplication | None = None
_CANVAS: QgsMapCanvas | None = None
_IFACE: QgisInterface | None = None
_PARENT: QtWidgets.QWidget | None = None
_AUTOUSE_QGIS: bool | None = None

_QGIS_SERVER: bool = False

try:
    _QGIS_VERSION = Qgis.versionInt()
except AttributeError:
    _QGIS_VERSION = Qgis.QGIS_VERSION_INT


@pytest.hookimpl()
def pytest_addoption(parser: "Parser") -> None:
    group = parser.getgroup(
        "qgis",
        "Utilities for testing QGIS plugins",
    )
    group.addoption(f"--{GUI_DISABLE_KEY}", action="store_true", help=GUI_DESCRIPTION)
    group.addoption(
        f"--{DISABLE_QGIS_INIT_KEY}",
        action="store_true",
        help=DISABLE_QGIS_INIT_DESCRIPTION,
    )
    group.addoption(
        f"--{EXIT_DISABLED_KEY}",
        action="store_true",
        help=EXIT_DISABLED_DESCRIPTION,
    )

    parser.addini(
        GUI_ENABLED_KEY, GUI_DESCRIPTION, type="bool", default=GUI_ENABLED_DEFAULT
    )
    parser.addini(
        EXIT_DISABLED_KEY,
        EXIT_DISABLED_DESCRIPTION,
        type="bool",
        default=EXIT_DISABLED_DEFAULT,
    )
    parser.addini(
        SERVER_KEY,
        "QGIS Server session",
        type="bool",
        default=SERVER_DEFAULT,
    )

    parser.addini(
        CANVAS_WIDTH_KEY,
        CANVAS_DESCRIPTION,
        type="string",
        default=CANVAS_SIZE_DEFAULT[0],
    )
    parser.addini(
        CANVAS_HEIGHT_KEY,
        CANVAS_DESCRIPTION,
        type="string",
        default=CANVAS_SIZE_DEFAULT[1],
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: "Config") -> None:
    """Configure and initialize qgis session for all tests."""
    config.addinivalue_line("markers", SHOW_MAP_MARKER_DESCRIPTION)

    settings = _parse_settings(config)
    config._plugin_settings = settings

    if not settings.gui_enabled:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    _start_and_configure_qgis_app(config)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:  # noqa: ARG001
    request = item.funcargs.get("request")
    if request:
        ensure_qgis_layer_fixtures_are_cleaned(request)


@pytest.fixture(autouse=True, scope="session")
def qgis_app(request: "SubRequest") -> QgsApplication:
    yield _APP if not request.config._plugin_settings.qgis_init_disabled else None

    if not request.config._plugin_settings.qgis_init_disabled:
        assert _APP

        if not request.config._plugin_settings.qgis_server:
            # TODO: investigate why legendLayersAdded is sometimes not connected
            with contextlib.suppress(TypeError):
                QgsProject.instance().legendLayersAdded.disconnect(_APP.processEvents)
            if not sip.isdeleted(_CANVAS) and _CANVAS is not None:
                _CANVAS.deleteLater()

        if not request.config._plugin_settings.qgis_exit_disabled:
            LOGGER.debug("EXITING QGIS")
            _APP.exitQgis()


@pytest.fixture(scope="session")
def qgis_parent(qgis_app: QgsApplication) -> QWidget:  # noqa: ARG001
    return _PARENT


@pytest.fixture(scope="session")
def qgis_canvas() -> QgsMapCanvas:
    assert _CANVAS
    return _CANVAS


@pytest.fixture(scope="session")
def qgis_version() -> int:
    """QGIS version number as integer."""
    return _QGIS_VERSION


@pytest.fixture(scope="session")
def qgis_iface() -> QgisInterfaceOrig:
    # This is needed because qgis_iface
    # is required in autouse=True fixture qgis_show_map
    if not _QGIS_SERVER:
        assert _IFACE
    return _IFACE


@pytest.fixture(scope="session")
def qgis_processing(qgis_app: QgsApplication) -> None:
    """
    Initializes QGIS processing framework
    """
    _initialize_processing(qgis_app)


@pytest.fixture
def qgis_new_project(qgis_iface: QgisInterface, request: "SubRequest") -> QgsProject:
    """
    Initializes new QGIS project by removing layers and relations etc.

    :return: QgsProject instance
    """
    qgis_iface.newProject()  # noqa: QGS201

    # Clear the project properly if qgis_show_map marker is not used
    show_map_marker = request.node.get_closest_marker(SHOW_MAP_MARKER)
    if not show_map_marker:
        QgsProject.instance().clear()
    return QgsProject.instance()


@pytest.fixture
def qgis_world_map_geopackage(tmp_path: Path) -> Path:
    """
    Path to natural world map geopackage containing Natural Earth data.
    This geopackage can be modified in any way.

    Layers:
    * countries
    * disputed_borders
    * states_provinces
    """
    return _get_world_map_geopackage(tmp_path)


@pytest.fixture
def qgis_countries_layer(qgis_world_map_geopackage: Path) -> QgsVectorLayer:
    """
    Natural Earth countries as a QgsVectorLayer.
    """
    return _get_countries_layer(qgis_world_map_geopackage)


@pytest.fixture(scope="session")
def qgis_bot(qgis_iface: QgisInterface) -> QgisBot:
    """
    Object that holds common utility methods for interacting with QGIS.
    """
    return QgisBot(qgis_iface)


@pytest.fixture
def qgis_message_log(
    qgis_app: QgsApplication,  # noqa: ARG001
) -> Generator[MessageLogCapture, None, None]:
    """
    Capture ``QgsMessageLog.logMessage`` emissions for the duration of
    a test.

    Yields a :class:`MessageLogCapture` whose ``.entries`` list holds
    every captured ``(message, tag, level)``.  Helpers ``.warnings`` /
    ``.errors`` / ``.infos`` filter by level; ``.find(text, level=...)``
    returns the first entry whose message contains ``text``.

    Example::

        def test_plugin_warns_on_empty_data(qgis_message_log):
            my_plugin.process_empty()
            assert qgis_message_log.find('No data', level=Qgis.Warning)
    """
    capture = MessageLogCapture()
    capture.connect()
    try:
        yield capture
    finally:
        capture.disconnect()


@pytest.fixture(autouse=True)
def qgis_show_map(
    qgis_app: QgsApplication,
    qgis_iface: QgisInterface | None,
    qgis_parent: QWidget | None,
    tmp_path: Path,
    request: "SubRequest",
) -> None:
    """
    Shows QGIS map if qgis_show_map marker is used.
    """
    # Noop if server session
    if _QGIS_SERVER:
        yield
        return

    assert qgis_iface is not None

    show_map_marker = request.node.get_closest_marker(SHOW_MAP_MARKER)
    common_settings: Settings = request.config._plugin_settings

    if show_map_marker:
        # Assign the bridge to have correct layer order and visibilities
        bridge = QgsLayerTreeMapCanvasBridge(  # noqa: F841, this needs to be assigned
            QgsProject.instance().layerTreeRoot(), qgis_iface.mapCanvas()
        )
        _show_qgis_dlg(common_settings, qgis_parent)

    yield

    if (
        show_map_marker
        and common_settings.gui_enabled
        and not common_settings.qgis_init_disabled
    ):
        _configure_qgis_map(
            qgis_app,
            qgis_iface,
            qgis_parent,
            _parse_show_map_marker(show_map_marker),
            tmp_path,
        )


def _load_qgis_settings(config: "Config") -> None:
    rootdir = config.rootpath
    path = rootdir.joinpath(".qgis-settings")

    os.environ["QGIS_CUSTOM_CONFIG_PATH"] = str(path)
    os.environ["QGIS_OPTIONS_PATH"] = str(path)

    qgis_ini_file = "QGIS3.ini" if _QGIS_VERSION < QGIS_V4_INT else "QGIS4.ini"

    settings_path = path.joinpath("profiles", "default")
    # Copy the ini file at correct location
    settings_file = settings_path.joinpath(
        QgsApplication.QGIS_ORGANIZATION_NAME,
        qgis_ini_file,
    )
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    # Copy the ini file
    settings = rootdir.joinpath("qgis_settings.ini")
    if settings.exists():
        shutil.copyfile(settings, settings_file)

    if _QGIS_VERSION < QGIS_V4_INT:
        settings_format = QSettings.IniFormat
        settings_scope = QSettings.UserScope
    else:
        settings_format = QSettings.Format.IniFormat
        settings_scope = QSettings.Scope.UserScope

    QSettings.setDefaultFormat(settings_format)
    QSettings.setPath(settings_format, settings_scope, str(settings_path))

    qgssettings = QgsSettings()
    LOGGER.info("QGIS Settings loaded from %s", qgssettings.fileName())


def _start_and_configure_qgis_app(config: "Config") -> None:
    global _APP, _CANVAS, _IFACE, _PARENT  # noqa: PLW0603
    settings: Settings = config._plugin_settings

    # From qgis server
    # Will enable us to read qgis setting file
    QCoreApplication.setOrganizationName(QgsApplication.QGIS_ORGANIZATION_NAME)
    QCoreApplication.setOrganizationDomain(QgsApplication.QGIS_ORGANIZATION_DOMAIN)
    QCoreApplication.setApplicationName(QgsApplication.QGIS_APPLICATION_NAME)

    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_ShareOpenGLContexts,
        True,
    )

    _load_qgis_settings(config)

    platform = "server" if settings.qgis_server else None

    if not settings.qgis_init_disabled:
        _APP = QgsApplication(
            [],
            GUIenabled=settings.gui_enabled,
            platformName=platform,
        )
        # Do not initialize QGIS app in qgis server mode
        # Since this is done in QgsServer() initialization
        if not settings.qgis_server:
            _APP.initQgis()
            QgsGui.editorWidgetRegistry().initEditors()

    if not settings.qgis_server:
        _PARENT = QMainWindow()
        _CANVAS = QgsMapCanvas(_PARENT)
        _PARENT.resize(QtCore.QSize(settings.canvas_width, settings.canvas_height))
        _CANVAS.resize(QtCore.QSize(settings.canvas_width, settings.canvas_height))

        # QgisInterface is a stub implementation of the QGIS plugin interface
        _IFACE = QgisInterface(_CANVAS, MockMessageBar(), _PARENT)

        # Patching imported iface (evaluated as None in tests) with iface
        mock.patch("qgis.utils.iface", _IFACE).start()

        if _APP is not None:
            # QGIS zooms to the layer's extent if it
            # is the first layer added to the map.
            # If the qgis_show_map marker is used, this zooming might occur
            # at some later time when events are processed (e.g. at qtbot.wait call)
            # and this might change the extent unexpectedly.
            # It is better to process events right after adding the
            # layer to avoid these kind of problems.
            QgsProject.instance().legendLayersAdded.connect(_APP.processEvents)

    if _APP is not None:
        # Initialize plugin_path is all cases
        _init_qgis_plugins_path(_APP)


def _init_qgis_plugins_path(qgis_app: QgsApplication) -> None:
    # Give access to python QGIS plugins
    python_plugins_path = os.path.join(qgis_app.pkgDataPath(), "python", "plugins")
    if python_plugins_path not in sys.path:
        LOGGER.info("QGIS plugins path: %s", python_plugins_path)
        sys.path.append(python_plugins_path)


def _initialize_processing(_qgis_app: QgsApplication) -> None:
    # Keep the unused arguments explicit because in will require
    # QgsApplication to be initialized instead of assuming it
    # implicitely.
    from processing.core.Processing import Processing  # noqa: PLC0415

    Processing.initialize()


def _show_qgis_dlg(common_settings: Settings, qgis_parent: QWidget) -> None:
    if not common_settings.qgis_init_disabled:
        qgis_parent.setWindowTitle("Test QGIS dialog opened by Pytest-qgis")
        qgis_parent.show()
    elif common_settings.qgis_init_disabled:
        warnings.warn(
            "Cannot show QGIS map because QGIS is not initialized. "
            "Run the tests without --qgis_disable_init to enable QGIS map.",
            stacklevel=1,
        )
    if not common_settings.gui_enabled:
        warnings.warn(
            "QGIS map is not visible because the GUI is not enabled. "
            "Set qgis_gui_enabled=True in pytest.ini to see the window.",
            stacklevel=1,
        )


def _configure_qgis_map(
    qgis_app: QgsApplication,
    qgis_iface: QgisInterface,
    qgis_parent: QWidget,
    settings: ShowMapSettings,
    tmp_path: Path,
) -> None:
    if settings.timeout == 0:
        qgis_parent.close()
        return

    message_box = QMessageBox(qgis_parent)

    try:
        # Change project CRS to most common CRS if it is not set
        if not QgsProject.instance().crs().isValid():
            set_map_crs_based_on_layers()

        extent = settings.extent
        if settings.zoom_to_common_extent and extent is None:
            extent = get_common_extent_from_all_layers()
        if extent is not None:
            qgis_iface.mapCanvas().setExtent(extent)

        # Replace layers with different CRS
        layers_with_different_crs = get_layers_with_different_crs()
        if layers_with_different_crs:
            _initialize_processing(qgis_app)
            replace_layers_with_reprojected_clones(layers_with_different_crs, tmp_path)

        if settings.add_basemap:
            # Add Natural Earth Countries
            countries_layer = _get_countries_layer(_get_world_map_geopackage(tmp_path))
            if not QgsProject.instance().addMapLayer(countries_layer):
                raise AssertionError(
                    f"Failed to add countries layer: {countries_layer.name()}"
                )
            if countries_layer.crs() != QgsProject.instance().crs():
                _initialize_processing(qgis_app)
                replace_layers_with_reprojected_clones([countries_layer], tmp_path)

        QgsProject.instance().reloadAllLayers()
        qgis_iface.mapCanvas().refreshAllLayers()

        message_box.setWindowTitle("pytest-qgis")
        message_box.setText(
            "Click close to close the map and to end the test.\n"
            f"It will close automatically in {settings.timeout} seconds."
        )
        message_box.addButton(QMessageBox.StandardButton.Close)
        message_box.move(QgsApplication.instance().primaryScreen().geometry().topLeft())
        message_box.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        message_box.show()

        t = time.time()
        while time.time() - t < settings.timeout and message_box.isVisible():
            QCoreApplication.processEvents()
    finally:
        message_box.close()
        qgis_parent.close()


def _parse_settings(config: "Config") -> Settings:
    global _QGIS_SERVER  #  noqa: PLW0603

    qgis_server = config.getini(SERVER_KEY)
    if qgis_server:
        gui_enabled = False
        _QGIS_SERVER = True
    else:
        gui_disabled = config.getoption(GUI_DISABLE_KEY)
        if not gui_disabled:
            gui_enabled = config.getini(GUI_ENABLED_KEY)
        else:
            gui_enabled = not gui_disabled

    qgis_init_disabled = config.getoption(DISABLE_QGIS_INIT_KEY)

    qgis_exit_disabled = config.getoption(EXIT_DISABLED_KEY)
    if not qgis_exit_disabled:
        qgis_exit_disabled = config.getini(EXIT_DISABLED_KEY)

    canvas_width = int(config.getini(CANVAS_WIDTH_KEY))
    canvas_height = int(config.getini(CANVAS_HEIGHT_KEY))

    return Settings(
        gui_enabled,
        qgis_init_disabled,
        qgis_exit_disabled,
        qgis_server,
        canvas_width,
        canvas_height,
    )


def _parse_show_map_marker(marker: "Mark") -> ShowMapSettings:  # noqa: C901, PLR0912 TODO: Fix complexity
    timeout = add_basemap = zoom_to_common_extent = extent = notset = object()

    for kwarg, value in marker.kwargs.items():
        if kwarg == "timeout":
            timeout = value
        elif kwarg == "add_basemap":
            add_basemap = value
        elif kwarg == "zoom_to_common_extent":
            zoom_to_common_extent = value
        elif kwarg == "extent":
            extent = value
        else:
            raise TypeError(
                f"Invalid keyword argument for qgis_show_map marker: {kwarg}"
            )

    if len(marker.args) >= 1 and timeout is not notset:
        raise TypeError("Multiple values for timeout argument of qgis_show_map marker")
    elif len(marker.args) >= 1:
        timeout = marker.args[0]
    if len(marker.args) >= 2 and add_basemap is not notset:  # noqa: PLR2004
        raise TypeError(
            "Multiple values for add_basemap argument of qgis_show_map marker"
        )
    elif len(marker.args) >= 2:  # noqa: PLR2004
        add_basemap = marker.args[1]
    if len(marker.args) >= 3 and zoom_to_common_extent is not notset:  # noqa: PLR2004
        raise TypeError(
            "Multiple values for zoom_to_common_extent argument of qgis_show_map marker"
        )
    elif len(marker.args) >= 3:  # noqa: PLR2004
        zoom_to_common_extent = marker.args[2]
    if len(marker.args) >= 4 and extent is not notset:  # noqa: PLR2004
        raise TypeError("Multiple values for extent argument of qgis_show_map marker")
    elif len(marker.args) >= 4:  # noqa: PLR2004
        extent = marker.args[3]
    if len(marker.args) > 4:  # noqa: PLR2004
        raise TypeError("Too many arguments for qgis_show_map marker")

    if timeout is notset:
        timeout = SHOW_MAP_VISIBILITY_TIMEOUT_DEFAULT
    if add_basemap is notset:
        add_basemap = False
    if zoom_to_common_extent is notset:
        zoom_to_common_extent = True
    if extent is notset:
        extent = None
    elif not isinstance(extent, QgsRectangle):
        raise TypeError("Extent has to be of type QgsRectangle")
    return ShowMapSettings(timeout, add_basemap, zoom_to_common_extent, extent)


def _get_world_map_geopackage(tmp_path: Path) -> Path:
    """Copy geopackage to the temporary directory and return the copy."""
    world_map_gpkg = Path(
        QgsApplication.pkgDataPath(), "resources", "data", "world_map.gpkg"
    )
    assert world_map_gpkg.exists(), world_map_gpkg

    # Copy the geopackage to allow modifications
    return Path(shutil.copy(world_map_gpkg, tmp_path))


def _get_countries_layer(geopackage: Path) -> QgsVectorLayer:
    countries_layer = QgsVectorLayer(
        f"{geopackage}|layername=countries",
        "Natural Earth Countries",
        "ogr",
    )
    assert countries_layer.isValid(), geopackage
    return countries_layer
