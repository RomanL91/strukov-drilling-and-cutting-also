"""Экран настроек: доступ к МойСклад, адрес станка, параметры запросов."""

from typing import Awaitable, Callable, List, Optional, Sequence

import flet as ft

from app.application.container import ServiceContainer
from app.application.production_service import ProductionService
from app.core.config import MS_DEFAULT_BASE_URL, AppConfig
from app.core.paths import config_file, log_dir
from app.ui.base_view import BaseView
from app.ui.common import caption, show_snack, title


class SettingsView(BaseView):
    """Форма настроек с проверкой подключений."""

    def __init__(
        self,
        page: ft.Page,
        config_provider: Callable[[], AppConfig],
        on_save: Callable[[AppConfig], None],
        container_factory: Callable[[AppConfig], ServiceContainer],
    ):
        """Создаёт экран настроек.

        Args:
            page: Страница Flet.
            config_provider: Поставщик текущих настроек.
            on_save: Обработчик сохранения настроек.
            container_factory: Фабрика контейнера по произвольным настройкам —
                позволяет проверять связь до сохранения формы.
        """
        super().__init__(page)
        self._config_provider = config_provider
        self._on_save = on_save
        self._container_factory = container_factory

        self.login = ft.TextField(label="Логин МойСклад", dense=True, expand=True)
        self.password = ft.TextField(
            label="Пароль МойСклад",
            password=True,
            can_reveal_password=True,
            dense=True,
            expand=True,
        )
        self.ms_base_url = ft.TextField(label="Адрес API МойСклад", dense=True)
        self.machine_host = ft.TextField(label="IP или хост станка", dense=True, expand=True)
        self.machine_port = ft.TextField(
            label="Порт", dense=True, width=120, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.timeout = ft.TextField(
            label="Таймаут запроса, с",
            dense=True,
            width=180,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.page_size = ft.TextField(
            label="Заданий на странице",
            dense=True,
            width=180,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.save_button = ft.FilledButton(
            "Сохранить", icon=ft.Icons.SAVE, on_click=self._handle_save
        )
        self.check_ms_button = ft.Button(
            "Проверить МойСклад", icon=ft.Icons.FACT_CHECK, on_click=self._handle_check_ms
        )
        self.check_machine_button = ft.Button(
            "Проверить станок",
            icon=ft.Icons.WIFI_TETHERING,
            on_click=self._handle_check_machine,
        )

    def build(self) -> ft.Control:
        """Строит дерево элементов экрана.

        Returns:
            Корневой элемент экрана.
        """
        self.fill_from_config()
        return ft.Column(
            expand=True,
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                title("Настройки"),
                self.status.control,
                self._section(
                    "МойСклад",
                    [
                        ft.Row(spacing=12, controls=[self.login, self.password]),
                        self.ms_base_url,
                        caption(
                            "Логин и пароль пользователя МойСклад с доступом "
                            "к производственным заданиям."
                        ),
                    ],
                ),
                self._section(
                    "Станок",
                    [
                        ft.Row(spacing=12, controls=[self.machine_host, self.machine_port]),
                        caption(
                            "Адрес линии сверления и отреза в локальной сети. "
                            "По документации управляющий компьютер должен иметь "
                            "адрес 192.168.0.108."
                        ),
                    ],
                ),
                self._section(
                    "Запросы", [ft.Row(spacing=12, controls=[self.timeout, self.page_size])]
                ),
                ft.Row(
                    spacing=10,
                    controls=[
                        self.save_button,
                        self.check_ms_button,
                        self.check_machine_button,
                    ],
                ),
                ft.Divider(height=1),
                ft.Column(
                    spacing=4,
                    controls=[
                        caption(f"Файл настроек: {config_file()}"),
                        caption(f"Логи: {log_dir()}"),
                        caption("Пароль хранится в файле настроек в открытом виде."),
                    ],
                ),
            ],
        )

    def interactive_controls(self) -> Sequence[ft.Control]:
        """Возвращает кнопки, блокируемые на время проверки."""
        return (self.save_button, self.check_ms_button, self.check_machine_button)

    def fill_from_config(self) -> None:
        """Заполняет поля формы текущими настройками."""
        config = self._config_provider()
        self.login.value = config.ms_login
        self.password.value = config.ms_password
        self.ms_base_url.value = config.ms_base_url or MS_DEFAULT_BASE_URL
        self.machine_host.value = config.machine_host
        self.machine_port.value = str(config.machine_port)
        self.timeout.value = str(int(config.request_timeout))
        self.page_size.value = str(config.page_size)

    def _collect(self) -> Optional[AppConfig]:
        """Собирает настройки из полей формы.

        Returns:
            Настройки либо None, если форма заполнена неверно; в этом случае
            поля с ошибками подсвечиваются.
        """
        for field in (self.machine_port, self.timeout, self.page_size, self.machine_host):
            field.error = None

        has_errors = False

        port = self._parse_int(self.machine_port.value)
        if port is None or not 1 <= port <= 65535:
            self.machine_port.error = "1–65535"
            has_errors = True

        timeout = self._parse_float(self.timeout.value)
        if timeout is None or not 1 <= timeout <= 300:
            self.timeout.error = "1–300"
            has_errors = True

        page_size = self._parse_int(self.page_size.value)
        if page_size is None or not 10 <= page_size <= 100:
            self.page_size.error = "10–100"
            has_errors = True

        if not (self.machine_host.value or "").strip():
            self.machine_host.error = "Укажите адрес станка"
            has_errors = True

        if has_errors:
            self.page.update()
            return None

        return AppConfig(
            ms_login=(self.login.value or "").strip(),
            ms_password=self.password.value or "",
            ms_base_url=(self.ms_base_url.value or "").strip() or MS_DEFAULT_BASE_URL,
            machine_host=(self.machine_host.value or "").strip(),
            machine_port=port,
            request_timeout=timeout,
            page_size=page_size,
        )

    async def _handle_save(self, event: ft.Event) -> None:
        """Сохраняет настройки."""
        config = self._collect()
        if config is None:
            return

        self._on_save(config)
        self.status.success("Настройки сохранены")
        show_snack(self.page, "Настройки сохранены")
        self.page.update()

    async def _handle_check_ms(self, event: ft.Event) -> None:
        """Проверяет доступ к МойСклад по значениям формы."""
        await self._check(
            "Проверка доступа к МойСклад…",
            lambda service: service.check_repository(),
            "Проверка МойСклад не удалась",
        )

    async def _handle_check_machine(self, event: ft.Event) -> None:
        """Проверяет связь со станком по значениям формы."""
        await self._check(
            "Проверка связи со станком…",
            lambda service: service.check_machine(),
            "Проверка станка не удалась",
        )

    async def _check(
        self,
        busy_message: str,
        operation: Callable[[ProductionService], Awaitable[str]],
        failure_message: str,
    ) -> None:
        """Проверяет подключение по значениям формы, не требуя сохранения.

        Args:
            busy_message: Текст индикатора выполнения.
            operation: Операция фасада, выполняющая проверку.
            failure_message: Текст для журнала при непредвиденной ошибке.
        """
        config = self._collect()
        if config is None:
            return

        container = self._container_factory(config)
        await self.run_action(
            action=lambda: operation(container.production_service()),
            busy_message=busy_message,
            success_message=lambda message: message,
            failure_message=failure_message,
        )

    @staticmethod
    def _section(heading: str, controls: List[ft.Control]) -> ft.Control:
        """Оформляет группу полей рамкой с заголовком.

        Args:
            heading: Заголовок группы.
            controls: Элементы группы.

        Returns:
            Оформленная группа.
        """
        return ft.Container(
            padding=ft.Padding.all(16),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=ft.BorderRadius.all(10),
            content=ft.Column(spacing=12, controls=[title(heading, size=15), *controls]),
        )

    @staticmethod
    def _parse_int(value) -> Optional[int]:
        """Приводит значение поля к целому числу.

        Args:
            value: Значение текстового поля.

        Returns:
            Целое число либо None.
        """
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_float(value) -> Optional[float]:
        """Приводит значение поля к вещественному числу.

        Args:
            value: Значение текстового поля.

        Returns:
            Число либо None.
        """
        try:
            return float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError):
            return None
