"""Экран задания: сводка, проверка по протоколу и отправка на станок."""

from typing import Callable, List, Optional, Sequence

import flet as ft

from app.application.production_service import ProductionService
from app.core.logger import logger
from app.domain.models import Job, ProductionTask
from app.infrastructure.machine.protocol import ProtocolLimits, browser_url
from app.ui.base_view import BaseView
from app.ui.common import (
    bullet_list,
    caption,
    error_notice,
    info_notice,
    stat_tile,
    title,
    warning_notice,
)


class JobView(BaseView):
    """Разбор задания, предпросмотр пакета и отправка на оборудование."""

    def __init__(
        self,
        page: ft.Page,
        service_factory: Callable[[], ProductionService],
        machine_address: Callable[[], str],
        limits: ProtocolLimits,
        on_back: Callable[[], None],
    ):
        """Создаёт экран задания.

        Args:
            page: Страница Flet.
            service_factory: Поставщик фасада с текущими настройками.
            machine_address: Поставщик адреса станка для диалога подтверждения.
            limits: Ограничения протокола для показа в плитках.
            on_back: Обработчик возврата к списку заданий.
        """
        super().__init__(page)
        self._service_factory = service_factory
        self._machine_address = machine_address
        self._limits = limits
        self._on_back = on_back
        self._job: Optional[Job] = None
        # Служба создаётся при первом обращении и переиспользуется: страница
        # складывает службы в общий список и не убирает их оттуда.
        self._url_launcher: Optional[ft.UrlLauncher] = None

        self.header = title("")
        self.subheader = caption("")
        self.body = ft.Column(expand=True, spacing=14, scroll=ft.ScrollMode.AUTO)

        self.back_button = ft.IconButton(
            ft.Icons.ARROW_BACK, tooltip="К списку заданий", on_click=lambda e: self._on_back()
        )
        self.copy_button = ft.Button(
            "Копировать URL", icon=ft.Icons.CONTENT_COPY, on_click=self._handle_copy, disabled=True
        )
        self.open_button = ft.Button(
            "Открыть в браузере",
            icon=ft.Icons.OPEN_IN_BROWSER,
            on_click=self._handle_open,
            disabled=True,
        )
        self.send_button = ft.FilledButton(
            "Отправить на станок",
            icon=ft.Icons.SEND,
            on_click=self._handle_send_click,
            disabled=True,
        )

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
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        self.back_button,
                        ft.Column(
                            spacing=0, tight=True, controls=[self.header, self.subheader]
                        ),
                    ],
                ),
                self.status.control,
                ft.Container(content=self.body, expand=True),
                ft.Divider(height=1),
                ft.Row(
                    spacing=10,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[self.copy_button, self.open_button, self.send_button],
                ),
            ],
        )

    def interactive_controls(self) -> Sequence[ft.Control]:
        """Возвращает кнопки, блокируемые на время операции."""
        return (self.copy_button, self.open_button, self.send_button)

    def after_action(self) -> None:
        """Согласует доступность кнопок с состоянием задания."""
        job = self._job
        self.copy_button.disabled = job is None or job.is_empty
        self.open_button.disabled = job is None or job.is_empty
        self.send_button.disabled = job is None or not job.can_send

    async def load(self, task: ProductionTask) -> None:
        """Загружает задание и показывает сводку.

        Args:
            task: Производственное задание.
        """
        service = self._service_factory()
        self._job = None
        self.header.value = task.name
        self.subheader.value = (
            f"{task.moment_display}  •  позиций: {task.positions_count}"
        )
        self.body.controls.clear()

        job = await self.run_action(
            action=lambda: service.build_job(task),
            busy_message="Загрузка позиций и разбор атрибутов…",
            failure_message="Не удалось собрать задание",
        )
        if job is None:
            return

        self._job = job
        self._render(job)
        self.after_action()
        self.page.update()

    def _render(self, job: Job) -> None:
        """Заполняет тело экрана блоками сводки.

        Args:
            job: Собранное задание.
        """
        controls: List[ft.Control] = []

        if job.is_empty:
            controls.append(
                info_notice(
                    "В задании не нашлось ни одного профиля с заполненными атрибутами. "
                    "Отправлять на станок нечего."
                )
            )

        if job.violations:
            controls.append(
                error_notice(
                    bullet_list(
                        "Пакет не соответствует протоколу станка, отправка заблокирована:",
                        list(job.violations),
                    )
                )
            )

        if job.packet_warnings:
            controls.append(
                warning_notice(bullet_list("Замечания к пакету:", list(job.packet_warnings)))
            )

        if job.parse_warnings:
            controls.append(
                warning_notice(
                    bullet_list(
                        f"Замечания при разборе ({len(job.parse_warnings)}):",
                        list(job.parse_warnings),
                    )
                )
            )

        if not job.is_empty:
            controls.append(self._totals(job))
            controls.append(self._table(job))

        controls.append(self._url_block(job))
        self.body.controls = controls

    def _totals(self, job: Job) -> ft.Control:
        """Строит ряд плиток с итогами.

        Args:
            job: Собранное задание.

        Returns:
            Ряд плиток.
        """
        return ft.Row(
            spacing=10,
            wrap=True,
            controls=[
                stat_tile("Отрезков", str(job.total_pieces)),
                stat_tile("Суммарная длина", f"{job.total_length_m:.2f} м"),
                stat_tile(
                    "Блоков в пакете",
                    f"{job.packet.block_count} из {self._limits.max_blocks}",
                ),
                stat_tile(
                    "Размер пакета",
                    f"{job.packet.byte_length} из {self._limits.max_url_bytes} б",
                ),
            ],
        )

    def _table(self, job: Job) -> ft.Control:
        """Строит таблицу того, что уйдёт на станок.

        Args:
            job: Собранное задание.

        Returns:
            Заголовок и прокручиваемая таблица.
        """
        return ft.Column(
            spacing=6,
            controls=[
                title("Что уйдёт на станок", size=16),
                ft.Row(
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.DataTable(
                            column_spacing=24,
                            heading_row_height=40,
                            data_row_max_height=48,
                            columns=[
                                ft.DataColumn(ft.Text("Изделие")),
                                ft.DataColumn(ft.Text("Профиль")),
                                ft.DataColumn(ft.Text("Длина, мм"), numeric=True),
                                ft.DataColumn(ft.Text("Кол-во"), numeric=True),
                                ft.DataColumn(ft.Text("Сверление, мм")),
                            ],
                            rows=[
                                ft.DataRow(
                                    cells=[
                                        ft.DataCell(ft.Text(row.client)),
                                        ft.DataCell(ft.Text(row.profile_title)),
                                        ft.DataCell(ft.Text(str(row.length_mm))),
                                        ft.DataCell(ft.Text(str(row.quantity))),
                                        ft.DataCell(ft.Text(row.drilling_display)),
                                    ]
                                )
                                for row in job.rows
                            ],
                        )
                    ],
                ),
            ],
        )

    def _url_block(self, job: Job) -> ft.Control:
        """Строит блок с адресом пакета.

        Args:
            job: Собранное задание.

        Returns:
            Заголовок и поле с адресом.
        """
        return ft.Column(
            spacing=6,
            controls=[
                title("Адрес задания", size=16),
                ft.TextField(
                    value=job.url,
                    read_only=True,
                    multiline=True,
                    min_lines=2,
                    max_lines=6,
                    text_size=12,
                ),
            ],
        )

    async def _handle_copy(self, event: ft.Event) -> None:
        """Копирует адрес пакета в буфер обмена.

        Работа с буфером асинхронная: без `await` корутина не выполняется, и
        сообщение об успехе появляется при пустом буфере.
        """
        if self._job is None:
            return

        try:
            await self.page.clipboard.set(self._job.url)
        except Exception as error:  # noqa: BLE001 — в интерфейсе нельзя падать молча
            logger.exception("Не удалось скопировать адрес в буфер обмена")
            self.status.error(f"Не удалось скопировать адрес: {error}")
        else:
            self.status.success("URL скопирован в буфер обмена")

        self.page.update()

    async def _handle_open(self, event: ft.Event) -> None:
        """Открывает адрес пакета в браузере."""
        if self._job is None:
            return

        if self._url_launcher is None:
            self._url_launcher = ft.UrlLauncher()

        try:
            await self._url_launcher.launch_url(browser_url(self._job.url))
        except Exception as error:  # noqa: BLE001 — в интерфейсе нельзя падать молча
            logger.exception("Не удалось открыть адрес в браузере")
            self.status.error(f"Не удалось открыть браузер: {error}")
            self.page.update()

    async def _handle_send_click(self, event: ft.Event) -> None:
        """Спрашивает подтверждение перед отправкой на станок."""
        job = self._job
        if job is None:
            return

        async def confirm(_: ft.Event) -> None:
            """Закрывает диалог и отправляет задание."""
            self.page.pop_dialog()
            await self._send(job)

        def cancel(_: ft.Event) -> None:
            """Закрывает диалог без отправки."""
            self.page.pop_dialog()

        self.page.show_dialog(
            ft.AlertDialog(
                open=True,
                modal=True,
                title=ft.Text("Отправить задание на станок?"),
                content=ft.Text(
                    f"Задание «{job.task.name}»: {job.packet.block_count} блоков, "
                    f"{job.total_pieces} отрезков, {job.total_length_m:.2f} м профиля.\n"
                    f"Адрес станка: {self._machine_address()}\n\n"
                    "Перед отправкой будет проверено, что оборудование свободно."
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=cancel),
                    ft.FilledButton("Отправить", icon=ft.Icons.SEND, on_click=confirm),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    async def _send(self, job: Job) -> None:
        """Отправляет задание на станок.

        Args:
            job: Собранное задание.
        """
        service = self._service_factory()
        await self.run_action(
            action=lambda: service.send_job(job),
            busy_message="Проверка готовности и отправка…",
            success_message=lambda message: message,
            failure_message="Не удалось отправить задание на станок",
        )
