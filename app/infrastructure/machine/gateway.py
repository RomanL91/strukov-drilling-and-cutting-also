"""Шлюз к линии сверления и отреза ALSO.

Паттерн «Шлюз»: сценарии вызывают `read_status` и `send`, не зная ни про HTTP,
ни про формат ответа. Другой способ ввода заданий (например, печать QR-кода,
описанная в разделе 5 документации) — это другая реализация `MachineGateway`.
"""

from yarl import URL

from app.core.logger import logger
from app.domain.errors import MachineError
from app.domain.models import MachinePacket, MachineStatus
from app.infrastructure.http.client import HttpClient
from app.infrastructure.machine.protocol import status_request_url
from app.infrastructure.machine.status import COMMAND_TITLES, MachineStatusParser


class AlsoMachineGateway:
    """Обмен с оборудованием по протоколу iPAP2 поверх HTTP."""

    def __init__(
        self,
        http: HttpClient,
        base_url: str,
        parser: MachineStatusParser,
        timeout: float = 30.0,
    ):
        """Создаёт шлюз для конкретного адреса оборудования.

        Args:
            http: Общий HTTP-транспорт приложения.
            base_url: Базовый адрес станка.
            parser: Разборщик ответа оборудования.
            timeout: Таймаут запроса в секундах.
        """
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._parser = parser
        self._timeout = timeout

    async def read_status(self) -> MachineStatus:
        """Запрашивает состояние командой `{status_request:1}`.

        Returns:
            Разобранное состояние оборудования.

        Raises:
            MachineError: Оборудование недоступно или ответило ошибкой HTTP.
        """
        return await self._exchange(
            status_request_url(self._base_url), timeout=min(self._timeout, 10.0)
        )

    async def send(self, packet: MachinePacket) -> MachineStatus:
        """Отправляет пакет заданий и проверяет, что он принят.

        Args:
            packet: Проверенный пакет заданий.

        Returns:
            Состояние оборудования после приёма пакета.

        Raises:
            MachineError: Оборудование недоступно, ответило ошибкой либо
                отклонило пакет.
        """
        logger.info(f"Отправка задания на станок: {packet.url[:200]}")
        status = await self._exchange(packet.url)

        # Оборудование отвечает HTTP 200 и на отклонённую команду —
        # настоящий итог лежит только в поле `tasks`.
        if status.command == 2:
            raise MachineError(
                "Оборудование отклонило пакет заданий. "
                "Код ошибки показан бегущей строкой на сенсорной панели станка."
            )
        if status.command != 1:
            title = COMMAND_TITLES.get(status.command, f"поле tasks={status.command}")
            raise MachineError(
                f"Оборудование не подтвердило приём задания ({title}). {status.summary}"
            )

        return status

    async def _exchange(self, url: str, timeout: float = None) -> MachineStatus:
        """Выполняет запрос к оборудованию и разбирает ответ.

        Адрес передаётся уже собранным: фигурные скобки и кавычки формата
        должны уйти как есть, поэтому переэкранирование в yarl отключено.

        Args:
            url: Готовый адрес запроса.
            timeout: Таймаут запроса; None — таймаут шлюза.

        Returns:
            Разобранное состояние оборудования.

        Raises:
            MachineError: Оборудование недоступно или вернуло код ошибки.
        """
        try:
            response = await self._http.get(
                URL(url, encoded=True),
                timeout=timeout or self._timeout,
                as_text=True,
            )
        except ConnectionError as error:
            raise MachineError(
                f"Станок недоступен по адресу {self._base_url}: {error}"
            ) from error

        if not response.is_success:
            raise MachineError(f"Станок ответил HTTP {response.status}")

        status = self._parser.parse(response.as_text)
        logger.info(f"Ответ станка: {status.summary} | сырой: {status.raw[:200]}")
        return status
