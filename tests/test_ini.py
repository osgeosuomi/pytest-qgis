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

if TYPE_CHECKING:
    from _pytest.pytester import Testdir


def test_ini_canvas(testdir: "Testdir"):
    testdir.makeini(
        """
        [pytest]
        qgis_canvas_height=1000
        qgis_canvas_width=1200
    """
    )
    testdir.makepyfile(
        """
        def test_canvas(qgis_canvas):
            assert qgis_canvas.width() == 1200
            assert qgis_canvas.height() == 1000
    """
    )
    result = testdir.runpytest("--qgis_disable_init")
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("gui_enabled", [True, False])
def test_ini_gui(gui_enabled: bool, testdir: "Testdir"):
    testdir.makeini(
        f"""
        [pytest]
        qgis_qui_enabled={gui_enabled}
    """
    )

    testdir.makepyfile(
        f"""
        import os

        def test_offscreen(qgis_new_project):
            assert (os.environ.get("QT_QPA_PLATFORM", "") ==
            "{"offscreen" if not gui_enabled else ""}")
    """
    )
    result = testdir.runpytest("--qgis_disable_init")
    result.assert_outcomes(passed=1)

    result = testdir.runpytest("--qgis_disable_init", "--qgis_disable_gui")
    result.assert_outcomes(
        passed=1 if not gui_enabled else 0, failed=1 if gui_enabled else 0
    )
