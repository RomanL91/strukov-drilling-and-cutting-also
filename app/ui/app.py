"""Оболочка приложения: навигация и жизненный цикл."""

import flet as ft

from app.application.container import ServiceContainer
from app.application.production_service import ProductionService
from app.core.config import AppConfig, get_config, set_config
from app.core.logger import logger
from app.domain.models import ProductionTask
from app.infrastructure.http.client import HttpClient
from app.ui.common import show_snack
from app.ui.job_view import JobView
from app.ui.settings_view import SettingsView
from app.ui.tasks_view import TasksView

NAV_TASKS = 0
NAV_SETTINGS = 1


class StrukovApp:
    """Главное окно: боковая навигация и переключение экранов.

    Владеет общими ресурсами — HTTP-сессией и контейнером зависимостей —
    и раздаёт экранам доступ к ним через функции-поставщики, чтобы после
    смены настроек экраны получали уже пересобранный контейнер.
    """

    def __init__(self, page: ft.Page):
        """Создаёт приложение на заданной странице.

        Args:
            page: Страница Flet.
        """
        self.page = page
        self._config = get_config()
        # Одна сессия aiohttp на всё приложение — переиспользуем соединения.
        self._http = HttpClient()
        self._container = ServiceContainer(self._config, self._http)

        self.content = ft.Container(expand=True, padding=ft.Padding.all(20))
        self.rail = ft.NavigationRail(
            selected_index=NAV_TASKS,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=72,
            group_alignment=-0.9,
            on_change=self._handle_navigation,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.LIST_ALT, selected_icon=ft.Icons.LIST_ALT, label="Задания"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS, selected_icon=ft.Icons.SETTINGS, label="Настройки"
                ),
            ],
        )

        self.tasks_view = TasksView(page, self._service, self._open_task)
        self.job_view = JobView(
            page,
            self._service,
            lambda: self._config.machine_base_url,
            self._container.protocol_limits,
            self._show_tasks_sync,
        )
        self.settings_view = SettingsView(
            page, lambda: self._config, self._apply_config, self._container_for
        )
        self.tasks_view.set_page_size(self._config.page_size)

    # --- зависимости -------------------------------------------------------

    def _service(self) -> ProductionService:
        """Возвращает фасад, собранный по текущим настройкам.

        Returns:
            Фасад приложения.

        Raises:
            ConfigError: Не хватает настроек МойСклад или станка.
        """
        return self._container.production_service()

    def _container_for(self, config: AppConfig) -> ServiceContainer:
        """Собирает контейнер по произвольным настройкам.

        Нужен экрану настроек: проверка связи выполняется по значениям формы
        до того, как их сохранили.

        Args:
            config: Настройки, по которым нужно собрать зависимости.

        Returns:
            Контейнер зависимостей.
        """
        return ServiceContainer(config, self._http)

    def _apply_config(self, config: AppConfig) -> None:
        """Сохраняет настройки и пересобирает зависимости.

        Args:
            config: Новые настройки.
        """
        self._config = set_config(config)
        self._container = ServiceContainer(self._config, self._http)
        # Учётная запись могла смениться — список перечитаем с первой страницы.
        self.tasks_view.reset()
        self.tasks_view.set_page_size(self._config.page_size)
        logger.info("Настройки сохранены, зависимости пересобраны")

    # --- жизненный цикл ----------------------------------------------------

    async def start(self) -> None:
        """Настраивает окно, открывает сессию и показывает первый экран."""
        self._setup_page()
        await self._http.open()

        self.page.add(
            ft.Row(
                expand=True,
                spacing=0,
                controls=[self.rail, ft.VerticalDivider(width=1), self.content],
            )
        )

        if self._config.is_ms_configured:
            await self._show_tasks()
        else:
            # Без учётных данных список всё равно не загрузится — сразу в настройки.
            self.rail.selected_index = NAV_SETTINGS
            self._show_settings()
            show_snack(
                self.page, "Укажите логин и пароль МойСклад, чтобы загрузить задания"
            )
            self.page.update()

    def _setup_page(self) -> None:
        """Задаёт заголовок, тему и размеры окна."""
        self.page.title = "Струков — сверление и резка"
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.window.width = 1150
        self.page.window.height = 780
        self.page.window.min_width = 900
        self.page.window.min_height = 620
        self.page.on_close = self._handle_close

    async def _handle_navigation(self, event: ft.Event) -> None:
        """Переключает экран по выбору в боковой панели."""
        if self.rail.selected_index == NAV_SETTINGS:
            self._show_settings()
            self.page.update()
        else:
            await self._show_tasks()

    async def _show_tasks(self) -> None:
        """Показывает список заданий и при необходимости загружает его."""
        self.content.content = self.tasks_view.build()
        self.page.update()
        await self.tasks_view.ensure_loaded()

    def _show_tasks_sync(self) -> None:
        """Возвращает к списку заданий без перезагрузки данных."""
        self.content.content = self.tasks_view.build()
        self.page.update()

    def _show_settings(self) -> None:
        """Показывает экран настроек."""
        self.settings_view.fill_from_config()
        self.content.content = self.settings_view.build()

    def _open_task(self, task: ProductionTask) -> None:
        """Открывает экран задания.

        Args:
            task: Выбранное производственное задание.
        """
        self.content.content = self.job_view.build()
        self.page.update()
        self.page.run_task(self.job_view.load, task)

    async def _handle_close(self, event: ft.Event) -> None:
        """Закрывает HTTP-сессию при выходе."""
        await self._http.close()


async def main(page: ft.Page) -> None:
    """Точка входа Flet.

    Args:
        page: Страница, создаваемая средой Flet.
    """
    app = StrukovApp(page)
    await app.start()
