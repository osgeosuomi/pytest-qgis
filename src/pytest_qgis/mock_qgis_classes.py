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
import typing

from qgis.core import Qgis
from qgis.gui import QgsMessageBar as QgsMessageBarOriginal


class MockMessageBar(QgsMessageBarOriginal):
    """Mocked message bar to hold the messages."""

    def __init__(self) -> None:
        super().__init__(None)
        self.messages: dict[int, list[str]] = {}
        self._init_messages()

    def _init_messages(self) -> None:
        self.messages = {
            Qgis.MessageLevel.Info: [],
            Qgis.MessageLevel.Warning: [],
            Qgis.MessageLevel.Critical: [],
            Qgis.MessageLevel.Success: [],
        }

    def get_messages(self, level: int) -> list[str]:
        """Used to test which messages have been logged."""
        return self.messages[level]

    def clear_messages(self) -> None:
        """Clear logged messages."""
        self._init_messages()

    @typing.overload
    def pushMessage(
        self,
        text: typing.Optional[str] = None,
        level: Qgis.MessageLevel = Qgis.MessageLevel.Info,
        duration: int = -1,
    ) -> None: ...

    @typing.overload
    def pushMessage(
        self,
        title: typing.Optional[str] = None,
        text: typing.Optional[str] = None,
        level: Qgis.MessageLevel = Qgis.MessageLevel.Info,
        duration: int = -1,
    ) -> None: ...

    @typing.overload
    def pushMessage(
        self,
        title: typing.Optional[str] = None,
        text: typing.Optional[str] = None,
        showMore: typing.Optional[str] = None,  # noqa: N803
        level: Qgis.MessageLevel = Qgis.MessageLevel.Info,
        duration: int = -1,
    ) -> None: ...

    @typing.no_type_check
    def pushMessage(  # noqa: N802
        self,
        *args: typing.Union[str, int],
        **kwargs: dict[str, typing.Union[str, int]],
    ) -> None:
        """A mocked method for pushing a message to the bar."""
        title = kwargs.get("title")
        text = kwargs.get("text")
        level = kwargs.get("level", Qgis.MessageLevel.Info)

        length = len(args)
        if length == 1 and not text:
            text = args[0]
        elif length == 1 and not title:
            title = args[0]
        elif length > 1 and isinstance(args[1], str):
            # title, text, level, ...
            title = args[0]
            text = args[1]
            if length > 2 and isinstance(args[2], int):  # noqa: PLR2004
                level = args[2]
            elif length > 3 and isinstance(args[3], int):  # noqa: PLR2004
                level = args[3]
        elif length > 1 and isinstance(args[1], int):
            # text, level, ...
            text = args[0]
            level = args[1]
        elif args and not text:
            text = ", ".join(map(str, args))

        msg = f"{title or 'no-title'}:{text}"
        self.messages[level].append(msg)
