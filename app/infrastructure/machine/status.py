"""Разбор ответа оборудования.

Станок отвечает HTML-страницей, внутри которой лежат два блока значений:
`status:{ready:1,state:1,tasks_left:0,products_left:0}` и
`command:{status_request:1,tasks:0`.
"""

import re
from typing import Optional

from app.domain.models import MachineStatus

COMMAND_TITLES = {
    0: "команды не было",
    1: "команда принята",
    2: "команда не принята (ошибка)",
}


class MachineStatusParser:
    """Извлекает состояние оборудования из текста ответа."""

    def parse(self, body: str) -> MachineStatus:
        """Разбирает тело ответа станка.

        Args:
            body: Текст ответа; может быть пустым или неполным.

        Returns:
            Состояние оборудования; неизвестные поля остаются None.
        """
        text = body or ""
        return MachineStatus(
            ready=self._field(text, "ready"),
            state=self._field(text, "state"),
            tasks_left=self._field(text, "tasks_left"),
            products_left=self._field(text, "products_left"),
            status_request=self._field(text, "status_request"),
            command=self._field(text, "tasks"),
            raw=text,
        )

    @staticmethod
    def _field(text: str, name: str) -> Optional[int]:
        """Достаёт числовое поле из ответа.

        Отрицательный просмотр назад не даёт полю `tasks` совпасть с
        началом имени `tasks_left`.

        Args:
            text: Текст ответа.
            name: Имя поля.

        Returns:
            Значение поля либо None, если поле не найдено.
        """
        match = re.search(rf"(?<![_a-zA-Z]){name}\s*:\s*(\d+)", text)
        return int(match.group(1)) if match else None
