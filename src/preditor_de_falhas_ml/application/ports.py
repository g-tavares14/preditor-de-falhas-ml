"""Portas dos use cases: Atlas e armazenamento, sem frameworks."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from preditor_de_falhas_ml.domain.ids import MeasurementId
from preditor_de_falhas_ml.domain.ping import Observation, PingSample, UnusableResult
from preditor_de_falhas_ml.domain.spec import (
    MeasurementDefinition,
    MeasurementSpec,
    ResultFilters,
)


class GatewayError(Exception):
    """Falha de transporte ou HTTP no gateway, já traduzida para a aplicação."""

    def __init__(self, message: str, *, creating: bool = False) -> None:
        super().__init__(message)
        self.creating = creating


@dataclass(frozen=True, slots=True)
class GatewaySnapshot:
    """Definição, resultados de domínio e payload bruto opaco para a CLI."""

    definition: MeasurementDefinition | None
    items: tuple[PingSample | UnusableResult, ...]
    raw_results: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class Rejection:
    """Resultado sem chave de observação; não entra em X."""

    source_event_id: str
    measurement_id: int
    result_index: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """Snapshot já em tipos de domínio, usado na projeção."""

    measurement_id: MeasurementId
    event_id: str
    collected_at: str
    items: tuple[PingSample | UnusableResult, ...]
    error: str | None = None
    credit_balance: int | None = None


@dataclass(frozen=True, slots=True)
class CollectReport:
    """Resumo da coleta ou reconstrução, com as linhas do snapshot atual."""

    measurement_id: int | None
    state: str
    total_rows: int
    total_rejected: int
    accepted: int
    rejected: int
    observations: tuple[Observation, ...]
    rejections: tuple[Rejection, ...]
    dataset_path: str | None = None
    raw_results: tuple[object, ...] = ()
    credit_balance: int | None = None

    def summary(self) -> dict[str, object]:
        return {
            "measurement_id": self.measurement_id,
            "state": self.state,
            "total_rows": self.total_rows,
            "total_rejected": self.total_rejected,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "dataset_path": self.dataset_path,
            "credit_balance": self.credit_balance,
        }


class MeasurementGateway(Protocol):
    """Fonte de medições. O adapter HTTP e o fake de teste implementam isto."""

    def create(self, spec: MeasurementSpec) -> MeasurementId: ...

    def get_credits(self) -> int: ...

    def load_snapshot(
        self, measurement_id: MeasurementId, filters: ResultFilters
    ) -> GatewaySnapshot: ...


class DatasetStore(Protocol):
    """Histórico e CSV. O adapter de arquivos e o fake in-memory implementam isto."""

    def record_creation(
        self,
        measurement_id: MeasurementId,
        spec: MeasurementSpec,
        credit_balance: int | None,
    ) -> None: ...

    def record_snapshot(
        self,
        measurement_id: MeasurementId,
        definition: MeasurementDefinition | None,
        items: Sequence[PingSample | UnusableResult],
        *,
        error: str | None = None,
        credit_balance: int | None = None,
    ) -> CollectReport: ...

    def rebuild(self) -> CollectReport: ...
