"""Сборка задания для станка из производственного задания источника."""

from typing import Dict, List, Sequence, Tuple

from app.core.logger import logger
from app.domain.interfaces import PacketBuilder, ProfileExtractor, TaskRepository
from app.domain.models import CutRow, Job, ProductSet, ProductionTask


class JobAssembler:
    """Координатор сборки: загрузка → разбор → сведение → пакет.

    Зависит только от интерфейсов, поэтому в тестах на его место можно
    подставить репозиторий и сборщик пакета без сети.
    """

    def __init__(
        self,
        repository: TaskRepository,
        extractor: ProfileExtractor,
        packet_builder: PacketBuilder,
    ):
        """Создаёт сборщик заданий.

        Args:
            repository: Источник производственных заданий.
            extractor: Разборщик атрибутов в комплекты профилей.
            packet_builder: Сборщик пакета для оборудования.
        """
        self._repository = repository
        self._extractor = extractor
        self._packet_builder = packet_builder

    async def assemble(self, task: ProductionTask) -> Job:
        """Собирает готовое задание.

        Args:
            task: Производственное задание.

        Returns:
            Задание со сводкой, замечаниями разбора и пакетом для станка.

        Raises:
            RepositoryError: Не удалось загрузить позиции задания.
        """
        positions = await self._repository.load_positions(task)
        extraction = self._extractor.extract(positions)
        rows = self.summarize(extraction.product_sets)
        packet = self._packet_builder.build(rows)

        logger.info(
            f"Задание «{task.name}»: блоков {packet.block_count}, "
            f"{packet.byte_length} байт, нарушений {len(packet.violations)}"
        )
        return Job(
            task=task,
            rows=rows,
            parse_warnings=extraction.warnings,
            packet=packet,
        )

    @staticmethod
    def summarize(product_sets: Sequence[ProductSet]) -> List[CutRow]:
        """Сводит комплекты в строки сводки, схлопывая одинаковые профили.

        Комплект повторяется по плановому количеству изделий, поэтому без
        сведения в пакет ушли бы десятки одинаковых блоков. Протокол
        ограничивает пакет сотней заданий и 2953 байтами, а количество и так
        задаётся полем `n` — поэтому одинаковые профили складываются.

        Args:
            product_sets: Разобранные комплекты профилей.

        Returns:
            Строки сводки, отсортированные по изделию, типу профиля и длине.
        """
        totals: Dict[Tuple, int] = {}
        samples: Dict[Tuple, CutRow] = {}

        for product_set in product_sets:
            for item in product_set.items:
                key = (
                    product_set.name,
                    item.profile_type.code,
                    item.length_mm,
                    item.drilling_mm,
                )
                totals[key] = totals.get(key, 0) + item.quantity * product_set.planned_quantity
                if key not in samples:
                    samples[key] = CutRow(
                        client=product_set.name,
                        profile_code=item.profile_type.code,
                        profile_title=item.profile_type.title,
                        length_mm=item.length_mm,
                        quantity=0,
                        drilling_mm=item.drilling_mm,
                    )

        rows = [
            CutRow(
                client=sample.client,
                profile_code=sample.profile_code,
                profile_title=sample.profile_title,
                length_mm=sample.length_mm,
                quantity=totals[key],
                drilling_mm=sample.drilling_mm,
            )
            for key, sample in samples.items()
        ]
        return sorted(rows, key=lambda row: (row.client, row.profile_code, row.length_mm))
