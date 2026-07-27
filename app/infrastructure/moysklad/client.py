"""Низкоуровневый клиент API МойСклад.

Отвечает только за транспорт: собрать адрес, подставить авторизацию, разобрать
ошибку. Превращением ответов в модели занимается `mapper`, выборкой — `repository`.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp

from app.core.logger import logger
from app.domain.errors import RepositoryError
from app.infrastructure.http.client import HttpClient, HttpResponse

# Ограничения пагинации МойСклад: обычно 1000, но с раскрытием ссылок — 100.
MAX_LIMIT = 1000
MAX_LIMIT_WITH_EXPAND = 100


class MoySkladClient:
    """Клиент API МойСклад с базовой авторизацией."""

    def __init__(
        self,
        http: HttpClient,
        login: str,
        password: str,
        base_url: str = "https://api.moysklad.ru/api/remap/1.2",
        timeout: float = 30.0,
    ):
        """Создаёт клиент для конкретной учётной записи.

        Args:
            http: Общий HTTP-транспорт приложения.
            login: Логин пользователя МойСклад.
            password: Пароль пользователя МойСклад.
            base_url: Базовый адрес API.
            timeout: Таймаут запроса в секундах.
        """
        self._http = http
        self._auth = aiohttp.BasicAuth(login, password)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        }

    def _absolute(self, url: str) -> str:
        """Достраивает относительный адрес до абсолютного.

        Args:
            url: Относительный путь либо готовая ссылка из ответа МойСклад.

        Returns:
            Абсолютный адрес запроса.
        """
        if url.startswith(self._base_url):
            return url
        return urljoin(self._base_url + "/", url.lstrip("/"))

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполняет GET-запрос к API.

        Args:
            url: Относительный путь либо абсолютная ссылка.
            params: Параметры строки запроса.

        Returns:
            Тело ответа словарём.

        Raises:
            RepositoryError: API вернуло ошибку либо неожиданный ответ.
        """
        absolute = self._absolute(url)
        try:
            response = await self._http.get(
                absolute,
                headers=self._headers,
                params=params,
                auth=self._auth,
                timeout=self._timeout,
            )
        except ConnectionError as error:
            raise RepositoryError(f"МойСклад недоступен: {error}") from error

        if not response.is_success or not isinstance(response.payload, dict):
            raise RepositoryError(
                self._error_text(response, absolute), status=response.status
            )
        return response.payload

    async def get_page(
        self,
        url: str,
        limit: int = 50,
        offset: int = 0,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Запрашивает одну страницу списка.

        Args:
            url: Путь к списочному ресурсу.
            limit: Размер страницы.
            offset: Смещение от начала списка.
            params: Дополнительные параметры запроса.

        Returns:
            Ответ с полями `rows` и `meta`.
        """
        query = dict(params or {})
        if "expand" in query:
            limit = min(limit, MAX_LIMIT_WITH_EXPAND)
        query["limit"] = limit
        query["offset"] = offset
        return await self.get(url, params=query)

    async def get_all(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Выкачивает все страницы списка.

        Args:
            url: Путь к списочному ресурсу.
            params: Дополнительные параметры запроса.

        Returns:
            Все строки списка.
        """
        query = dict(params or {})
        limit = MAX_LIMIT_WITH_EXPAND if "expand" in query else MAX_LIMIT
        offset = 0
        rows: List[Dict[str, Any]] = []

        while True:
            response = await self.get_page(url, limit=limit, offset=offset, params=query)
            page = response.get("rows", [])
            meta = response.get("meta", {})
            logger.info(f"{url}: size={meta.get('size')} limit={limit} offset={offset}")

            rows.extend(page)
            if len(page) < limit:
                break
            offset += limit

        return rows

    @staticmethod
    def _error_text(response: HttpResponse, url: str) -> str:
        """Собирает читаемое сообщение из ответа МойСклад.

        Args:
            response: Ответ API.
            url: Адрес запроса для подстановки в текст.

        Returns:
            Сообщение для интерфейса.
        """
        status = response.status
        if status in (401, 403):
            return "МойСклад отклонил авторизацию — проверьте логин и пароль в настройках"
        if status == 404:
            return f"Объект не найден в МойСклад: {url}"
        if status == 429:
            return "МойСклад ограничил частоту запросов — повторите через несколько секунд"

        errors = response.as_dict.get("errors")
        if isinstance(errors, list) and errors:
            parts = []
            for item in errors:
                if not isinstance(item, dict):
                    continue
                text = item.get("error") or ""
                more = item.get("moreInfo")
                parts.append(f"{text} ({more})" if more else text)
            joined = "; ".join(part for part in parts if part)
            if joined:
                return f"МойСклад ({status}): {joined}"

        if isinstance(response.payload, str) and response.payload.strip():
            return f"МойСклад ({status}): {response.payload.strip()[:300]}"

        return f"МойСклад вернул неожиданный ответ (HTTP {status})"
