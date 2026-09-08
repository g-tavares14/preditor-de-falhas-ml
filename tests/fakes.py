"""Adapters in-memory para testar use cases sem HTTP e sem filesystem."""

from preditor_de_falhas_ml.application.ports import (
    CollectReport,
    GatewaySnapshot,
    SnapshotRecord,
)
from preditor_de_falhas_ml.application.project import project_events
from preditor_de_falhas_ml.domain.ids import MeasurementId, ObservationKey, ProbeId
from preditor_de_falhas_ml.domain.ping import (
    PacketError,
    PingSample,
    Reply,
    Timeout,
    UnusableResult,
)
from preditor_de_falhas_ml.domain.spec import (
    MeasurementDefinition,
    MeasurementSpec,
    ResultFilters,
)


def sample(
    rtts,
    *,
    prb=1000173,
    ts=1788882988,
    msm=209319472,
    dup=0,
    dst="8.8.8.8",
    af=4,
):
    packets = []
    for item in rtts:
        if item == "*":
            packets.append(Timeout())
        elif isinstance(item, str):
            packets.append(PacketError(item))
        else:
            packets.append(Reply(item))
    return PingSample(
        key=ObservationKey(MeasurementId(msm), ProbeId(prb), ts),
        destination=dst,
        address_family=af,
        destination_source="result",
        sent=len(packets),
        received=sum(isinstance(packet, Reply) for packet in packets),
        duplicates=dup,
        packets=tuple(packets),
    )


class FakeGateway:
    def __init__(self) -> None:
        self.created: list[MeasurementSpec] = []
        self.credits = 10
        self.credits_error: Exception | None = None
        self.fail_load: Exception | None = None
        self.last_filters: ResultFilters | None = None
        self.snapshots: dict[int, GatewaySnapshot] = {}
        self.next_id = 12345

    def create(self, spec: MeasurementSpec) -> MeasurementId:
        self.created.append(spec)
        return MeasurementId(self.next_id)

    def get_credits(self) -> int:
        if self.credits_error is not None:
            raise self.credits_error
        return self.credits

    def load_snapshot(
        self, measurement_id: MeasurementId, filters: ResultFilters
    ) -> GatewaySnapshot:
        self.last_filters = filters
        if self.fail_load is not None:
            raise self.fail_load
        return self.snapshots[measurement_id.value]


class MemoryDataset:
    def __init__(self) -> None:
        self.creations: list[tuple[MeasurementId, MeasurementSpec, int | None]] = []
        self.records: list[SnapshotRecord] = []
        self._n = 0

    def record_creation(
        self,
        measurement_id: MeasurementId,
        spec: MeasurementSpec,
        credit_balance: int | None,
    ) -> None:
        self.creations.append((measurement_id, spec, credit_balance))

    def record_snapshot(
        self,
        measurement_id: MeasurementId,
        definition: MeasurementDefinition | None,
        items: tuple[PingSample | UnusableResult, ...]
        | list[PingSample | UnusableResult],
        *,
        error: str | None = None,
        credit_balance: int | None = None,
    ) -> CollectReport:
        del definition
        self._n += 1
        record = SnapshotRecord(
            measurement_id=measurement_id,
            event_id=f"e{self._n}",
            collected_at=f"t{self._n}",
            items=tuple(items),
            error=error,
            credit_balance=credit_balance,
        )
        self.records.append(record)
        return self._report(
            record, state="request_failed" if error else "results_present"
        )

    def rebuild(self) -> CollectReport:
        rows, rejected = project_events(self.records)
        return CollectReport(
            measurement_id=None
            if not self.records
            else self.records[-1].measurement_id.value,
            state="rebuild",
            total_rows=len(rows),
            total_rejected=len(rejected),
            accepted=len(rows),
            rejected=len(rejected),
            observations=tuple(rows),
            rejections=tuple(rejected),
        )

    def _report(self, current: SnapshotRecord | None, *, state: str) -> CollectReport:
        rows, rejected = project_events(self.records)
        current_id = None if current is None else current.event_id
        current_rows = tuple(row for row in rows if row.source_event_id == current_id)
        current_errors = tuple(
            item for item in rejected if item.source_event_id == current_id
        )
        return CollectReport(
            measurement_id=None if current is None else current.measurement_id.value,
            state=state,
            total_rows=len(rows),
            total_rejected=len(rejected),
            accepted=len(current_rows),
            rejected=len(current_errors),
            observations=current_rows,
            rejections=current_errors,
            credit_balance=None if current is None else current.credit_balance,
        )
