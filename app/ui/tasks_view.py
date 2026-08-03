"""Экран со списком производственных заданий."""

from typing import Callable, List, Optional, Sequence

import flet as ft

from app.application.production_service import ProductionService
from app.domain.models import ProductionTask, TaskPage, TaskQuery
from app.ui.base_view import BaseView
from app.ui.common import caption, info_notice, title


class TasksView(BaseView):
    """Список заданий с поиском и постраничной навигацией."""

    def __init__(
        self,
        page: ft.Page,
        service_factory: Callable[[], ProductionService],
        on_open_task: Callable[[ProductionTask], None],
    ):
        """Создаёт экран списка заданий.

        Args:
            page: Страница Flet.
            service_factory: Поставщик фасада с текущими настройками.
            on_open_task: Обработчик открытия задания.
        """
        super().__init__(page)
        self._service_factory = service_factory
        self._on_open_task = on_open_task

        self._offset = 0
        self._page_size = 50
        self._search = ""
        self._current: Optional[TaskPage] = None
        self.loaded = False

        self.search_field = ft.TextField(
            hint_text="Поиск по номеру, комментарию…",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            expand=True,
            on_submit=self._handle_search,
        )
        self.search_button = ft.Button(
            "Найти", icon=ft.Icons.SEARCH, on_click=self._handle_search
        )
        self.refresh_button = ft.IconButton(
            ft.Icons.REFRESH, tooltip="Обновить", on_click=self._handle_refresh
        )
        self.previous_button = ft.IconButton(
            ft.Icons.CHEVRON_LEFT, tooltip="Предыдущая страница", on_click=self._handle_previous
        )
        self.next_button = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT, tooltip="Следующая страница", on_click=self._handle_next
        )
        self.list_view = ft.ListView(
            spacing=6, expand=True, padding=ft.Padding.only(right=6)
        )
        self.range_label = caption("")

    def build(self) -> ft.Control:
        """Строит дерево элементов экрана.

        Returns:
            Корневой элемент экрана.
        """
        return ft.Column(
            expand=True,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[title("Производственные задания"), self.refresh_button],
                ),
                ft.Row(spacing=10, controls=[self.search_field, self.search_button]),
                self.status.control,
                ft.Container(content=self.list_view, expand=True),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        self.range_label,
                        ft.Row(
                            spacing=0,
                            controls=[self.previous_button, self.next_button],
                        ),
                    ],
                ),
            ],
        )

    def interactive_controls(self) -> Sequence[ft.Control]:
        """Возвращает элементы, блокируемые на время загрузки."""
        return (
            self.search_field,
            self.search_button,
            self.refresh_button,
            self.previous_button,
            self.next_button,
        )

    def after_action(self) -> None:
        """Уточняет доступность кнопок листания после загрузки."""
        page = self._current
        self.previous_button.disabled = not (page and page.has_previous)
        self.next_button.disabled = not (page and page.has_next)

    async def ensure_loaded(self) -> None:
        """Загружает первую страницу, если экран ещё не открывали."""
        if not self.loaded:
            await self.load()

    async def load(self) -> None:
        """Загружает текущую страницу списка и перерисовывает её.

        Список заполняется внутри операции, а не после неё: перерисовку на
        экран отправляет `run_action` своим последним `page.update()`, и он же
        сверяется с `_current`, когда решает, доступны ли кнопки листания.
        """
        service = self._service_factory()
        query = TaskQuery(search=self._search, offset=self._offset, limit=self._page_size)

        async def load_and_render() -> TaskPage:
            """Загружает страницу и сразу заполняет список."""
            page = await service.list_tasks(query)
            self._current = page
            self.loaded = True
            self._render(page)
            return page

        self._current = None
        self.range_label.value = ""
        self.list_view.controls.clear()

        await self.run_action(
            action=load_and_render,
            busy_message="Загрузка заданий…",
            failure_message="Не удалось загрузить список заданий",
        )

    def set_page_size(self, page_size: int) -> None:
        """Задаёт размер страницы из настроек.

        Args:
            page_size: Количество заданий на странице.
        """
        self._page_size = page_size

    def reset(self) -> None:
        """Сбрасывает состояние — например, после смены учётной записи."""
        self.loaded = False
        self._offset = 0
        self._current = None

    def _render(self, page: TaskPage) -> None:
        """Заполняет список карточками заданий.

        Args:
            page: Загруженная страница списка.
        """
        if page.tasks:
            self.list_view.controls.extend(self._task_card(task) for task in page.tasks)
        else:
            self.list_view.controls.append(
                info_notice(
                    "По запросу ничего не найдено"
                    if self._search
                    else "В МойСклад нет производственных заданий"
                )
            )

        self.range_label.value = f"{page.first_number}–{page.last_number} из {page.total}"

    def _task_card(self, task: ProductionTask) -> ft.Control:
        """Создаёт карточку одного задания.

        Args:
            task: Производственное задание.

        Returns:
            Карточка для списка.
        """
        summary: List[str] = [task.moment_display]
        if task.state:
            summary.append(task.state)
        summary.append(f"позиций: {task.positions_count}")

        subtitle_controls: List[ft.Control] = [caption("  •  ".join(summary))]
        if task.description:
            subtitle_controls.append(
                ft.Text(
                    task.description,
                    size=12,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        return ft.Card(
            content=ft.ListTile(
                leading=ft.Icon(ft.Icons.INVENTORY_2, color=ft.Colors.PRIMARY),
                title=ft.Text(task.name, weight=ft.FontWeight.W_500),
                subtitle=ft.Column(spacing=2, tight=True, controls=subtitle_controls),
                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT),
                on_click=lambda event, item=task: self._on_open_task(item),
            )
        )

    async def _handle_search(self, event: ft.Event) -> None:
        """Выполняет поиск с первой страницы."""
        self._search = self.search_field.value or ""
        self._offset = 0
        await self.load()

    async def _handle_refresh(self, event: ft.Event) -> None:
        """Перезагружает текущую страницу."""
        await self.load()

    async def _handle_previous(self, event: ft.Event) -> None:
        """Переходит на предыдущую страницу."""
        self._offset = max(0, self._offset - self._page_size)
        await self.load()

    async def _handle_next(self, event: ft.Event) -> None:
        """Переходит на следующую страницу."""
        if self._current and self._current.has_next:
            self._offset += self._page_size
            await self.load()
