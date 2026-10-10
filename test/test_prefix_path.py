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
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pytest_qgis import plugin

if TYPE_CHECKING:
    from _pytest.pytester import Pytester


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MagicMock:
    """QgsApplication with paths derived from a venv python symlink like Qt>=6.12."""
    real_python = tmp_path / "usr" / "bin" / "python3"
    real_python.parent.mkdir(parents=True)
    real_python.touch()
    (tmp_path / "usr" / "share" / "qgis" / "resources").mkdir(parents=True)
    venv_python = tmp_path / "venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(real_python)

    app = MagicMock()
    app.pkgDataPath.return_value = str(tmp_path / "venv" / "share" / "qgis")
    monkeypatch.setattr(plugin, "QgsApplication", app)
    monkeypatch.setattr(plugin.sys, "executable", str(venv_python))
    monkeypatch.delenv("QGIS_PREFIX_PATH", raising=False)
    return app


def test_prefix_path_is_resolved_from_venv_python(app: MagicMock, tmp_path: Path):
    plugin._fix_qgis_prefix_path()

    app.setPrefixPath.assert_called_once_with(str(tmp_path / "usr"), True)
    assert os.environ["QGIS_PREFIX_PATH"] == str(tmp_path / "usr")


@pytest.mark.parametrize("case", ["env_set", "data_found", "no_data_in_real_prefix"])
def test_prefix_path_is_kept(
    case: str, app: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    if case == "env_set":
        monkeypatch.setenv("QGIS_PREFIX_PATH", "/custom")
    elif case == "data_found":
        app.pkgDataPath.return_value = str(tmp_path / "usr" / "share" / "qgis")
    else:
        (tmp_path / "usr" / "share" / "qgis" / "resources").rmdir()

    plugin._fix_qgis_prefix_path()

    app.setPrefixPath.assert_not_called()
    expected_env = "/custom" if case == "env_set" else None
    assert os.environ.get("QGIS_PREFIX_PATH") == expected_env


def test_qgis_data_is_found_when_started_from_venv(
    pytester: "Pytester", monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("QGIS_PREFIX_PATH", raising=False)
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_pkg_data_path(qgis_app, qgis_processing):
            assert Path(qgis_app.pkgDataPath(), "resources").is_dir()
    """
    )
    args = ("-p", "no:pytest-qt", "--qgis_disable_gui")
    # Both are started with an absolute path inside the venv
    pytester.runpytest_subprocess(*args).assert_outcomes(passed=1)
    pytest_script = Path(sys.executable).with_name("pytest")
    if pytest_script.exists():
        pytester.run(pytest_script, *args).assert_outcomes(passed=1)
