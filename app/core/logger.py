"""Настройка журналирования приложения.

Журнал пишется в консоль и в файл с суточной ротацией. Путь к файлу берётся из
`app.core.paths`, потому что каталог программы в упакованном виде недоступен
для записи.
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import List

from app.core.paths import log_dir

FORMAT = "%(asctime)s | %(levelname)-8s | %(module)s.%(funcName)s:%(lineno)d | %(message)s"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Настраивает корневой журнал: консоль и суточная ротация в файл.

    Повторные вызовы игнорируются, поэтому импорт модуля из разных мест не
    приводит к дублированию обработчиков.

    Args:
        level: Минимальный уровень записей.
    """
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(FORMAT)
    handlers: List[logging.Handler] = []

    # В упакованном оконном приложении стандартный вывод может отсутствовать.
    if sys.stderr is not None:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    try:
        file_handler = TimedRotatingFileHandler(
            log_dir() / "app.log",
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except OSError:
        # Без файла журнала приложение всё равно должно запускаться.
        pass

    root = logging.getLogger()
    root.setLevel(level)
    for handler in handlers:
        root.addHandler(handler)

    _configured = True


setup_logging()

logger = logging.getLogger("strukov")
