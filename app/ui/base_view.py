"""Базовый экран приложения.

Все три экрана выполняют операции по одной схеме: заблокировать управление,
показать индикатор, выполнить, разобрать ошибку, разблокировать, перерисовать.
Схема вынесена в шаблонный метод `run_action`, а экраны переопределяют только
блокировку своих элементов.
"""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional, Sequence, TypeVar

import flet as ft

from app.core.logger import logger
from app.domain.errors import AppError
from app.ui.common import StatusLine

T = TypeVar("T")


class BaseView(ABC):
    """Общее поведение экранов: построение, блокировка, обработка ошибок."""

    def __init__(self, page: ft.Page):
        """Создаёт экран.

        Args:
            page: Страница Flet, которой принадлежит экран.
        """
        self.page = page
        self.status = StatusLine()

    @abstractmethod
    def build(self) -> ft.Control:
        """Строит дерево элементов экрана.

        Returns:
            Корневой элемент экрана.
        """

    def interactive_controls(self) -> Sequence[ft.Control]:
        """Возвращает элементы, блокируемые на время операции.

        Returns:
            Кнопки и поля ввода экрана; по умолчанию — ничего.
        """
        return ()

    def set_enabled(self, enabled: bool) -> None:
        """Включает или выключает элементы управления экрана.

        Args:
            enabled: True — разблокировать, False — заблокировать.
        """
        for control in self.interactive_controls():
            control.disabled = not enabled

    async def run_action(
        self,
        action: Callable[[], Awaitable[T]],
        busy_message: str,
        success_message: Optional[Callable[[T], str]] = None,
        failure_message: str = "Не удалось выполнить операцию",
    ) -> Optional[T]:
        """Выполняет операцию по общей схеме экрана.

        Шаблонный метод: последовательность шагов фиксирована, а конкретную
        работу задаёт `action`.

        Args:
            action: Корутина без аргументов с полезной работой.
            busy_message: Текст индикатора на время выполнения.
            success_message: Функция, строящая текст успеха по результату;
                None — не показывать сообщение об успехе.
            failure_message: Текст для журнала при непредвиденной ошибке.

        Returns:
            Результат операции либо None, если она завершилась ошибкой.
        """
        self.set_enabled(False)
        self.status.busy(busy_message)
        self.page.update()

        result: Optional[T] = None
        try:
            result = await action()
            if success_message is not None:
                self.status.success(success_message(result))
            else:
                self.status.clear()
        except AppError as error:
            # Доменные ошибки уже несут текст для пользователя.
            self.status.error(str(error))
        except Exception as error:  # noqa: BLE001 — в интерфейсе нельзя падать молча
            logger.exception(failure_message)
            self.status.error(f"Непредвиденная ошибка: {error}")

        self.set_enabled(True)
        self.after_action()
        self.page.update()
        return result

    def after_action(self) -> None:
        """Вызывается после операции — момент уточнить состояние элементов.

        По умолчанию ничего не делает.
        """
