"""Чтение `.env` — только для первичного заполнения настроек.

Раньше здесь создавался глобальный объект настроек, который падал на импорте,
если переменных нет. Для оконного приложения это неприемлемо: оно должно
запускаться и предлагать ввести логин и пароль. Поэтому обращение к `.env`
необязательно и не бросает исключений.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """Учётные данные МойСклад из `.env` или переменных окружения.

    Attributes:
        MS_LOGIN: Логин пользователя МойСклад.
        MS_PASSWORD: Пароль пользователя МойСклад.
    """

    MS_LOGIN: Optional[str] = Field(default=None)
    MS_PASSWORD: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def read_env_settings() -> EnvSettings:
    """Читает `.env` и переменные окружения.

    Returns:
        Настройки из окружения; при любой ошибке — пустые значения.
    """
    try:
        return EnvSettings()
    except Exception:  # noqa: BLE001 — .env необязателен, приложение работает без него
        return EnvSettings.model_construct(MS_LOGIN=None, MS_PASSWORD=None)
