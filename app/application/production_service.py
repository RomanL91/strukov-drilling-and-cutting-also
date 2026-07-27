"""Фасад приложения для интерфейса."""

from app.domain.errors import ProtocolError
from app.domain.interfaces import JobAssembly, MachineGateway, TaskRepository
from app.domain.models import Job, ProductionTask, TaskPage, TaskQuery


class ProductionService:
    """Единая точка входа для интерфейса.

    Паттерн «Фасад»: экраны вызывают четыре понятных операции и не знают ни про
    репозиторий, ни про сборщик пакета, ни про шлюз к оборудованию.
    """

    def __init__(
        self,
        repository: TaskRepository,
        job_assembler: JobAssembly,
        machine: MachineGateway,
    ):
        """Создаёт фасад поверх готовых зависимостей.

        Args:
            repository: Источник производственных заданий.
            job_assembler: Сборщик заданий для станка.
            machine: Шлюз к оборудованию.
        """
        self._repository = repository
        self._job_assembler = job_assembler
        self._machine = machine

    async def list_tasks(self, query: TaskQuery) -> TaskPage:
        """Возвращает страницу списка производственных заданий.

        Args:
            query: Параметры выборки.

        Returns:
            Страница с заданиями и общим количеством.

        Raises:
            RepositoryError: Источник недоступен или отклонил запрос.
        """
        return await self._repository.list_tasks(query)

    async def build_job(self, task: ProductionTask) -> Job:
        """Собирает задание для станка.

        Args:
            task: Производственное задание.

        Returns:
            Готовое задание со сводкой и пакетом.

        Raises:
            RepositoryError: Не удалось загрузить позиции задания.
        """
        return await self._job_assembler.assemble(task)

    async def send_job(self, job: Job) -> str:
        """Отправляет задание на станок, предварительно проверив готовность.

        Пока оборудование занято, оно молча игнорирует команды, поэтому
        состояние проверяется обязательно.

        Args:
            job: Собранное задание.

        Returns:
            Сообщение об успешной отправке для интерфейса.

        Raises:
            ProtocolError: Пакет нарушает ограничения протокола.
            MachineError: Оборудование недоступно, занято или отклонило пакет.
        """
        if not job.can_send:
            raise ProtocolError(
                "Пакет не соответствует протоколу: " + "; ".join(job.violations),
                violations=list(job.violations),
            )

        status = await self._machine.read_status()
        if not status.is_free:
            raise ProtocolError(
                f"Оборудование не готово принять задание — {status.summary}. "
                "Дождитесь завершения текущих заданий."
            )

        result = await self._machine.send(job.packet)
        return (
            f"Задание принято станком: {job.packet.block_count} блоков, "
            f"{job.total_pieces} отрезков. {result.summary}"
        )

    async def check_repository(self) -> str:
        """Проверяет доступ к источнику заданий.

        Returns:
            Сообщение об успешной проверке для интерфейса.

        Raises:
            RepositoryError: Источник недоступен или отклонил запрос.
        """
        total = await self._repository.count_tasks()
        return f"Подключение успешно. Производственных заданий: {total}"

    async def check_machine(self) -> str:
        """Проверяет связь со станком.

        Returns:
            Сообщение с состоянием оборудования для интерфейса.

        Raises:
            MachineError: Оборудование недоступно или ответило ошибкой.
        """
        status = await self._machine.read_status()
        return f"Станок отвечает. {status.summary}"
