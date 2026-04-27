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
"""Tests for the extra helpers: run_task, wait_signal,
qgis_message_log fixture and make_memory_layer."""

from __future__ import annotations

import pytest
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal

from pytest_qgis.utils import (
    MessageLogCapture,
    make_memory_layer,
    run_task,
    wait_signal,
)

# ===========================================================================
# run_task
# ===========================================================================


class _SuccessTask(QgsTask):
    def __init__(self, description: str = "ok") -> None:
        super().__init__(description)
        self.ran = False

    def run(self) -> bool:
        self.ran = True
        return True


class _FailureTask(QgsTask):
    def run(self) -> bool:
        return False


class _RaisingTask(QgsTask):
    def run(self) -> bool:
        raise RuntimeError("boom")


@pytest.mark.usefixtures("qgis_app")
class TestRunTask:
    def test_successful_task_returns_true(self) -> None:
        task = _SuccessTask("ok")
        assert run_task(task) is True
        assert task.ran

    def test_failed_task_returns_false(self) -> None:
        task = _FailureTask("fail")
        assert run_task(task) is False

    def test_task_exception_propagates(self) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            run_task(_RaisingTask("boom"))

    def test_rejects_non_task(self) -> None:
        with pytest.raises(TypeError):
            run_task(object())  # type: ignore[arg-type]

    def test_timeout_short_still_returns(self) -> None:
        """A short timeout doesn't block forever even on a no-op task."""
        task = _SuccessTask("short")
        assert run_task(task, timeout_ms=50) is True


# ===========================================================================
# wait_signal
# ===========================================================================


class _Emitter(QObject):
    triggered = pyqtSignal(int, str)
    silent = pyqtSignal()


@pytest.mark.usefixtures("qgis_app")
class TestWaitSignal:
    def test_detects_synchronous_emission_after_timer(self) -> None:
        emitter = _Emitter()
        QTimer.singleShot(10, lambda: emitter.triggered.emit(42, "hi"))
        with wait_signal(emitter.triggered, timeout_ms=500) as w:
            pass
        assert w.triggered
        assert w.timed_out is False
        assert w.args == (42, "hi")

    def test_times_out_when_signal_never_fires(self) -> None:
        emitter = _Emitter()
        with wait_signal(emitter.silent, timeout_ms=20) as w:
            pass
        assert w.triggered is False
        assert w.timed_out is True

    def test_predicate_filter(self) -> None:
        emitter = _Emitter()
        # Fire twice -- once with an unwanted value, then with a matching one.
        QTimer.singleShot(5, lambda: emitter.triggered.emit(1, "skip"))
        QTimer.singleShot(15, lambda: emitter.triggered.emit(2, "keep"))
        with wait_signal(
            emitter.triggered,
            timeout_ms=500,
            check=lambda _i, s: s == "keep",
        ) as w:
            pass
        assert w.triggered
        assert w.args == (2, "keep")

    def test_disconnects_on_exit_even_if_timeout(self) -> None:
        """After the context exits the listener must be disconnected."""
        emitter = _Emitter()
        with wait_signal(emitter.silent, timeout_ms=5):
            pass
        # If still connected, emitting the signal after the context would
        # schedule another loop.  Emit and verify that nothing crashes;
        # the check is mostly that disconnect() didn't raise.
        emitter.silent.emit()


# ===========================================================================
# qgis_message_log fixture
# ===========================================================================


class TestMessageLogCapture:
    def test_captures_emissions(self, qgis_message_log: MessageLogCapture):
        QgsMessageLog.logMessage("hello world", "OMRAT", Qgis.Info)
        QgsMessageLog.logMessage("oops", "OMRAT", Qgis.Warning)
        # QgsMessageLog.messageReceived fires synchronously.
        assert len(qgis_message_log.entries) >= 2
        messages = [e.message for e in qgis_message_log.entries]
        assert "hello world" in messages
        assert "oops" in messages

    def test_level_filters(self, qgis_message_log: MessageLogCapture):
        QgsMessageLog.logMessage("info msg", "T", Qgis.Info)
        QgsMessageLog.logMessage("warn msg", "T", Qgis.Warning)
        QgsMessageLog.logMessage("crit msg", "T", Qgis.Critical)
        infos = [e.message for e in qgis_message_log.infos]
        warnings = [e.message for e in qgis_message_log.warnings]
        errors = [e.message for e in qgis_message_log.errors]
        assert "info msg" in infos
        assert "warn msg" in warnings
        assert "crit msg" in errors

    def test_find_substring(self, qgis_message_log: MessageLogCapture):
        QgsMessageLog.logMessage("the drift speed is 1.94 kts", "T", Qgis.Info)
        hit = qgis_message_log.find("drift speed")
        assert hit is not None
        assert "1.94" in hit.message

    def test_find_returns_none_for_unknown_text(
        self, qgis_message_log: MessageLogCapture
    ):
        QgsMessageLog.logMessage("foo", "T", Qgis.Info)
        assert qgis_message_log.find("bar") is None

    def test_entry_is_tuple_unpackable(self, qgis_message_log: MessageLogCapture):
        QgsMessageLog.logMessage("x", "tag", Qgis.Warning)
        entry = qgis_message_log.entries[-1]
        msg, tag, level = entry
        assert msg == "x"
        assert tag == "tag"
        assert level == Qgis.Warning

    def test_filter_by_tag(self, qgis_message_log: MessageLogCapture):
        QgsMessageLog.logMessage("a", "TAGA", Qgis.Info)
        QgsMessageLog.logMessage("b", "TAGB", Qgis.Info)
        taga = qgis_message_log.filter(tag="TAGA")
        assert [e.message for e in taga] == ["a"]

    def test_clear_drops_existing_entries(self, qgis_message_log: MessageLogCapture):
        QgsMessageLog.logMessage("first", "T", Qgis.Info)
        qgis_message_log.clear()
        assert qgis_message_log.entries == []


# ===========================================================================
# make_memory_layer
# ===========================================================================


@pytest.mark.usefixtures("qgis_app")
class TestMakeMemoryLayer:
    def test_bare_wkt_strings_build_layer(self) -> None:
        layer = make_memory_layer(
            [
                "POINT(14.0 55.0)",
                "POINT(14.5 55.5)",
            ]
        )
        assert isinstance(layer, QgsVectorLayer)
        assert layer.isValid()
        assert layer.featureCount() == 2
        assert layer.geometryType() == 0  # Point

    def test_fields_inferred_from_first_feature(self) -> None:
        layer = make_memory_layer(
            [
                ("POINT(0 0)", {"name": "a", "depth": 10.0}),
                ("POINT(1 1)", {"name": "b", "depth": 20.0}),
            ]
        )
        field_names = [f.name() for f in layer.fields()]
        assert field_names == ["name", "depth"]
        features = list(layer.getFeatures())
        assert features[0]["name"] == "a"
        assert features[0]["depth"] == 10.0
        assert features[1]["name"] == "b"
        assert features[1]["depth"] == 20.0

    def test_explicit_fields_override_inference(self) -> None:
        layer = make_memory_layer(
            [("POINT(0 0)", {"n": 5})],
            fields={"n": int, "label": str},
        )
        assert sorted(f.name() for f in layer.fields()) == ["label", "n"]

    def test_linestring_geometry_auto_detected(self) -> None:
        layer = make_memory_layer(["LINESTRING(0 0, 1 1, 2 0)"])
        assert layer.geometryType() == 1  # Line

    def test_polygon_geometry_auto_detected(self) -> None:
        layer = make_memory_layer(["POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"])
        assert layer.geometryType() == 2  # Polygon

    def test_explicit_crs(self) -> None:
        layer = make_memory_layer(["POINT(0 0)"], crs="EPSG:3857")
        assert layer.crs().authid() == "EPSG:3857"

    def test_empty_features_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty sequence"):
            make_memory_layer([])

    def test_invalid_wkt_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not"):
            make_memory_layer(["THIS IS NOT WKT"])

    def test_unsupported_field_type_raises(self) -> None:
        with pytest.raises(TypeError, match="unsupported type"):
            make_memory_layer(
                [("POINT(0 0)", {"bad": object()})],
                fields={"bad": object},
            )
