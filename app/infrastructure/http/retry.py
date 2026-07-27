"""Политика повторов сетевых запросов.

Вынесена отдельным объектом: транспорт отвечает за сам запрос, политика — за
решение «повторять или сдаться». Их можно менять независимо, а в тестах —
подставить политику без задержек.
"""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

import aiohttp

from app.core.logger import logger

T = TypeVar("T")

RETRIABLE_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError)


@dataclass(frozen=True)
class RetryPolicy:
    """Параметры повторов при сетевых сбоях.

    Значения подобраны под интерфейс: пользователь должен быстро увидеть
    ошибку и починить настройки, а не ждать минутами.

    Attributes:
        attempts: Общее число попыток, включая первую.
        initial_delay: Пауза перед вторым запросом в секундах.
        backoff_factor: Во сколько раз растёт пауза после каждой неудачи.
        max_delay: Верхняя граница паузы в секундах.
    """

    attempts: int = 3
    initial_delay: float = 0.5
    backoff_factor: float = 2.0
    max_delay: float = 4.0

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Выполняет операцию, повторяя её при сетевых сбоях.

        Args:
            operation: Корутина без аргументов, выполняющая запрос.

        Returns:
            Результат первой успешной попытки.

        Raises:
            ConnectionError: Все попытки исчерпаны; текст пригоден для показа.
        """
        delay = self.initial_delay
        last_error: Optional[BaseException] = None

        for attempt in range(1, self.attempts + 1):
            try:
                return await operation()
            except RETRIABLE_ERRORS as error:
                last_error = error
                logger.warning(f"Попытка {attempt}/{self.attempts} не удалась: {error!r}")
                if attempt == self.attempts:
                    break
                await asyncio.sleep(delay)
                delay = min(delay * self.backoff_factor, self.max_delay)

        raise ConnectionError(self.describe(last_error)) from last_error

    @staticmethod
    def describe(error: Optional[BaseException]) -> str:
        """Переводит сетевую ошибку в понятный пользователю текст.

        Args:
            error: Последняя перехваченная ошибка.

        Returns:
            Сообщение для интерфейса.
        """
        if isinstance(error, asyncio.TimeoutError):
            return "Превышено время ожидания ответа"
        if isinstance(error, aiohttp.ClientConnectorError):
            return f"Не удалось подключиться: {error.os_error}"
        if error is not None:
            return f"Ошибка сети: {error}"
        return "Ошибка сети"
