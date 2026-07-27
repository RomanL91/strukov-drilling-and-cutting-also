"""Композиционный корень приложения.

Единственное место, где интерфейсы связываются с конкретными реализациями.
Паттерн «Фабрика»: интерфейс просит `production_service()` и получает готовый
фасад, не зная состава зависимостей. Замена источника данных или протокола
станка сводится к правке этого модуля.
"""

from app.core.config import AppConfig
from app.domain.errors import ConfigError
from app.domain.profiles import ProfileCatalog
from app.infrastructure.http.client import HttpClient
from app.infrastructure.machine.builder import AlsoPacketBuilder
from app.infrastructure.machine.gateway import AlsoMachineGateway
from app.infrastructure.machine.protocol import (
    PacketValidator,
    ProtocolLimits,
    ValueEncoder,
)
from app.infrastructure.machine.status import MachineStatusParser
from app.infrastructure.moysklad.attributes import AttributeProfileExtractor
from app.infrastructure.moysklad.client import MoySkladClient
from app.infrastructure.moysklad.mapper import ProductionTaskMapper
from app.infrastructure.moysklad.repository import MoySkladTaskRepository
from app.application.job_assembler import JobAssembler
from app.application.production_service import ProductionService


class ServiceContainer:
    """Собирает объектный граф приложения по текущим настройкам.

    Контейнер намеренно создаёт объекты заново на каждый вызов: настройки
    меняются из интерфейса, и следующий вызов должен работать уже с новыми
    учётными данными и адресом станка.
    """

    def __init__(self, config: AppConfig, http: HttpClient):
        """Создаёт контейнер.

        Args:
            config: Текущие настройки приложения.
            http: Общий HTTP-транспорт приложения.
        """
        self._config = config
        self._http = http
        self._catalog = ProfileCatalog.default()
        self._limits = ProtocolLimits()

    @property
    def config(self) -> AppConfig:
        """Возвращает настройки, с которыми собран контейнер."""
        return self._config

    @property
    def profile_catalog(self) -> ProfileCatalog:
        """Возвращает справочник типов профилей."""
        return self._catalog

    @property
    def protocol_limits(self) -> ProtocolLimits:
        """Возвращает ограничения протокола станка."""
        return self._limits

    def repository(self) -> MoySkladTaskRepository:
        """Создаёт репозиторий производственных заданий.

        Returns:
            Репозиторий поверх API МойСклад.

        Raises:
            ConfigError: Не заданы учётные данные МойСклад.
        """
        if not self._config.is_ms_configured:
            raise ConfigError("Не заданы логин и пароль МойСклад — откройте «Настройки»")

        client = MoySkladClient(
            self._http,
            login=self._config.ms_login,
            password=self._config.ms_password,
            base_url=self._config.ms_base_url,
            timeout=self._config.request_timeout,
        )
        return MoySkladTaskRepository(client, ProductionTaskMapper())

    def packet_builder(self) -> AlsoPacketBuilder:
        """Создаёт сборщик пакета для текущего адреса станка.

        Returns:
            Сборщик пакета в формате iPAP2.

        Raises:
            ConfigError: Не задан адрес станка.
        """
        if not self._config.is_machine_configured:
            raise ConfigError("Не задан адрес станка — откройте «Настройки»")

        return AlsoPacketBuilder(
            base_url=self._config.machine_base_url,
            limits=self._limits,
            encoder=ValueEncoder(),
            validator=PacketValidator(self._limits),
        )

    def machine_gateway(self) -> AlsoMachineGateway:
        """Создаёт шлюз к оборудованию.

        Returns:
            Шлюз к линии сверления и отреза.

        Raises:
            ConfigError: Не задан адрес станка.
        """
        if not self._config.is_machine_configured:
            raise ConfigError("Не задан адрес станка — откройте «Настройки»")

        return AlsoMachineGateway(
            self._http,
            base_url=self._config.machine_base_url,
            parser=MachineStatusParser(),
            timeout=self._config.request_timeout,
        )

    def production_service(self) -> ProductionService:
        """Собирает фасад со всеми зависимостями.

        Returns:
            Фасад для интерфейса.

        Raises:
            ConfigError: Не хватает настроек МойСклад или станка.
        """
        repository = self.repository()
        assembler = JobAssembler(
            repository=repository,
            extractor=AttributeProfileExtractor(self._catalog),
            packet_builder=self.packet_builder(),
        )
        return ProductionService(
            repository=repository,
            job_assembler=assembler,
            machine=self.machine_gateway(),
        )
