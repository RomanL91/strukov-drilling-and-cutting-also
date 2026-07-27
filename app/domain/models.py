"""Модели предметной области.

Почти все модели — неизменяемые объекты-значения (frozen dataclass): их
безопасно передавать между слоями и сравнивать по содержимому.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from app.domain.profiles import ProfileType


@dataclass(frozen=True)
class ProductionTask:
    """Производственное задание в списке.

    Attributes:
        id: Идентификатор задания в источнике.
        name: Номер или название задания.
        moment: Дата и время задания в исходном текстовом виде.
        state: Название статуса; пустая строка, если статус не загружен.
        description: Комментарий к заданию.
        positions_ref: Ссылка на позиции задания в источнике.
        positions_count: Количество позиций.
    """

    id: str
    name: str
    moment: str
    state: str
    description: str
    positions_ref: str
    positions_count: int

    @property
    def moment_display(self) -> str:
        """Возвращает дату задания в формате «ДД.ММ.ГГГГ ЧЧ:ММ»."""
        if not self.moment:
            return "—"
        for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(self.moment, pattern).strftime("%d.%m.%Y %H:%M")
            except ValueError:
                continue
        return self.moment


@dataclass(frozen=True)
class TaskQuery:
    """Параметры выборки производственных заданий.

    Attributes:
        search: Строка поиска; пустая — без фильтра.
        offset: Смещение от начала списка.
        limit: Размер страницы.
    """

    search: str = ""
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class TaskPage:
    """Страница списка заданий.

    Attributes:
        tasks: Задания текущей страницы.
        total: Общее количество заданий в источнике.
        offset: Смещение, с которого получена страница.
    """

    tasks: Sequence[ProductionTask]
    total: int
    offset: int

    @property
    def first_number(self) -> int:
        """Порядковый номер первого задания на странице (с единицы)."""
        return self.offset + 1 if self.tasks else 0

    @property
    def last_number(self) -> int:
        """Порядковый номер последнего задания на странице."""
        return self.offset + len(self.tasks)

    @property
    def has_previous(self) -> bool:
        """Есть ли предыдущая страница."""
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        """Есть ли следующая страница."""
        return self.last_number < self.total


@dataclass(frozen=True)
class ProductPosition:
    """Позиция производственного задания в нейтральном виде.

    Промежуточное представление между сырым ответом источника и профилями:
    репозиторий отдаёт его, а разбор атрибутов превращает в комплект профилей.

    Attributes:
        name: Название изделия или производственного ряда.
        planned_quantity: Плановое количество изделий.
        attributes: Атрибуты номенклатуры «имя → значение».
    """

    name: str
    planned_quantity: int
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileItem:
    """Один профиль в комплекте изделия.

    Attributes:
        profile_type: Тип профиля из справочника.
        length_mm: Длина профиля в миллиметрах.
        quantity: Количество отрезков на одно изделие.
        drilling_mm: Отступы сверловки в миллиметрах.
    """

    profile_type: ProfileType
    length_mm: int
    quantity: int
    drilling_mm: tuple[int, ...] = ()


@dataclass(frozen=True)
class ProductSet:
    """Комплект профилей на одно изделие.

    Attributes:
        name: Название изделия; уходит на станок в поле `cli`.
        items: Профили, входящие в комплект.
        planned_quantity: Сколько таких изделий запланировано.
    """

    name: str
    items: tuple[ProfileItem, ...]
    planned_quantity: int = 1


@dataclass(frozen=True)
class ExtractionResult:
    """Итог разбора позиций задания.

    Attributes:
        product_sets: Успешно разобранные комплекты.
        warnings: Замечания по позициям, которые разобрать не удалось.
    """

    product_sets: Sequence[ProductSet]
    warnings: Sequence[str]


@dataclass(frozen=True)
class CutRow:
    """Строка сводки — она же один блок пакета для станка.

    Одинаковые профили сведены в одну строку: количество задаётся полем
    `quantity`, поэтому в пакет уходит один блок вместо десятков одинаковых.

    Attributes:
        client: Название изделия для поля `cli`.
        profile_code: Код типа профиля для поля `oc`.
        profile_title: Название типа профиля для интерфейса.
        length_mm: Длина отрезка в миллиметрах.
        quantity: Количество отрезков.
        drilling_mm: Отступы сверловки в миллиметрах.
    """

    client: str
    profile_code: str
    profile_title: str
    length_mm: int
    quantity: int
    drilling_mm: tuple[int, ...] = ()

    @property
    def drilling_display(self) -> str:
        """Возвращает отступы сверловки строкой для таблицы."""
        return ", ".join(map(str, self.drilling_mm)) if self.drilling_mm else "—"

    @property
    def total_length_mm(self) -> int:
        """Возвращает суммарную длину всех отрезков строки."""
        return self.length_mm * self.quantity


@dataclass(frozen=True)
class MachinePacket:
    """Готовый пакет заданий для станка вместе с итогом проверки.

    Attributes:
        url: Адрес запроса целиком.
        block_count: Количество блоков заданий в пакете.
        byte_length: Размер адреса в байтах.
        violations: Нарушения ограничений протокола; непустой список запрещает отправку.
        warnings: Замечания, не мешающие отправке.
    """

    url: str
    block_count: int
    byte_length: int
    violations: Sequence[str] = ()
    warnings: Sequence[str] = ()

    @property
    def can_send(self) -> bool:
        """Можно ли отправлять пакет на станок."""
        return self.block_count > 0 and not self.violations


@dataclass(frozen=True)
class MachineStatus:
    """Состояние оборудования из ответа на запрос.

    Attributes:
        ready: Признак завершения всех заданий (0 или 1).
        state: 0 — базовая точка не найдена, 1 — готово, 2 — в работе.
        tasks_left: Количество незавершённых заданий.
        products_left: Количество невыполненных изделий.
        status_request: Итог обработки команды запроса состояния.
        command: Итог обработки пакета заданий (1 — принят, 2 — отклонён).
        raw: Исходный текст ответа для журнала.
    """

    ready: Optional[int] = None
    state: Optional[int] = None
    tasks_left: Optional[int] = None
    products_left: Optional[int] = None
    status_request: Optional[int] = None
    command: Optional[int] = None
    raw: str = ""

    STATE_TITLES = {
        0: "базовая точка не найдена",
        1: "готово",
        2: "в работе",
    }

    @property
    def is_free(self) -> bool:
        """Свободно ли оборудование для приёма нового задания."""
        return self.state == 1 and self.ready == 1

    @property
    def state_title(self) -> str:
        """Возвращает состояние оборудования словами."""
        if self.state is None:
            return "состояние неизвестно"
        return self.STATE_TITLES.get(self.state, f"неизвестный код {self.state}")

    @property
    def summary(self) -> str:
        """Возвращает краткую сводку состояния для интерфейса."""
        parts = [f"состояние: {self.state_title}"]
        if self.tasks_left is not None:
            parts.append(f"незавершённых заданий: {self.tasks_left}")
        if self.products_left is not None:
            parts.append(f"изделий в очереди: {self.products_left}")
        return ", ".join(parts)


@dataclass(frozen=True)
class Job:
    """Задание, подготовленное к отправке на станок.

    Attributes:
        task: Исходное производственное задание.
        rows: Сводка того, что уйдёт на станок.
        parse_warnings: Замечания разбора атрибутов номенклатуры.
        packet: Собранный пакет и итог проверки по протоколу.
    """

    task: ProductionTask
    rows: Sequence[CutRow]
    parse_warnings: Sequence[str]
    packet: MachinePacket

    @property
    def url(self) -> str:
        """Возвращает адрес пакета."""
        return self.packet.url

    @property
    def violations(self) -> Sequence[str]:
        """Возвращает нарушения протокола, блокирующие отправку."""
        return self.packet.violations

    @property
    def packet_warnings(self) -> Sequence[str]:
        """Возвращает замечания к пакету, не мешающие отправке."""
        return self.packet.warnings

    @property
    def can_send(self) -> bool:
        """Можно ли отправлять задание на станок."""
        return self.packet.can_send

    @property
    def is_empty(self) -> bool:
        """Пусто ли задание — нет ни одного профиля."""
        return not self.rows

    @property
    def total_pieces(self) -> int:
        """Возвращает общее количество отрезков."""
        return sum(row.quantity for row in self.rows)

    @property
    def total_length_m(self) -> float:
        """Возвращает суммарную длину профиля в метрах."""
        return sum(row.total_length_mm for row in self.rows) / 1000
