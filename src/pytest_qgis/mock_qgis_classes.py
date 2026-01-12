#  Copyright (C) 2021-2023 pytest-qgis Contributors.
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


from typing import Dict, List

from qgis.core import Qgis
from qgis.PyQt.QtCore import QObject


class MockMessageBar(QObject):
    """Mocked message bar to hold the messages."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: Dict[int, List[str]] = {
            Qgis.MessageLevel.Info: [],
            Qgis.MessageLevel.Warning: [],
            Qgis.MessageLevel.Critical: [],
            Qgis.MessageLevel.Success: [],
        }

    def get_messages(self, level: int) -> List[str]:
        """Used to test which messages have been logged."""
        return self.messages[level]

    def pushMessage(  # noqa: N802
        self,
        title: str,
        text: str,
        level: int,
        duration: int,  # noqa: ARG002
    ) -> None:
        """A mocked method for pushing a message to the bar."""
        msg = f"{title}:{text}"
        self.messages[level].append(msg)
