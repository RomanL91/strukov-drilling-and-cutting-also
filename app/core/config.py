"""Настройки приложения, редактируемые из интерфейса.

Хранятся в JSON в пользовательской директории (см. `app.core.paths`). При
первом запуске заполняются из `.env`, если он лежит рядом с проектом.
"""

import json
import os
import sys
from typing import Optional

from pydantic import BaseModel, Field

from app.core.paths import config_file
from app.core.settings import read_env_settings

MS_DEFAULT_BASE_URL = "https://api.moysklad.ru/api/remap/1.2"


class AppConfig(BaseModel):
    """Настройки приложения.

    Attributes:
        ms_login: Логин пользователя МойСклад.
        ms_password: Пароль пользователя МойСклад.
        ms_base_url: Базовый адрес API МойСклад.
        machine_host: IP или имя хоста станка.
        machine_port: Порт, на котором станок принимает команды.
        request_timeout: Таймаут сетевого запроса в секундах.
        page_size: Количество заданий на странице списка.
    """

    ms_login: str = ""
    ms_password: str = ""
    ms_base_url: str = MS_DEFAULT_BASE_URL

    machine_host: str = "192.168.0.100"
    machine_port: int = 8080

    request_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    page_size: int = Field(default=50, ge=10, le=100)

    @property
    def machine_base_url(self) -> str:
        """Возвращает базовый адрес станка."""
        return f"http://{self.machine_host}:{self.machine_port}"

    @property
    def is_ms_configured(self) -> bool:
        """Заданы ли учётные данные МойСклад."""
        return bool(self.ms_login and self.ms_password)

    @property
    def is_machine_configured(self) -> bool:
        """Задан ли адрес станка."""
        return bool(self.machine_host)


def _seed_from_env() -> AppConfig:
    """Создаёт настройки по умолчанию, подставив учётные данные из `.env`.

    Returns:
        Настройки с логином и паролем из окружения, если они там есть.
    """
    env = read_env_settings()
    return AppConfig(
        ms_login=env.MS_LOGIN or "",
        ms_password=env.MS_PASSWORD or "",
    )


def load_config() -> AppConfig:
    """Читает настройки с диска.

    При отсутствии файла создаёт его, заполнив значениями из `.env`. Битый файл
    не должен мешать запуску, поэтому подменяется значениями по умолчанию.

    Returns:
        Текущие настройки приложения.
    """
    path = config_file()
    if not path.exists():
        config = _seed_from_env()
        save_config(config)
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(raw)
    except Exception:  # noqa: BLE001 — битый файл не должен ронять запуск
        return _seed_from_env()


def save_config(config: AppConfig) -> None:
    """Атомарно записывает настройки на диск.

    Args:
        config: Настройки для сохранения.
    """
    path = config_file()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)

    # Пароль лежит в открытом виде — на POSIX хотя бы закрываем файл от чужих.
    if sys.platform != "win32":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Возвращает настройки, читая их с диска при первом обращении.

    Returns:
        Текущие настройки приложения.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: AppConfig) -> AppConfig:
    """Сохраняет настройки и делает их текущими.

    Args:
        config: Новые настройки.

    Returns:
        Сохранённые настройки.
    """
    global _config
    save_config(config)
    _config = config
    return _config
