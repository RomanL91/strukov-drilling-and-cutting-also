"""Отображение ответов МойСклад в модели предметной области.

Паттерн «Преобразователь данных»: знание о структуре JSON собрано в одном
месте, поэтому изменение формата ответа не расходится по всему приложению.
"""

from typing import Any, Dict, Mapping, Optional

from app.domain.models import ProductPosition, ProductionTask


class ProductionTaskMapper:
    """Преобразует строки ответа МойСклад в модели заданий и позиций."""

    def to_task(self, row: Mapping[str, Any]) -> ProductionTask:
        """Строит производственное задание из строки списка.

        Args:
            row: Элемент массива `rows` ответа `/entity/productiontask`.

        Returns:
            Модель производственного задания.
        """
        positions = row.get("products") or {}
        meta = positions.get("meta") or {}
        state = row.get("state") or {}

        return ProductionTask(
            id=row.get("id", ""),
            name=row.get("name") or "Без номера",
            moment=row.get("moment") or "",
            # Без expand=state в ответе только ссылка, названия статуса там нет.
            state=state.get("name") or "",
            description=row.get("description") or "",
            positions_ref=meta.get("href", ""),
            positions_count=int(meta.get("size") or 0),
        )

    def to_position(self, row: Mapping[str, Any]) -> ProductPosition:
        """Строит позицию задания из строки ответа.

        Args:
            row: Элемент массива `rows` ресурса позиций задания.

        Returns:
            Позиция с плоским словарём атрибутов номенклатуры.
        """
        assortment = row.get("assortment") or {}
        return ProductPosition(
            name=self._position_name(row, assortment),
            planned_quantity=self._to_int(row.get("planQuantity"), default=1),
            attributes=self._flatten_attributes(assortment.get("attributes")),
        )

    @staticmethod
    def _position_name(row: Mapping[str, Any], assortment: Mapping[str, Any]) -> str:
        """Выбирает название позиции: сначала ряд, затем номенклатуру.

        Args:
            row: Строка ответа.
            assortment: Блок номенклатуры из строки.

        Returns:
            Название позиции для поля `cli`.
        """
        production_row = row.get("productionRow") or {}
        return production_row.get("name") or assortment.get("name") or "Без названия"

    @staticmethod
    def _flatten_attributes(attributes: Any) -> Dict[str, Any]:
        """Сводит массив атрибутов к словарю «имя → значение».

        Args:
            attributes: Массив атрибутов номенклатуры либо None.

        Returns:
            Словарь атрибутов; пустой, если атрибутов нет.
        """
        if not isinstance(attributes, list):
            return {}
        return {
            item.get("name"): item.get("value")
            for item in attributes
            if isinstance(item, dict) and item.get("name")
        }

    @staticmethod
    def _to_int(value: Any, default: Optional[int] = None) -> int:
        """Приводит значение к целому числу.

        Args:
            value: Исходное значение из ответа.
            default: Значение, если привести не удалось.

        Returns:
            Целое число либо значение по умолчанию.
        """
        try:
            return int(float(str(value).strip().replace(",", ".")))
        except (TypeError, ValueError):
            return default if default is not None else 0
