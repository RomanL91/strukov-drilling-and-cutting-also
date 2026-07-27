"""Асинхронный HTTP-транспорт поверх aiohttp."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional, Union

import aiohttp
from yarl import URL

from app.infrastructure.http.retry import RetryPolicy


@dataclass(frozen=True)
class HttpResponse:
    """Ответ на HTTP-запрос.

    Attributes:
        status: Код состояния HTTP.
        payload: Разобранный JSON либо текст, если тело не JSON.
    """

    status: int
    payload: Any

    @property
    def is_success(self) -> bool:
        """Успешен ли ответ по коду состояния."""
        return 200 <= self.status < 300

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Возвращает тело словарём либо пустой словарь."""
        return self.payload if isinstance(self.payload, dict) else {}

    @property
    def as_text(self) -> str:
        """Возвращает тело строкой."""
        return self.payload if isinstance(self.payload, str) else str(self.payload)


class HttpClient:
    """Единая сессия aiohttp с политикой повторов.

    Авторизация не хранится в клиенте, а передаётся на каждый запрос: одну и ту
    же сессию используют и МойСклад, и станок, а учётные данные МойСклад не
    должны уезжать вместе с запросами к оборудованию.
    """

    def __init__(self, retry_policy: Optional[RetryPolicy] = None):
        """Создаёт клиент с заданной политикой повторов.

        Args:
            retry_policy: Политика повторов; по умолчанию — стандартная.
        """
        self._session: Optional[aiohttp.ClientSession] = None
        self._retry_policy = retry_policy or RetryPolicy()

    async def __aenter__(self) -> "HttpClient":
        """Открывает сессию при входе в асинхронный контекст."""
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Закрывает сессию при выходе из асинхронного контекста."""
        await self.close()

    @asynccontextmanager
    async def context(self) -> AsyncIterator["HttpClient"]:
        """Возвращает контекстный менеджер с гарантированным закрытием сессии."""
        try:
            await self.open()
            yield self
        finally:
            await self.close()

    async def open(self) -> None:
        """Открывает сессию, если она ещё не открыта."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Закрывает сессию и освобождает соединения."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Возвращает открытую сессию, при необходимости создавая её."""
        if not self._session or self._session.closed:
            await self.open()
        return self._session

    async def request(
        self,
        method: str,
        url: Union[str, URL],
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        auth: Optional[aiohttp.BasicAuth] = None,
        as_text: bool = False,
    ) -> HttpResponse:
        """Выполняет запрос с повторами при сетевых сбоях.

        Args:
            method: Метод HTTP.
            url: Адрес запроса; `yarl.URL` с `encoded=True` уходит без переэкранирования.
            headers: Дополнительные заголовки.
            params: Параметры строки запроса.
            json_data: Тело запроса в формате JSON.
            timeout: Общий таймаут запроса в секундах.
            auth: Базовая авторизация для этого запроса.
            as_text: Читать ответ текстом, не пытаясь разобрать JSON.

        Returns:
            Код состояния и тело ответа.

        Raises:
            ConnectionError: Сетевой сбой не удалось преодолеть повторами.
        """

        async def perform() -> HttpResponse:
            """Выполняет одну попытку запроса."""
            session = await self._get_session()
            async with session.request(
                method=method.upper(),
                url=url,
                auth=auth,
                headers=headers,
                params=params,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if as_text:
                    return HttpResponse(response.status, await response.text())
                try:
                    payload: Any = await response.json()
                except (aiohttp.ContentTypeError, ValueError):
                    payload = await response.text()
                return HttpResponse(response.status, payload)

        return await self._retry_policy.run(perform)

    async def get(self, url: Union[str, URL], **kwargs) -> HttpResponse:
        """Выполняет GET-запрос."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: Union[str, URL], **kwargs) -> HttpResponse:
        """Выполняет POST-запрос."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: Union[str, URL], **kwargs) -> HttpResponse:
        """Выполняет PUT-запрос."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: Union[str, URL], **kwargs) -> HttpResponse:
        """Выполняет DELETE-запрос."""
        return await self.request("DELETE", url, **kwargs)
