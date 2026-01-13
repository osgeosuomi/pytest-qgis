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

from typing import TYPE_CHECKING

import pytest
from qgis.core import Qgis

if TYPE_CHECKING:
    from qgis.gui import QgisInterface


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_level", "expected_message"),
    [
        (["text"], {}, Qgis.Info, "no-title:text"),
        (["title"], {"text": "text"}, Qgis.MessageLevel.Info, "title:text"),
        (
            ["text", Qgis.MessageLevel.Success],
            {},
            Qgis.MessageLevel.Success,
            "no-title:text",
        ),
        (
            ["title", "text", Qgis.MessageLevel.Warning, 20],
            {},
            Qgis.Warning,
            "title:text",
        ),
        (
            ["title", "text", "showMore", Qgis.MessageLevel.Warning, 20],
            {},
            Qgis.Warning,
            "title:text",
        ),
        (
            [],
            {
                "title": "title",
                "text": "text",
                "showMore": "showMore",
                "level": Qgis.MessageLevel.Warning,
                "duration": 20,
            },
            Qgis.Warning,
            "title:text",
        ),
    ],
)
@pytest.mark.usefixtures("qgis_new_project")
def test_message_bar(
    qgis_iface: "QgisInterface",
    args: list,
    kwargs: dict,
    expected_level: Qgis.MessageLevel,
    expected_message: str,
):
    qgis_iface.messageBar().pushMessage(*args, **kwargs)
    assert qgis_iface.messageBar().messages.get(expected_level) == [expected_message]
