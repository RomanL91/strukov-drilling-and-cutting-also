"""Разбор атрибутов номенклатуры в комплекты профилей.

Реализация доменного интерфейса `ProfileExtractor`. Правила разбора вынесены из
репозитория: репозиторий отвечает за загрузку, разбор — за смысл значений.
"""

from typing import Any, List, Optional, Sequence, Tuple

from app.core.logger import logger
from app.domain.models import ExtractionResult, ProductPosition, ProductSet, ProfileItem
from app.domain.profiles import ProfileCatalog, ProfileType


class AttributeProfileExtractor:
    """Превращает атрибуты номенклатуры в комплекты профилей.

    Значения в МойСклад заведены строками и заполняются вручную, поэтому разбор
    терпим к формату: принимает «800,0», дробные числа и лишние пробелы, а всё
    непонятное превращает в замечание, а не в исключение.
    """

    def __init__(self, catalog: ProfileCatalog):
        """Создаёт разборщик поверх справочника типов профилей.

        Args:
            catalog: Справочник типов профилей.
        """
        self._catalog = catalog

    def extract(self, positions: Sequence[ProductPosition]) -> ExtractionResult:
        """Разбирает позиции задания в комплекты профилей.

        Args:
            positions: Позиции производственного задания.

        Returns:
            Комплекты профилей и замечания по неразобранным позициям.
        """
        product_sets: List[ProductSet] = []
        warnings: List[str] = []

        for position in positions:
            if not position.attributes:
                warnings.append(
                    f"«{position.name}»: у номенклатуры нет атрибутов — позиция пропущена"
                )
                continue

            items, item_warnings = self._extract_items(position)
            warnings.extend(f"«{position.name}»: {text}" for text in item_warnings)

            if not items:
                warnings.append(
                    f"«{position.name}»: не найдено ни одной длины профиля — позиция пропущена"
                )
                continue

            quantity = position.planned_quantity
            if quantity < 1:
                warnings.append(
                    f"«{position.name}»: плановое количество {quantity} — взята 1 шт."
                )
                quantity = 1

            product_sets.append(
                ProductSet(name=position.name, items=tuple(items), planned_quantity=quantity)
            )

        logger.info(
            f"Разобрано комплектов: {len(product_sets)}, замечаний: {len(warnings)}"
        )
        return ExtractionResult(product_sets=product_sets, warnings=warnings)

    def _extract_items(
        self, position: ProductPosition
    ) -> Tuple[List[ProfileItem], List[str]]:
        """Собирает профили одной позиции по справочнику типов.

        Args:
            position: Позиция задания.

        Returns:
            Список профилей и замечания по этой позиции.
        """
        items: List[ProfileItem] = []
        warnings: List[str] = []

        for profile_type in self._catalog:
            raw_length = position.attributes.get(profile_type.length_attribute)
            if raw_length in (None, ""):
                continue

            length = self._to_int(raw_length)
            if length is None or length <= 0:
                warnings.append(
                    f"{profile_type.title}: длина «{raw_length}» не распознана — профиль пропущен"
                )
                continue

            quantity, quantity_warning = self._read_quantity(position, profile_type)
            if quantity_warning:
                warnings.append(f"{profile_type.title}: {quantity_warning}")

            drilling, drilling_warning = self._read_drilling(position, profile_type)
            if drilling_warning:
                warnings.append(f"{profile_type.title}: {drilling_warning}")

            items.append(
                ProfileItem(
                    profile_type=profile_type,
                    length_mm=length,
                    quantity=quantity,
                    drilling_mm=drilling,
                )
            )

        return items, warnings

    def _read_quantity(
        self, position: ProductPosition, profile_type: ProfileType
    ) -> Tuple[int, Optional[str]]:
        """Читает количество отрезков профиля.

        Args:
            position: Позиция задания.
            profile_type: Тип профиля.

        Returns:
            Количество и замечание, если значение пришлось заменить.
        """
        if not profile_type.quantity_attribute:
            return 1, None

        raw = position.attributes.get(profile_type.quantity_attribute)
        if raw in (None, ""):
            return 1, None

        value = self._to_int(raw)
        if value is None or value < 1:
            return 1, f"количество «{raw}» не распознано — взята 1 шт."
        return value, None

    def _read_drilling(
        self, position: ProductPosition, profile_type: ProfileType
    ) -> Tuple[Tuple[int, ...], Optional[str]]:
        """Читает отступы сверловки вида «100, 250».

        Args:
            position: Позиция задания.
            profile_type: Тип профиля.

        Returns:
            Отступы сверловки и замечание по нераспознанным значениям.
        """
        if not profile_type.drilling_attribute:
            return (), None

        raw = position.attributes.get(profile_type.drilling_attribute)
        if raw in (None, ""):
            return (), None

        points: List[int] = []
        unparsed: List[str] = []
        for chunk in str(raw).replace(";", ",").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            value = self._to_int(chunk)
            if value is None:
                unparsed.append(chunk)
            else:
                points.append(value)

        warning = (
            f"не распознаны точки сверления: {', '.join(unparsed)}" if unparsed else None
        )
        return tuple(points), warning

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        """Приводит значение к целому числу, прощая формат записи.

        Args:
            value: Значение атрибута.

        Returns:
            Целое число либо None, если распознать не удалось.
        """
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        try:
            return int(float(str(value).strip().replace(",", ".")))
        except (TypeError, ValueError):
            return None
