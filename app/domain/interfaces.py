"""Интерфейсы, от которых зависит слой сценариев.

Описаны через `typing.Protocol`: реализациям не нужно наследоваться, достаточно
совпадения сигнатур. Интерфейсы намеренно узкие — по две-три операции, чтобы
реализация не была обязана поддерживать лишнее (принцип разделения интерфейсов).
"""

from typing import Protocol, Sequence, runtime_checkable

from app.domain.models import (
    CutRow,
    ExtractionResult,
    Job,
    MachinePacket,
    MachineStatus,
    ProductPosition,
    ProductionTask,
    TaskPage,
    TaskQuery,
)


@runtime_checkable
class TaskRepository(Protocol):
    """Источник производственных заданий."""

    async def list_tasks(self, query: TaskQuery) -> TaskPage:
        """Возвращает страницу списка заданий.

        Args:
            query: Параметры выборки — поиск, смещение, размер страницы.

        Returns:
            Страница с заданиями и общим количеством.

        Raises:
            RepositoryError: Источник недоступен или отклонил запрос.
        """
        ...

    async def load_positions(self, task: ProductionTask) -> Sequence[ProductPosition]:
        """Загружает все позиции задания.

        Args:
            task: Задание, позиции которого нужно получить.

        Returns:
            Позиции задания с атрибутами номенклатуры.

        Raises:
            RepositoryError: Источник недоступен или отклонил запрос.
        """
        ...

    async def count_tasks(self) -> int:
        """Возвращает общее количество заданий — для проверки связи.

        Returns:
            Количество производственных заданий в источнике.

        Raises:
            RepositoryError: Источник недоступен или отклонил запрос.
        """
        ...


@runtime_checkable
class ProfileExtractor(Protocol):
    """Преобразователь позиций задания в комплекты профилей."""

    def extract(self, positions: Sequence[ProductPosition]) -> ExtractionResult:
        """Разбирает атрибуты позиций в комплекты профилей.

        Args:
            positions: Позиции производственного задания.

        Returns:
            Комплекты профилей и замечания по неразобранным позициям.
        """
        ...


@runtime_checkable
class PacketBuilder(Protocol):
    """Сборщик пакета заданий для оборудования."""

    def build(self, rows: Sequence[CutRow]) -> MachinePacket:
        """Собирает пакет и проверяет его по ограничениям протокола.

        Args:
            rows: Строки сводки — по одной на блок пакета.

        Returns:
            Пакет с адресом запроса и перечнем нарушений.
        """
        ...


@runtime_checkable
class MachineGateway(Protocol):
    """Шлюз к оборудованию."""

    async def read_status(self) -> MachineStatus:
        """Запрашивает текущее состояние оборудования.

        Returns:
            Разобранное состояние оборудования.

        Raises:
            MachineError: Оборудование недоступно или ответило ошибкой.
        """
        ...

    async def send(self, packet: MachinePacket) -> MachineStatus:
        """Отправляет пакет заданий на оборудование.

        Args:
            packet: Проверенный пакет заданий.

        Returns:
            Состояние оборудования после приёма пакета.

        Raises:
            MachineError: Оборудование недоступно, занято или отклонило пакет.
        """
        ...


@runtime_checkable
class JobAssembly(Protocol):
    """Сборщик готового задания из производственного задания источника."""

    async def assemble(self, task: ProductionTask) -> Job:
        """Загружает позиции, разбирает их и собирает пакет.

        Args:
            task: Производственное задание.

        Returns:
            Готовое задание со сводкой и пакетом.
        """
        ...
