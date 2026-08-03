"""Проверка связи со станком из командной строки.

Запускается там, где стоит оборудование, и печатает сырой ответ целиком —
этого хватает, чтобы отличить «станок не отвечает» от «ответ не разобрался».

Примеры:
    poetry run python -m app.tools.probe_machine
    poetry run python -m app.tools.probe_machine http://192.168.0.100:8080
"""

import asyncio
import sys

from app.infrastructure.machine.protocol import status_request_url
from app.infrastructure.machine.status import MachineStatusParser
from app.infrastructure.machine.transport import (
    build_request,
    parse_response,
    read_response,
    split_url,
)

DEFAULT_BASE_URL = "http://192.168.0.100:8080"


async def probe(url: str, timeout: float = 10.0) -> int:
    """Шлёт запрос на станок и печатает ответ как есть.

    Args:
        url: Полный адрес запроса.
        timeout: Таймаут обмена в секундах.

    Returns:
        Код возврата процесса: 0 — ответ разобран, 1 — обмен не удался.
    """
    host, port, target = split_url(url)
    print(f"Запрос: GET {target}")
    print(f"Адрес:  {host}:{port}\n")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout
        )
    except (OSError, asyncio.TimeoutError) as error:
        print(f"Соединение не установлено: {error!r}")
        return 1

    try:
        writer.write(build_request(host, port, target))
        await writer.drain()
        raw = await read_response(reader, timeout)
    except (OSError, asyncio.TimeoutError) as error:
        print(f"Ответа нет: {error!r}")
        return 1
    finally:
        writer.close()

    print(f"Сырой ответ ({len(raw)} байт):")
    print("-" * 60)
    print(raw.decode("utf-8", errors="replace"))
    print("-" * 60)

    response = parse_response(raw)
    status = MachineStatusParser().parse(response.text)
    print(f"\nHTTP {response.status}")
    print(f"Разбор: {status.summary}")
    print(f"Поля: ready={status.ready}, state={status.state}, "
          f"status_request={status.status_request}, tasks={status.command}")
    return 0


def main() -> int:
    """Разбирает аргументы и запускает проверку.

    Returns:
        Код возврата процесса.
    """
    argument = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    # Полный адрес с командой передаётся как есть, базовый — дополняется
    # запросом состояния.
    url = argument if "?" in argument else status_request_url(argument)
    return asyncio.run(probe(url))


if __name__ == "__main__":
    raise SystemExit(main())
