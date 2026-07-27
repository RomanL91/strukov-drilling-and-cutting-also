"""Справочник типов профилей.

Тип профиля описывает, из каких атрибутов номенклатуры МойСклад берутся длина,
количество и точки сверления. Справочник вынесен в данные, поэтому добавление
нового типа не требует правки кода разбора (принцип открытости/закрытости).
"""

from dataclasses import dataclass
from typing import Iterator, Optional, Sequence


@dataclass(frozen=True)
class ProfileType:
    """Тип профиля и привязка к атрибутам номенклатуры.

    Attributes:
        code: Код, который уходит на станок в поле `oc` (Osnov, Per, Otrag).
        title: Название для интерфейса.
        length_attribute: Имя атрибута с длиной профиля в миллиметрах.
        quantity_attribute: Имя атрибута с количеством; None — всегда 1 шт.
        drilling_attribute: Имя атрибута с точками сверления; None — без сверления.
    """

    code: str
    title: str
    length_attribute: str
    quantity_attribute: Optional[str] = None
    drilling_attribute: Optional[str] = None


class ProfileCatalog:
    """Набор типов профилей, известных приложению.

    Играет роль справочника: разбор атрибутов и интерфейс обращаются к нему,
    а не к жёстко зашитым строкам.
    """

    def __init__(self, profile_types: Sequence[ProfileType]):
        """Создаёт справочник из перечня типов.

        Args:
            profile_types: Типы профилей в порядке обработки.
        """
        self._types: tuple[ProfileType, ...] = tuple(profile_types)
        self._by_code = {item.code: item for item in self._types}

    def __iter__(self) -> Iterator[ProfileType]:
        """Перебирает типы профилей в заданном порядке."""
        return iter(self._types)

    def __len__(self) -> int:
        """Возвращает количество типов в справочнике."""
        return len(self._types)

    def by_code(self, code: str) -> Optional[ProfileType]:
        """Находит тип профиля по коду.

        Args:
            code: Код типа, например «Osnov».

        Returns:
            Тип профиля или None, если код неизвестен.
        """
        return self._by_code.get(code)

    def title_of(self, code: str) -> str:
        """Возвращает название типа для интерфейса.

        Args:
            code: Код типа профиля.

        Returns:
            Название типа либо сам код, если тип неизвестен.
        """
        profile_type = self._by_code.get(code)
        return profile_type.title if profile_type else code

    @classmethod
    def default(cls) -> "ProfileCatalog":
        """Создаёт справочник с типами, заведёнными в МойСклад заказчика.

        Имена атрибутов сверены со справочником доп.полей товара в МойСклад.
        """
        return cls(
            [
                ProfileType(
                    code="Osnov",
                    title="Основной",
                    length_attribute='Длина профиля "Основной"',
                    quantity_attribute='Кол-во "Основного"',
                    drilling_attribute="Сверление",
                ),
                ProfileType(
                    code="Per",
                    title="Перемычка",
                    length_attribute='Длина профиля "Перемычка"',
                    quantity_attribute='Кол-во "Перемычек"',
                ),
                ProfileType(
                    code="Otrag",
                    title="Отражатель",
                    length_attribute='Длина профиля "Отрожатель"',
                ),
            ]
        )
