"""Сборка пакета заданий для станка.

Паттерн «Строитель»: сборщик получает строки сводки и выдаёт готовый пакет,
пряча самодельный формат строки запроса. Кодирование и проверку он делегирует
`ValueEncoder` и `PacketValidator`, а сам отвечает только за склейку.
"""

from typing import List, Sequence

from app.domain.models import CutRow, MachinePacket
from app.infrastructure.machine.protocol import (
    PacketValidator,
    ProtocolLimits,
    ValueEncoder,
)


class AlsoPacketBuilder:
    """Сборщик пакета заданий в формате iPAP2."""

    def __init__(
        self,
        base_url: str,
        limits: ProtocolLimits,
        encoder: ValueEncoder,
        validator: PacketValidator,
    ):
        """Создаёт сборщик для конкретного адреса оборудования.

        Args:
            base_url: Базовый адрес станка.
            limits: Ограничения протокола.
            encoder: Кодировщик строковых значений.
            validator: Валидатор блоков и пакета.
        """
        self._base_url = base_url.rstrip("/")
        self._limits = limits
        self._encoder = encoder
        self._validator = validator

    def build(self, rows: Sequence[CutRow]) -> MachinePacket:
        """Собирает пакет и проверяет его по ограничениям протокола.

        Args:
            rows: Строки сводки — по одной на блок пакета.

        Returns:
            Пакет с адресом запроса, нарушениями и замечаниями.
        """
        blocks: List[str] = []
        violations: List[str] = []
        warnings: List[str] = []

        for row in rows:
            violations.extend(self._validator.check_row(row))
            block, block_warnings = self._build_block(row)
            warnings.extend(block_warnings)
            blocks.append(block)

        url = f"{self._base_url}/?{{tasks:[{','.join(blocks)}]}}"
        byte_length = len(url.encode("utf-8"))
        violations.extend(self._validator.check_packet(len(blocks), byte_length))

        return MachinePacket(
            url=url,
            block_count=len(blocks),
            byte_length=byte_length,
            violations=violations,
            warnings=warnings,
        )

    def _build_block(self, row: CutRow) -> tuple[str, List[str]]:
        """Собирает один блок задания.

        Args:
            row: Строка сводки.

        Returns:
            Текст блока и замечания кодировщика.
        """
        label = f"«{row.client}» {row.profile_code} {row.length_mm} мм"
        order_code, order_warnings = self._encoder.encode(row.profile_code)
        client, client_warnings = self._encoder.encode(row.client)

        parts = [f"s:{row.length_mm}", f"n:{row.quantity}"]
        if row.drilling_mm:
            parts.append(f"d:[{','.join(map(str, row.drilling_mm))}]")
        parts.append(f'oc:"{order_code}"')
        parts.append(f'cli:"{client}"')

        warnings = [f"{label}: {text}" for text in order_warnings + client_warnings]
        return "{" + ",".join(parts) + "}", warnings
