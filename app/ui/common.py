"""Переиспользуемые элементы интерфейса."""

from typing import List, Optional

import flet as ft


def show_snack(page: ft.Page, message: str, error: bool = False) -> None:
    """Показывает всплывающее уведомление внизу окна.

    Args:
        page: Страница Flet.
        message: Текст уведомления.
        error: True — оформить как ошибку.
    """
    page.show_dialog(
        ft.SnackBar(
            open=True,
            content=ft.Text(message, color=ft.Colors.WHITE if error else None),
            bgcolor=ft.Colors.RED_700 if error else None,
        )
    )


def title(text: str, size: int = 20) -> ft.Text:
    """Создаёт заголовок.

    Args:
        text: Текст заголовка.
        size: Размер шрифта.

    Returns:
        Текстовый элемент заголовка.
    """
    return ft.Text(text, size=size, weight=ft.FontWeight.W_600)


def caption(text: str) -> ft.Text:
    """Создаёт пояснительную подпись.

    Args:
        text: Текст подписи.

    Returns:
        Текстовый элемент подписи.
    """
    return ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT)


def notice(message: str, icon: str, color: str, bgcolor: str) -> ft.Container:
    """Создаёт цветной блок с сообщением.

    Args:
        message: Текст сообщения.
        icon: Значок слева.
        color: Цвет текста и значка.
        bgcolor: Цвет подложки.

    Returns:
        Готовый блок сообщения.
    """
    return ft.Container(
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Icon(icon, color=color, size=20),
                ft.Text(message, color=color, expand=True, selectable=True),
            ],
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        bgcolor=bgcolor,
        border_radius=ft.BorderRadius.all(8),
    )


def error_notice(message: str) -> ft.Container:
    """Создаёт блок сообщения об ошибке."""
    return notice(message, ft.Icons.ERROR_OUTLINE, ft.Colors.RED_700, ft.Colors.RED_50)


def warning_notice(message: str) -> ft.Container:
    """Создаёт блок предупреждения."""
    return notice(message, ft.Icons.WARNING_AMBER, ft.Colors.AMBER_900, ft.Colors.AMBER_50)


def info_notice(message: str) -> ft.Container:
    """Создаёт информационный блок."""
    return notice(message, ft.Icons.INFO_OUTLINE, ft.Colors.BLUE_GREY_700, ft.Colors.BLUE_GREY_50)


def success_notice(message: str) -> ft.Container:
    """Создаёт блок сообщения об успехе."""
    return notice(
        message, ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN_700, ft.Colors.GREEN_50
    )


def bullet_list(header: str, items: List[str], limit: int = 20) -> str:
    """Собирает маркированный список для блока сообщения.

    Args:
        header: Заголовок перед списком.
        items: Строки списка.
        limit: Сколько строк показать целиком.

    Returns:
        Готовый многострочный текст.
    """
    shown = items[:limit]
    text = "\n".join(f"• {item}" for item in shown)
    if len(items) > len(shown):
        text += f"\n… и ещё {len(items) - len(shown)}"
    return f"{header}\n{text}"


def stat_tile(label: str, value: str) -> ft.Control:
    """Создаёт плитку с числовым показателем.

    Args:
        label: Подпись показателя.
        value: Значение показателя.

    Returns:
        Готовая плитка.
    """
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=ft.BorderRadius.all(8),
        content=ft.Column(
            spacing=2,
            tight=True,
            controls=[caption(label), ft.Text(value, size=18, weight=ft.FontWeight.W_600)],
        ),
    )


class StatusLine:
    """Строка состояния экрана: занятость, ошибка или успех.

    Обёртка над `ft.Container`, а не наследник: элементы Flet — датаклассы,
    и композиция здесь надёжнее наследования.
    """

    def __init__(self):
        """Создаёт скрытую строку состояния."""
        self.control = ft.Container(visible=False, padding=0)

    def busy(self, message: str) -> None:
        """Показывает индикатор выполнения.

        Args:
            message: Текст рядом с индикатором.
        """
        self.control.content = ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(width=16, height=16, stroke_width=2),
                ft.Text(message, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        )
        self.control.visible = True

    def error(self, message: str) -> None:
        """Показывает сообщение об ошибке.

        Args:
            message: Текст ошибки.
        """
        self.control.content = error_notice(message)
        self.control.visible = True

    def success(self, message: str) -> None:
        """Показывает сообщение об успехе.

        Args:
            message: Текст сообщения.
        """
        self.control.content = success_notice(message)
        self.control.visible = True

    def clear(self) -> None:
        """Скрывает строку состояния."""
        self.control.content = None
        self.control.visible = False
