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
from typing import TYPE_CHECKING

import pytest

from pytest_qgis.pytest_qgis import _get_xdist_worker_id, _is_xdist_controller

if TYPE_CHECKING:
    from _pytest.pytester import Pytester

pytest.importorskip("xdist")


class StubConfig:
    def __init__(self, workerinput=None, dist="no") -> None:
        if workerinput is not None:
            self.workerinput = workerinput
        self._dist = dist

    def getoption(self, name: str, default=None):  # noqa: ARG002
        assert name == "dist"
        return self._dist


def test_worker_id_from_workerinput(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    config = StubConfig(workerinput={"workerid": "gw1"})
    assert _get_xdist_worker_id(config) == "gw1"


def test_worker_id_from_environment(monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw2")
    config = StubConfig()
    assert _get_xdist_worker_id(config) == "gw2"


def test_worker_id_missing(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    config = StubConfig()
    assert _get_xdist_worker_id(config) is None


def test_controller_detected(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    config = StubConfig(dist="load")
    assert _is_xdist_controller(config)


def test_serial_run_is_not_controller(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    config = StubConfig(dist="no")
    assert not _is_xdist_controller(config)


def test_worker_is_not_controller(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    config = StubConfig(workerinput={"workerid": "gw0"}, dist="load")
    assert not _is_xdist_controller(config)


def test_workers_get_isolated_settings_dirs(pytester: "Pytester"):
    pytester.makepyfile(
        """
        from qgis.core import QgsProject, QgsVectorLayer

        def test_first(qgis_new_project):
            layer = QgsVectorLayer("Point?crs=epsg:4326", "layer", "memory")
            assert layer.isValid()
            assert QgsProject.instance().addMapLayer(layer)

        def test_second(qgis_new_project):
            layer = QgsVectorLayer("Point?crs=epsg:4326", "layer", "memory")
            assert layer.isValid()
            assert QgsProject.instance().addMapLayer(layer)
        """
    )
    result = pytester.runpytest_subprocess(
        "-n", "2", "-p", "no:pytest-qt", "--qgis_disable_gui"
    )
    result.assert_outcomes(passed=2)
    # Every worker process creates its own settings directory
    assert (pytester.path / ".qgis-settings" / "gw0").is_dir()
    assert (pytester.path / ".qgis-settings" / "gw1").is_dir()


def test_qgis_settings_ini_copied_per_worker(pytester: "Pytester"):
    pytester.path.joinpath("qgis_settings.ini").write_text(
        "[pytest_qgis]\ntest_setting=success\n"
    )
    pytester.makepyfile(
        """
        from qgis.core import QgsSettings

        def test_setting_first(qgis_app):
            assert QgsSettings().value("pytest_qgis/test_setting") == "success"

        def test_setting_second(qgis_app):
            assert QgsSettings().value("pytest_qgis/test_setting") == "success"
        """
    )
    result = pytester.runpytest_subprocess(
        "-n", "2", "-p", "no:pytest-qt", "--qgis_disable_gui"
    )
    result.assert_outcomes(passed=2)
