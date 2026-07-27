"""Пути к пользовательским данным приложения.

В упакованном виде (.exe или .app) каталог программы доступен только на чтение,
поэтому настройки и журнал хранятся в пользовательских директориях ОС.
"""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "StrukovDrilling"


def config_dir() -> Path:
    """Возвращает каталог настроек, создавая его при необходимости.

    Returns:
        Каталог настроек: `%APPDATA%` в Windows, `~/Library/Application Support`
        в macOS, `$XDG_CONFIG_HOME` в остальных системах.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        path = base / APP_DIR_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        path = base / APP_DIR_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    """Возвращает каталог журнала, создавая его при необходимости.

    Returns:
        Каталог журнала: `%LOCALAPPDATA%` в Windows, `~/Library/Logs` в macOS,
        `$XDG_STATE_HOME` в остальных системах.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / APP_DIR_NAME / "logs"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Logs" / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        path = base / APP_DIR_NAME / "logs"

    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    """Возвращает путь к файлу настроек.

    Returns:
        Путь к `config.json` в каталоге настроек.
    """
    return config_dir() / "config.json"
