"""Иерархия ошибок приложения.

Все тексты пригодны для показа пользователю: интерфейс выводит `str(ошибка)`
как есть, не дополняя её техническими подробностями.
"""


class AppError(Exception):
    """Базовая ошибка приложения с человекочитаемым текстом."""


class ConfigError(AppError):
    """Не хватает настроек для выполнения операции."""


class RepositoryError(AppError):
    """Ошибка источника производственных заданий."""

    def __init__(self, message: str, status: int = 0):
        """Запоминает текст и код ответа источника.

        Args:
            message: Сообщение для пользователя.
            status: Код HTTP-ответа, если он известен.
        """
        super().__init__(message)
        self.status = status


class MachineError(AppError):
    """Ошибка при обращении к станку или отказ оборудования."""


class ProtocolError(MachineError):
    """Пакет не соответствует протоколу и не может быть отправлен."""

    def __init__(self, message: str, violations: list[str] | None = None):
        """Запоминает текст и перечень нарушений протокола.

        Args:
            message: Общее сообщение для пользователя.
            violations: Список конкретных нарушений ограничений протокола.
        """
        super().__init__(message)
        self.violations = violations or []
