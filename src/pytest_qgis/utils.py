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
import contextlib
import time
from collections import Counter
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union
from unittest.mock import MagicMock

from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsLayerTree,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMapLayer,
    QgsMessageLog,
    QgsProcessing,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QElapsedTimer,
    QEventLoop,
    QTimer,
    QVariant,
    pyqtBoundSignal,
)

if TYPE_CHECKING:
    from _pytest.fixtures import FixtureRequest

DEFAULT_RASTER_FORMAT = "tif"

DEFAULT_EPSG = "EPSG:4326"
LAYER_KEYWORDS = ("layer", "lyr", "raster", "rast", "tif")


def get_common_extent_from_all_layers() -> QgsRectangle | None:
    """Get common extent from all QGIS layers in the project."""
    map_crs = QgsProject.instance().crs()
    layers = list(QgsProject.instance().mapLayers(validOnly=True).values())

    if layers:
        extent = transform_rectangle(layers[0].extent(), layers[0].crs(), map_crs)
        for layer in layers[1:]:
            extent.combineExtentWith(
                transform_rectangle(layer.extent(), layer.crs(), map_crs)
            )
        return extent
    return None


def set_map_crs_based_on_layers() -> None:
    """Set map crs based on layers of the project."""
    crs_counter = Counter(
        layer.crs().authid()
        for layer in QgsProject.instance().mapLayers().values()
        if layer.isSpatial()
    )
    if crs_counter:
        crs_id, _ = crs_counter.most_common(1)[0]
        crs = QgsCoordinateReferenceSystem(crs_id)
    else:
        crs = QgsCoordinateReferenceSystem(DEFAULT_EPSG)
    QgsProject.instance().setCrs(crs)


def transform_rectangle(
    rectangle: QgsRectangle,
    in_crs: QgsCoordinateReferenceSystem,
    out_crs: QgsCoordinateReferenceSystem,
) -> QgsRectangle:
    """
    Transform rectangle from one crs to other.
    """
    if in_crs == out_crs:
        return rectangle

    transform = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem(in_crs),
        QgsCoordinateReferenceSystem(out_crs),
        QgsProject.instance(),
    )
    return transform.transformBoundingBox(rectangle)


def get_layers_with_different_crs() -> list[QgsMapLayer]:
    map_crs = QgsProject.instance().crs()
    return [
        layer
        for layer in QgsProject.instance().mapLayers().values()
        if layer.crs() != map_crs
    ]


def replace_layers_with_reprojected_clones(
    layers: list[QgsMapLayer], output_path: Path
) -> None:
    """
    For some reason all layers having differing crs from the project are invisible.
    Hotfix is to replace those by reprojected layers with map crs.
    """
    import processing  # noqa: PLC0415

    vector_layers = [
        layer
        for layer in layers
        if isinstance(layer, QgsVectorLayer) and layer.isSpatial()
    ]
    raster_layers = [
        layer
        for layer in layers
        if isinstance(layer, QgsRasterLayer) and layer.isSpatial()
    ]

    map_crs = QgsProject.instance().crs()
    for input_layer in vector_layers:
        output_layer: QgsVectorLayer = processing.run(  # noqa: QGS110
            "native:reprojectlayer",
            {
                "INPUT": input_layer,
                "TARGET_CRS": map_crs,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
        )["OUTPUT"]
        if not output_layer.crs().isValid():
            output_layer.setCrs(map_crs)

        copy_layer_style_and_position(input_layer, output_layer, output_path)

    for input_layer in raster_layers:
        try:
            output_raster = str(
                Path(output_path, f"{input_layer.name()}.{DEFAULT_RASTER_FORMAT}")
            )
            warp = gdal.Warp(
                output_raster, input_layer.source(), dstSRS=map_crs.authid()
            )

        finally:
            warp = None  # noqa: F841

        output_layer = QgsRasterLayer(output_raster)
        if not output_layer.crs().isValid():
            output_layer.setCrs(map_crs)
        copy_layer_style_and_position(input_layer, output_layer, output_path)

    # Remove originals from project
    QgsProject.instance().removeMapLayers([layer.id() for layer in layers])


def copy_layer_style_and_position(
    layer1: QgsMapLayer, layer2: QgsMapLayer, tmp_path: Path
) -> None:
    """
    Copy layer style and position to another layer.
    """
    style_file = str(Path(tmp_path, f"{layer1.id()}.qml"))
    error_msg, succeeded = layer1.saveNamedStyle(style_file)
    if not succeeded:
        raise AssertionError(f"Failed to save layer style to {style_file}: {error_msg}")

    error_msg, succeeded = layer2.loadNamedStyle(style_file)
    if not succeeded:
        raise AssertionError(
            f"Failed to load layer style from {style_file}: {error_msg}"
        )
    layer2.setMetadata(layer1.metadata())
    layer2.setName(layer1.name())
    if layer2.isValid():  # noqa: SIM102
        if not QgsProject.instance().addMapLayer(layer2, False):
            raise AssertionError(f"Failed to add layer {layer2.name()} to project")

    root: QgsLayerTree = QgsProject.instance().layerTreeRoot()
    layer_tree_layer: QgsLayerTreeLayer = root.findLayer(layer1)
    group: QgsLayerTreeGroup = layer_tree_layer.parent()
    index = {child.name(): i for i, child in enumerate(group.children())}[
        layer_tree_layer.name()
    ]

    group.insertLayer(index + 1, layer2)


def clean_qgis_layer(fn: Callable[..., QgsMapLayer]) -> Callable[..., QgsMapLayer]:
    """
    Decorator to ensure that a map layer created by a fixture is cleaned properly.

    Sometimes fixture non-memory layers that are used but not added
    to the project might cause segmentation fault errors.

    This decorator works only with fixtures that **return** QgsMapLayer instances.
    There is no support for fixtures that use yield.

    >>> @pytest.fixture()
    >>> @clean_qgis_layer
    >>> def geojson_layer() -> QgsVectorLayer:
    >>>     layer = QgsVectorLayer("layer.json", "layer", "ogr")
    >>>     return layer

    This decorator is the alternative way of cleaning the layers since layer fixtures
    are automatically cleaned if they contain one of the keywords listed in
    LAYER_KEYWORDS by pytest_runtest_teardown hook.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Generator[QgsMapLayer, None, None]:
        layer = fn(*args, **kwargs)
        yield layer
        _set_layer_owner_to_project(layer)

    return wrapper


def ensure_qgis_layer_fixtures_are_cleaned(request: "FixtureRequest") -> None:
    """
    Sometimes fixture non-memory layers that are used but not added
    to the project might cause segmentation fault errors.

    This function ensures that the layer fixtures will be cleaned by
    adding and removing those into the project.

    It does not matter what scoped the fixtures are since the
    layers are not actually deleted at any point.
    """
    for fixture_name in request.fixturenames:
        if any(
            possible_layer_name in fixture_name.lower()
            for possible_layer_name in LAYER_KEYWORDS
        ):
            try:
                layer = request.getfixturevalue(fixture_name)
            except AssertionError:
                continue
            _set_layer_owner_to_project(layer)


def _set_layer_owner_to_project(layer: Any) -> None:
    if (
        isinstance(layer, QgsMapLayer)
        and not isinstance(layer, MagicMock)
        and not sip.isdeleted(layer)
        and layer.id() not in QgsProject.instance().mapLayers(True)
    ):
        if not QgsProject.instance().addMapLayer(layer):
            raise AssertionError(f"Failed to add layer {layer.name()} to project")
        QgsProject.instance().removeMapLayer(layer)


def wait(wait_time_milliseconds: int = 0) -> None:
    """Waits for wait_time ms."""
    start = time.time()

    while (time.time() - start) * 1000 < wait_time_milliseconds:
        QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# Task runner: synchronous execution of QgsTask subclasses in tests
# ---------------------------------------------------------------------------


def run_task(
    task: QgsTask,
    *,
    timeout_ms: int = 30_000,
    pump_interval_ms: int = 10,
) -> bool:
    """Run a ``QgsTask`` synchronously and wait until it finishes.

    This is meant for unit-testing task subclasses without spinning up
    the full ``QgsTaskManager``.  It calls ``task.run()`` on the current
    thread (same as a non-threaded processing task), then pumps the
    Qt event loop until ``task.isCanceled()`` or ``task.status() ==
    Complete/Terminated`` to make sure the ``taskCompleted`` /
    ``taskTerminated`` signals are delivered to any listeners.

    Args:
        task: The ``QgsTask`` instance.  It must not have been added to
            any ``QgsTaskManager`` yet.
        timeout_ms: Abort the pump loop after this many milliseconds.
            Defaults to 30 seconds.
        pump_interval_ms: How long to wait between event-pump batches.

    Returns:
        The return value of ``task.run()`` (``True`` on success,
        ``False`` on failure).

    Example:
        >>> def test_my_task(qgis_app):
        ...     task = MyTask("desc")
        ...     assert run_task(task) is True
        ...     assert task.result_value == 42
    """
    if not isinstance(task, QgsTask):
        raise TypeError(
            f"run_task expects a QgsTask instance, got {type(task).__name__}"
        )
    try:
        result = task.run()
    except Exception:  # re-raise after pumping pending events
        wait(pump_interval_ms)
        raise

    # Let Qt emit taskCompleted / taskTerminated to any listeners.
    # Qt6 (QGIS 4) scopes the flag under QEventLoop.ProcessEventsFlag;
    # Qt5 (QGIS 3) exposes it flat on QEventLoop.  Try the nested form
    # first, then fall back.
    _all_events = getattr(
        getattr(QEventLoop, "ProcessEventsFlag", None),
        "AllEvents",
        getattr(QEventLoop, "AllEvents", None),
    )

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < timeout_ms:
        if _all_events is not None:
            QCoreApplication.processEvents(_all_events, pump_interval_ms)
        else:  # pragma: no cover - defensive
            QCoreApplication.processEvents()
        status = task.status()
        done_statuses = (
            getattr(QgsTask, "Complete", None),
            getattr(QgsTask, "Terminated", None),
        )
        if status in done_statuses or task.isCanceled():
            break
    # finalize hook so any cleanup logic runs on the main thread
    try:
        task.finished(result)
    except Exception:
        pass
    return bool(result)


# ---------------------------------------------------------------------------
# Signal waiter: block until a pyqt signal fires (with optional predicate)
# ---------------------------------------------------------------------------


class _SignalWaiter:
    """Helper returned by :func:`wait_signal`.  Exposes the captured
    args on the ``args`` attribute after the context manager exits."""

    def __init__(
        self,
        signal: pyqtBoundSignal,
        timeout_ms: int,
        check: Callable[..., bool] | None,
    ) -> None:
        self._signal = signal
        self._timeout_ms = timeout_ms
        self._check = check
        self._loop = QEventLoop()
        self.args: tuple = ()
        self.triggered: bool = False
        self.timed_out: bool = False

    def _on_signal(self, *args: Any) -> None:
        if self._check is not None and not self._check(*args):
            return  # keep waiting
        self.args = args
        self.triggered = True
        self._loop.quit()

    def _on_timeout(self) -> None:
        self.timed_out = True
        self._loop.quit()

    def __enter__(self) -> "_SignalWaiter":
        self._signal.connect(self._on_signal)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None and not self.triggered:
                QTimer.singleShot(self._timeout_ms, self._on_timeout)
                self._loop.exec()
        finally:
            try:
                self._signal.disconnect(self._on_signal)
            except TypeError:
                pass  # already disconnected


def wait_signal(
    signal: pyqtBoundSignal,
    *,
    timeout_ms: int = 1_000,
    check: Callable[..., bool] | None = None,
) -> _SignalWaiter:
    """Context manager that blocks until a Qt signal is emitted.

    Args:
        signal: A bound ``pyqtSignal`` to wait on.
        timeout_ms: Abort after this many milliseconds.  Default 1 s.
        check: Optional predicate ``(*args) -> bool`` invoked for every
            emission.  When provided, the wait continues until the
            predicate returns ``True`` (or the timeout fires).

    Example:
        >>> with wait_signal(task.taskCompleted, timeout_ms=500) as w:
        ...     QgsApplication.taskManager().addTask(task)
        >>> assert w.triggered, "task did not complete within 500 ms"

    The returned object also exposes:
        * ``args``      -- tuple of args from the emission that triggered it
        * ``triggered`` -- whether the signal fired before the timeout
        * ``timed_out`` -- whether the timeout fired first
    """
    return _SignalWaiter(signal, timeout_ms=timeout_ms, check=check)


# ---------------------------------------------------------------------------
# QgsMessageLog capture
# ---------------------------------------------------------------------------


class MessageLogEntry(
    # Using tuple[str, str, int] via a lightweight namedtuple-ish class
    # keeps the API usable without an extra dependency on dataclasses.
):
    __slots__ = ("message", "tag", "level")

    def __init__(self, message: str, tag: str, level: int) -> None:
        self.message = message
        self.tag = tag
        self.level = level

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        lvl_name = {
            Qgis.Info: "Info",
            Qgis.Warning: "Warning",
            Qgis.Critical: "Critical",
            Qgis.Success: "Success",
        }.get(self.level, str(self.level))
        return f"MessageLogEntry({lvl_name}, tag={self.tag!r}, message={self.message!r})"

    def __iter__(self) -> Iterator[Any]:
        # Allow tuple-style unpacking: message, tag, level = entry
        return iter((self.message, self.tag, self.level))


class MessageLogCapture:
    """Capture context for ``QgsMessageLog.logMessage`` emissions.

    Access captured entries via ``.entries`` (list of
    :class:`MessageLogEntry`).  Helpers ``warnings`` / ``errors`` /
    ``infos`` filter by level.  ``find(text, level=...)`` returns the
    first entry whose message contains ``text``.

    Implementation note: ``QgsMessageLog.messageReceived`` is unreliable
    in some pytest-qgis contexts because the log instance may not be
    initialised the way a full QGIS app instance would.  To avoid
    surprise, we install a thin wrapper around the static
    ``QgsMessageLog.logMessage`` classmethod that records the call and
    then delegates to the original implementation.  The wrapper is
    removed on ``disconnect()``.
    """

    def __init__(self) -> None:
        self.entries: list[MessageLogEntry] = []
        self._original: Any = None

    def _wrap_log_message(
        self, message: str, tag: str = "default", level: int = 0, **_kwargs: Any
    ) -> None:
        self.entries.append(MessageLogEntry(message, tag, level))
        # Delegate to the original so the real logger still does its thing.
        if self._original is not None:
            try:
                self._original(message, tag, level)
            except Exception:  # pragma: no cover - never mask test state
                pass

    def connect(self) -> None:
        from qgis.core import QgsMessageLog  # noqa: PLC0415 - avoid top-level hit

        if self._original is not None:
            return  # already connected
        self._original = QgsMessageLog.logMessage
        QgsMessageLog.logMessage = staticmethod(self._wrap_log_message)

    def disconnect(self) -> None:
        from qgis.core import QgsMessageLog  # noqa: PLC0415

        if self._original is None:
            return
        QgsMessageLog.logMessage = staticmethod(self._original)
        self._original = None

    # Filters ---------------------------------------------------------------
    def filter(
        self, *, level: int | None = None, tag: str | None = None
    ) -> list[MessageLogEntry]:
        out = self.entries
        if level is not None:
            out = [e for e in out if e.level == level]
        if tag is not None:
            out = [e for e in out if e.tag == tag]
        return out

    @property
    def warnings(self) -> list[MessageLogEntry]:
        return self.filter(level=Qgis.Warning)

    @property
    def errors(self) -> list[MessageLogEntry]:
        return self.filter(level=Qgis.Critical)

    @property
    def infos(self) -> list[MessageLogEntry]:
        return self.filter(level=Qgis.Info)

    def find(
        self,
        text: str,
        *,
        level: int | None = None,
        tag: str | None = None,
    ) -> MessageLogEntry | None:
        """Return the first entry whose message contains ``text``."""
        for entry in self.filter(level=level, tag=tag):
            if text in entry.message:
                return entry
        return None

    def clear(self) -> None:
        self.entries.clear()


def _get_qgs_application():
    """Internal helper -- avoids a top-level import cycle."""
    from qgis.core import QgsApplication as _QgsApplication  # noqa: PLC0415

    return _QgsApplication


# ---------------------------------------------------------------------------
# Vector layer builder
# ---------------------------------------------------------------------------

_GEOMETRY_KIND_BY_WKT_PREFIX: Mapping[str, str] = {
    "POINT": "Point",
    "MULTIPOINT": "MultiPoint",
    "LINESTRING": "LineString",
    "MULTILINESTRING": "MultiLineString",
    "POLYGON": "Polygon",
    "MULTIPOLYGON": "MultiPolygon",
}


def _infer_geometry_kind(sample: str) -> str:
    prefix = sample.strip().upper().split("(", 1)[0].strip()
    if prefix not in _GEOMETRY_KIND_BY_WKT_PREFIX:
        raise ValueError(
            f"Could not infer geometry kind from WKT prefix {prefix!r}. "
            f"Supported: {sorted(_GEOMETRY_KIND_BY_WKT_PREFIX)}"
        )
    return _GEOMETRY_KIND_BY_WKT_PREFIX[prefix]


_PYTHON_TYPE_TO_QVARIANT: Mapping[type, Any] = {
    int: QVariant.Int,
    float: QVariant.Double,
    str: QVariant.String,
    bool: QVariant.Bool,
}


def make_memory_layer(
    features: Sequence[Union[str, tuple[str, Mapping[str, Any]]]],
    *,
    fields: Mapping[str, type] | None = None,
    crs: str = "EPSG:4326",
    name: str = "memory",
    geometry_kind: str | None = None,
) -> QgsVectorLayer:
    """Build an in-memory QgsVectorLayer from WKT strings.

    Args:
        features: Sequence of either ``wkt`` strings, or ``(wkt, attrs)``
            tuples where ``attrs`` is a mapping from field name to value.
        fields: Mapping from field name to Python type.  Supported types:
            ``int``, ``float``, ``str``, ``bool``.  If omitted, fields
            are inferred from the first feature's attribute dict.
        crs: Layer CRS auth id (default ``EPSG:4326``).
        name: Layer display name (default ``"memory"``).
        geometry_kind: Override the geometry type (one of ``"Point"``,
            ``"LineString"``, ``"Polygon"``, etc.).  When omitted, the
            kind is inferred from the first feature's WKT prefix.

    Returns:
        A valid :class:`QgsVectorLayer` with the features and fields
        populated.  The layer is *not* added to ``QgsProject``.

    Example:
        >>> layer = make_memory_layer([
        ...     ("POINT(14 55)", {"name": "harbour", "depth": 7.5}),
        ...     ("POINT(15 55)", {"name": "wreck",   "depth": 18.0}),
        ... ], crs="EPSG:4326")
        >>> layer.isValid()
        True
        >>> layer.featureCount()
        2
    """
    if not features:
        raise ValueError("features must be a non-empty sequence")

    # Normalise input to (wkt, attrs) pairs and infer schema.
    normalised: list[tuple[str, dict[str, Any]]] = []
    for item in features:
        if isinstance(item, str):
            normalised.append((item, {}))
        else:
            wkt, attrs = item
            normalised.append((wkt, dict(attrs)))

    if geometry_kind is None:
        geometry_kind = _infer_geometry_kind(normalised[0][0])

    if fields is None:
        first_attrs = normalised[0][1]
        fields = {k: type(v) for k, v in first_attrs.items()}

    # Create the layer.
    layer = QgsVectorLayer(
        f"{geometry_kind}?crs={crs}", name, "memory"
    )
    if not layer.isValid():
        raise RuntimeError(
            f"Failed to construct memory layer (geom={geometry_kind}, crs={crs})"
        )
    pr = layer.dataProvider()

    # Schema.
    qgs_fields: list[QgsField] = []
    for fname, fpy_type in fields.items():
        qvariant = _PYTHON_TYPE_TO_QVARIANT.get(fpy_type)
        if qvariant is None:
            raise TypeError(
                f"Field {fname!r}: unsupported type {fpy_type!r}. "
                f"Supported: {sorted(t.__name__ for t in _PYTHON_TYPE_TO_QVARIANT)}"
            )
        qgs_fields.append(QgsField(fname, qvariant))
    if qgs_fields:
        pr.addAttributes(qgs_fields)
        layer.updateFields()

    # Features.
    field_names = list(fields.keys())
    for wkt, attrs in normalised:
        geom = QgsGeometry.fromWkt(wkt)
        if geom.isEmpty():
            raise ValueError(f"Could not parse WKT: {wkt!r}")
        feat = QgsFeature(layer.fields())
        feat.setGeometry(geom)
        for fname in field_names:
            feat.setAttribute(fname, attrs.get(fname))
        pr.addFeature(feat)

    layer.updateExtents()
    return layer
