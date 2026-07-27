"""Ограничения и кодирование протокола iPAP2.

Модуль разделён на три роли:
    `ProtocolLimits` — числовые ограничения из документации;
    `ValueEncoder` — кодирование строковых значений по приложению А;
    `PacketValidator` — проверка блока и пакета целиком.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from app.domain.models import CutRow


@dataclass(frozen=True)
class ProtocolLimits:
    """Числовые ограничения протокола.

    Attributes:
        max_blocks: Сколько заданий принимается в одном пакете.
        max_packet_bytes: Предельный размер TCP-пакета.
        http_overhead_bytes: Запас под строку запроса и заголовки HTTP.
        max_size_mm: Предельная длина отрезка (4 цифры).
        max_quantity: Предельное количество отрезков (3 цифры).
        max_order_code: Предельная длина кода заказа `oc`.
        max_client: Предельная длина имени клиента `cli`.
        max_drill_points: Сколько отступов сверловки принимает оборудование.
    """

    max_blocks: int = 100
    max_packet_bytes: int = 2953
    http_overhead_bytes: int = 250
    max_size_mm: int = 9999
    max_quantity: int = 999
    max_order_code: int = 8
    max_client: int = 12
    max_drill_points: int = 2

    @property
    def max_url_bytes(self) -> int:
        """Возвращает бюджет байтов на сам адрес запроса.

        Оборудование ограничивает TCP-пакет целиком, а aiohttp добавляет к
        адресу строку запроса и заголовки, поэтому оставляем запас.
        """
        return self.max_packet_bytes - self.http_overhead_bytes


class ValueEncoder:
    """Кодировщик строковых значений `oc` и `cli` по приложению А.

    Оборудование понимает URL-кодирование лишь для перечисленных в документации
    символов: `#`, `%`, `'`, `*`, `^`, пробел и кириллица. Всё прочее за
    пределами печатного ASCII отбрасывается — иначе панель выдаёт ошибку 67/77
    «URL неподдерживаемого символа».
    """

    ESCAPES = {
        "#": "%23",
        "%": "%25",
        "'": "%27",
        "‘": "%27",
        "’": "%27",
        "*": "%2A",
        "^": "%5E",
        " ": "%20",
    }

    def encode(self, text: str) -> Tuple[str, List[str]]:
        """Кодирует значение для строки запроса.

        Args:
            text: Исходное значение поля `oc` или `cli`.

        Returns:
            Закодированное значение и замечания об отброшенных символах.
        """
        encoded: List[str] = []
        dropped: List[str] = []

        for char in text:
            if char in self.ESCAPES:
                encoded.append(self.ESCAPES[char])
            elif self._is_cyrillic(char):
                encoded.extend(f"%{byte:02X}" for byte in char.encode("utf-8"))
            elif 32 < ord(char) < 127 and char != '"':
                encoded.append(char)
            else:
                dropped.append(char)

        warnings: List[str] = []
        if dropped:
            unique = "".join(dict.fromkeys(dropped))
            warnings.append(f"в «{text}» отброшены неподдерживаемые символы: {unique}")

        return "".join(encoded), warnings

    @staticmethod
    def _is_cyrillic(char: str) -> bool:
        """Проверяет, что символ — кириллическая буква из таблицы приложения А.

        Args:
            char: Проверяемый символ.

        Returns:
            True, если символ кодируется как кириллица.
        """
        return "а" <= char.lower() <= "я" or char in ("ё", "Ё")


class PacketValidator:
    """Проверка блоков и пакета на соответствие ограничениям протокола."""

    def __init__(self, limits: ProtocolLimits):
        """Создаёт валидатор с заданными ограничениями.

        Args:
            limits: Ограничения протокола.
        """
        self._limits = limits

    def check_row(self, row: CutRow) -> List[str]:
        """Проверяет одну строку сводки.

        Args:
            row: Строка сводки, соответствующая одному блоку пакета.

        Returns:
            Перечень нарушений; пустой список — нарушений нет.
        """
        label = f"«{row.client}» {row.profile_code} {row.length_mm} мм"
        violations: List[str] = []

        if not 0 < row.length_mm <= self._limits.max_size_mm:
            violations.append(
                f"{label}: длина {row.length_mm} вне диапазона 1…{self._limits.max_size_mm} мм"
            )
        if not 0 < row.quantity <= self._limits.max_quantity:
            violations.append(
                f"{label}: количество {row.quantity} вне диапазона 1…{self._limits.max_quantity}"
            )
        if len(row.profile_code) > self._limits.max_order_code:
            violations.append(
                f"{label}: код заказа «{row.profile_code}» длиннее "
                f"{self._limits.max_order_code} символов"
            )
        if len(row.client) > self._limits.max_client:
            violations.append(
                f"{label}: имя клиента «{row.client}» длиннее "
                f"{self._limits.max_client} символов"
            )
        if len(row.drilling_mm) > self._limits.max_drill_points:
            violations.append(
                f"{label}: {len(row.drilling_mm)} отступов сверловки, оборудование "
                f"принимает до {self._limits.max_drill_points}"
            )
        if any(not 0 < point <= self._limits.max_size_mm for point in row.drilling_mm):
            violations.append(
                f"{label}: отступ сверловки вне диапазона 1…{self._limits.max_size_mm} мм"
            )

        return violations

    def check_packet(self, block_count: int, byte_length: int) -> List[str]:
        """Проверяет пакет целиком.

        Args:
            block_count: Количество блоков в пакете.
            byte_length: Размер адреса запроса в байтах.

        Returns:
            Перечень нарушений; пустой список — нарушений нет.
        """
        violations: List[str] = []

        if block_count > self._limits.max_blocks:
            violations.append(
                f"Заданий в пакете {block_count}, оборудование принимает "
                f"не более {self._limits.max_blocks}"
            )
        if byte_length > self._limits.max_url_bytes:
            violations.append(
                f"Пакет {byte_length} байт при лимите TCP-пакета "
                f"{self._limits.max_packet_bytes} байт (с учётом заголовков HTTP "
                f"под адрес остаётся ~{self._limits.max_url_bytes})"
            )

        return violations


def status_request_url(base_url: str) -> str:
    """Собирает адрес команды запроса состояния.

    Args:
        base_url: Базовый адрес оборудования.

    Returns:
        Адрес вида `http://хост:порт/?{status_request:1}`.
    """
    return f"{base_url.rstrip('/')}/?{{status_request:1}}"
