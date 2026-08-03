"""Сырой HTTP-обмен со станком.

Веб-сервер оборудования (S7-1200) отвечает страницей, длина которой не сходится
с заголовком `Content-Length`: строгий разборщик aiohttp дочитывает тело по
заголовку, а оставшийся хвост `</html>` принимает за начало следующего ответа и
падает с «Bad status line». Браузер такой ответ показывает без нареканий —
здесь повторена его снисходительность: запрос уходит байт в байт как в
документации, ответ читается до конца страницы и разбирается вручную.
"""

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional, Tuple

from app.core.logger import logger
from app.infrastructure.http.retry import RetryPolicy

CHUNK_SIZE = 65536
END_MARKER = b"</html>"
LOG_LIMIT = 400


@dataclass(frozen=True)
class RawResponse:
    """Ответ станка после ручного разбора.

    Attributes:
        status: Код состояния из строки ответа; 200, если строки ответа не было.
        text: Тело ответа текстом.
    """

    status: int
    text: str

    @property
    def is_success(self) -> bool:
        """Успешен ли ответ по коду состояния."""
        return 200 <= self.status < 300


class RawHttpTransport:
    """Обмен со станком по TCP без строгого разбора HTTP.

    Отдельный транспорт нужен только оборудованию: МойСклад отвечает
    правильным HTTP, и там остаётся aiohttp.
    """

    def __init__(self, retry_policy: Optional[RetryPolicy] = None):
        """Создаёт транспорт с заданной политикой повторов.

        Args:
            retry_policy: Политика повторов; по умолчанию — стандартная.
        """
        self._retry_policy = retry_policy or RetryPolicy()

    async def get(self, url: str, timeout: float = 30.0) -> RawResponse:
        """Выполняет GET-запрос, отправляя адрес без переэкранирования.

        Args:
            url: Готовый адрес запроса вместе с фигурными скобками и кавычками.
            timeout: Общий таймаут обмена в секундах.

        Returns:
            Код состояния и тело ответа.

        Raises:
            ConnectionError: Сетевой сбой не удалось преодолеть повторами.
            ValueError: Адрес станка нельзя разобрать.
        """
        host, port, target = split_url(url)

        async def perform() -> RawResponse:
            """Выполняет одну попытку обмена."""
            raw = await self._exchange(host, port, target, timeout)
            logger.info(f"Сырой ответ станка ({len(raw)} байт): {raw[:LOG_LIMIT]!r}")
            return parse_response(raw)

        return await self._retry_policy.run(perform)

    async def _exchange(self, host: str, port: int, target: str, timeout: float) -> bytes:
        """Открывает соединение, шлёт запрос и забирает ответ целиком.

        Args:
            host: Имя или адрес оборудования.
            port: Порт оборудования.
            target: Путь со строкой запроса, как он должен уйти в сеть.
            timeout: Общий таймаут обмена в секундах.

        Returns:
            Ответ оборудования сырыми байтами вместе с заголовками.

        Raises:
            OSError: Соединение не удалось установить или оно оборвалось.
            asyncio.TimeoutError: Оборудование не ответило за отведённое время.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout
        )
        try:
            writer.write(build_request(host, port, target))
            await writer.drain()
            return await read_response(reader, timeout)
        finally:
            writer.close()
            # Станок закрывает соединение сам и не всегда штатно —
            # ошибки закрытия не должны подменять собой результат обмена.
            with suppress(Exception):
                await writer.wait_closed()


def split_url(url: str) -> Tuple[str, int, str]:
    """Разбирает адрес на хост, порт и цель запроса.

    Строка запроса не трогается: `urllib` переэкранировал бы фигурные скобки,
    а оборудование ждёт их как есть.

    Args:
        url: Полный адрес запроса.

    Returns:
        Хост, порт и путь со строкой запроса.

    Raises:
        ValueError: В адресе нет хоста или порт не число.
    """
    rest = url.split("://", 1)[-1]
    authority, separator, path = rest.partition("/")
    target = f"/{path}" if separator else "/"

    if ":" in authority:
        host, _, port_text = authority.rpartition(":")
    else:
        host, port_text = authority, ""
    if not host:
        raise ValueError(f"В адресе «{url}» не указан хост")

    try:
        port = int(port_text) if port_text else 80
    except ValueError as error:
        raise ValueError(f"В адресе «{url}» неверный порт «{port_text}»") from error

    return host, port, target


def build_request(host: str, port: int, target: str) -> bytes:
    """Собирает строку запроса HTTP.

    `Connection: close` просит оборудование закрыть соединение после ответа:
    так остаток страницы не достанется следующему запросу.

    Args:
        host: Имя или адрес оборудования.
        port: Порт оборудования.
        target: Путь со строкой запроса.

    Returns:
        Готовый запрос в байтах.
    """
    lines = [
        f"GET {target} HTTP/1.1",
        f"Host: {host}:{port}",
        "User-Agent: StrukovDrilling",
        "Accept: */*",
        "Connection: close",
        "",
        "",
    ]
    return "\r\n".join(lines).encode("utf-8")


async def read_response(reader: asyncio.StreamReader, timeout: float) -> bytes:
    """Читает ответ до закрытия соединения или до конца страницы.

    Оборудование не всегда закрывает соединение и завышает `Content-Length`,
    поэтому признаком конца служит закрывающий тег страницы.

    Args:
        reader: Поток чтения открытого соединения.
        timeout: Общий таймаут чтения в секундах.

    Returns:
        Полученные байты ответа.

    Raises:
        asyncio.TimeoutError: За отведённое время не пришло ни байта.
        ConnectionError: Оборудование закрыло соединение, не ответив.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    buffer = bytearray()

    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            chunk = await asyncio.wait_for(reader.read(CHUNK_SIZE), remaining)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        buffer.extend(chunk)
        if END_MARKER in buffer:
            break

    if buffer:
        return bytes(buffer)
    if loop.time() >= deadline:
        raise asyncio.TimeoutError()
    raise ConnectionError("оборудование закрыло соединение, не ответив")


def parse_response(raw: bytes) -> RawResponse:
    """Разбирает сырой ответ на код состояния и тело.

    Ответ без заголовков или с оборванными заголовками считается телом
    целиком: разбор состояния всё равно ищет свои поля по всему тексту.

    Args:
        raw: Полученные байты ответа.

    Returns:
        Код состояния и тело ответа.
    """
    head, separator, body = raw.partition(b"\r\n\r\n")
    if not separator:
        head, separator, body = raw.partition(b"\n\n")

    status = parse_status_line(head) if separator else None
    if status is None:
        status, body = 200, raw

    return RawResponse(status, body.decode("utf-8", errors="replace"))


def parse_status_line(head: bytes) -> Optional[int]:
    """Достаёт код состояния из строки ответа.

    Args:
        head: Байты заголовков ответа.

    Returns:
        Код состояния либо None, если строки ответа HTTP там нет.
    """
    first_line = head.split(b"\n", 1)[0].strip()
    if not first_line.upper().startswith(b"HTTP/"):
        return None

    parts = first_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return None

    return int(parts[1])
