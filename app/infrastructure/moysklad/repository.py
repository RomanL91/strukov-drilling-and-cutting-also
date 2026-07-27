"""Репозиторий производственных заданий поверх API МойСклад.

Паттерн «Репозиторий»: слой сценариев работает с заданиями, не зная ни путей
API, ни параметров пагинации. Замена источника данных — это новая реализация
`TaskRepository`, а не правка сценариев.
"""

from typing import Sequence

from app.core.logger import logger
from app.domain.models import ProductPosition, ProductionTask, TaskPage, TaskQuery
from app.infrastructure.moysklad.client import MoySkladClient
from app.infrastructure.moysklad.mapper import ProductionTaskMapper

PRODUCTION_TASK_PATH = "/entity/productiontask"


class MoySkladTaskRepository:
    """Доступ к производственным заданиям МойСклад."""

    def __init__(self, client: MoySkladClient, mapper: ProductionTaskMapper):
        """Создаёт репозиторий.

        Args:
            client: Клиент API МойСклад.
            mapper: Преобразователь ответов в модели.
        """
        self._client = client
        self._mapper = mapper

    async def list_tasks(self, query: TaskQuery) -> TaskPage:
        """Возвращает страницу списка заданий, новые сверху.

        Args:
            query: Параметры выборки — поиск, смещение, размер страницы.

        Returns:
            Страница с заданиями и общим количеством.

        Raises:
            RepositoryError: МойСклад недоступен или отклонил запрос.
        """
        # expand=state нужен, чтобы в списке было название статуса,
        # иначе в ответе приходит только ссылка на него.
        params = {"order": "moment,desc", "expand": "state"}
        if query.search.strip():
            params["search"] = query.search.strip()

        response = await self._client.get_page(
            PRODUCTION_TASK_PATH,
            limit=query.limit,
            offset=query.offset,
            params=params,
        )

        rows = response.get("rows", [])
        total = int((response.get("meta") or {}).get("size", len(rows)))
        logger.info(f"Список заданий: получено {len(rows)} из {total} (offset={query.offset})")

        return TaskPage(
            tasks=[self._mapper.to_task(row) for row in rows],
            total=total,
            offset=query.offset,
        )

    async def load_positions(self, task: ProductionTask) -> Sequence[ProductPosition]:
        """Загружает все позиции задания вместе с атрибутами номенклатуры.

        Args:
            task: Производственное задание.

        Returns:
            Позиции задания; пустой список, если ссылка на позиции отсутствует.

        Raises:
            RepositoryError: МойСклад недоступен или отклонил запрос.
        """
        if not task.positions_ref:
            return []

        rows = await self._client.get_all(
            task.positions_ref,
            params={"expand": "productionRow,assortment"},
        )
        logger.info(f"Задание «{task.name}»: получено позиций {len(rows)}")
        return [self._mapper.to_position(row) for row in rows]

    async def count_tasks(self) -> int:
        """Возвращает общее количество заданий — используется для проверки связи.

        Returns:
            Количество производственных заданий в источнике.

        Raises:
            RepositoryError: МойСклад недоступен или отклонил запрос.
        """
        response = await self._client.get_page(PRODUCTION_TASK_PATH, limit=1, offset=0)
        return int((response.get("meta") or {}).get("size", 0))
