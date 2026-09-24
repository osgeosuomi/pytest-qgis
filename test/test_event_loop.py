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
import time
from unittest.mock import Mock

import pytest
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from pytest_qgis.utils import process_events, wait, wait_until


class Emitter(QObject):
    signal = pyqtSignal()


class PollingThread(QThread):
    """Emits ready from run() like an endpoint-polling plugin thread."""

    ready = pyqtSignal()

    def run(self) -> None:
        self.ready.emit()


def test_wait_delivers_queued_signal_to_mock():
    emitter = Emitter()
    mock = Mock()
    emitter.signal.connect(mock, Qt.ConnectionType.QueuedConnection)

    emitter.signal.emit()
    mock.assert_not_called()

    wait(0)
    mock.assert_called_once()


def test_process_events_delivers_queued_signal_to_mock():
    emitter = Emitter()
    mock = Mock()
    emitter.signal.connect(mock, Qt.ConnectionType.QueuedConnection)

    emitter.signal.emit()
    mock.assert_not_called()

    process_events()
    mock.assert_called_once()


def test_wait_zero_flushes_delete_later():
    obj = QObject()
    obj.deleteLater()

    wait(0)

    assert sip.isdeleted(obj)


def test_wait_does_not_busy_spin():
    start_cpu = time.process_time()
    start_wall = time.perf_counter()

    wait(200)

    assert time.perf_counter() - start_wall >= 0.2
    assert time.process_time() - start_cpu < 0.1


@pytest.mark.parametrize("_repetition", range(20))
def test_signal_from_thread_is_delivered_deterministically(_repetition):
    """The canonical flaky pattern: a thread emits into a main-thread mock."""
    thread = PollingThread()
    mock = Mock()
    thread.ready.connect(mock)

    thread.start()
    try:
        assert wait_until(lambda: mock.call_count == 1)
        mock.assert_called_once()
    finally:
        thread.wait()


def test_single_shot_timer_fires_during_wait():
    fired = []
    QTimer.singleShot(10, lambda: fired.append(1))

    wait(100)

    assert fired == [1]


# The two tests below verify together that queued events are flushed at
# test teardown. They rely on their execution order.
_teardown_flush_mock = Mock()
_teardown_flush_emitter: list[Emitter] = []


def test_teardown_flushes_queued_events_part_1():
    emitter = Emitter()
    _teardown_flush_emitter.append(emitter)
    emitter.signal.connect(_teardown_flush_mock, Qt.ConnectionType.QueuedConnection)

    emitter.signal.emit()
    _teardown_flush_mock.assert_not_called()


def test_teardown_flushes_queued_events_part_2():
    _teardown_flush_mock.assert_called_once()
