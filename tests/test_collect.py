"""Use cases de criação e coleta contra fakes, sem requests nem arquivos."""

from fakes import FakeGateway, MemoryDataset, sample
from preditor_de_falhas_ml.application.collect import collect_measurement
from preditor_de_falhas_ml.application.create import create_measurement
from preditor_de_falhas_ml.application.ports import GatewayError, GatewaySnapshot
from preditor_de_falhas_ml.domain.ids import MeasurementId, ObservationKey, ProbeId
from preditor_de_falhas_ml.domain.ping import (
    PingSample,
    Timeout,
    UnusableResult,
    features_from_sample,
)
from preditor_de_falhas_ml.domain.spec import (
    CountrySelection,
    MeasurementDefinition,
    MeasurementSpec,
    ResultFilters,
)


def _spec(**kwargs) -> MeasurementSpec:
    return MeasurementSpec(
        target=kwargs.get("target", "8.8.8.8"),
        address_family=kwargs.get("address_family", 4),
        selection=CountrySelection("BR", kwargs.get("probe_count", 1)),
        packets=kwargs.get("packets", 16),
        interval=kwargs.get("interval"),
        duration=kwargs.get("duration"),
    )


def test_create_records_spec_and_credit_balance():
    gateway = FakeGateway()
    store = MemoryDataset()
    identifier = create_measurement(gateway, store, _spec(target="1.1.1.1", packets=4))
    assert identifier.value == 12345
    assert gateway.created[0].target == "1.1.1.1"
    assert store.creations[0][2] == 10


def test_create_keeps_id_when_credits_fail():
    gateway = FakeGateway()
    gateway.credits_error = GatewayError("credits down")
    store = MemoryDataset()
    create_measurement(gateway, store, _spec())
    assert store.creations[0][2] is None


def test_collect_computes_x_and_forwards_filters():
    gateway = FakeGateway()
    ping = sample([10, 14])
    gateway.snapshots[42] = GatewaySnapshot(
        MeasurementDefinition(MeasurementId(42), "ping", "1.1.1.1", 4),
        (ping,),
        ({"raw": True},),
    )
    store = MemoryDataset()
    report = collect_measurement(
        gateway,
        store,
        MeasurementId(42),
        ResultFilters(probe_id=ProbeId(7), start=1, stop=2),
    )
    assert gateway.last_filters.probe_id.value == 7
    assert report.raw_results == ({"raw": True},)
    assert report.credit_balance == 10
    row = report.observations[0]
    assert row.features.as_dict() == features_from_sample(ping).features.as_dict()
    assert row.credit_balance == 10


def test_incomplete_result_with_key_stays_in_x():
    gateway = FakeGateway()
    key = ObservationKey(MeasurementId(42), ProbeId(2), 100)
    gateway.snapshots[42] = GatewaySnapshot(
        None,
        (
            sample([10], msm=42, prb=1, ts=100),
            UnusableResult(1, "pacote quebrado", key=key, destination="8.8.8.8"),
            UnusableResult(2, "sem chave"),
        ),
        (),
    )
    report = collect_measurement(gateway, MemoryDataset(), MeasurementId(42))
    assert [row.key.probe_id.value for row in report.observations] == [1, 2]
    incomplete = report.observations[1]
    assert incomplete.quality == "incomplete"
    assert incomplete.features.latency_ms is None
    assert report.rejected == 1
    assert report.rejections[0].reason == "sem chave"


def test_latest_snapshot_wins_and_failed_fetch_does_not_erase():
    store = MemoryDataset()
    gateway = FakeGateway()
    first = sample([10, 12], msm=1, prb=1, ts=100)
    gateway.snapshots[1] = GatewaySnapshot(None, (first,), ())
    collect_measurement(gateway, store, MeasurementId(1))
    gateway.snapshots[1] = GatewaySnapshot(
        None, (sample([20, 22], msm=1, prb=1, ts=100),), ()
    )
    collect_measurement(gateway, store, MeasurementId(1))
    gateway.fail_load = GatewayError("rede")
    try:
        collect_measurement(gateway, store, MeasurementId(1))
    except GatewayError:
        pass
    rebuilt = store.rebuild()
    assert rebuilt.observations[0].features.latency_ms == 21.0


def test_timeout_row_is_kept_with_null_latency():
    gateway = FakeGateway()
    ping = PingSample(
        key=ObservationKey(MeasurementId(5), ProbeId(1), 1),
        destination="8.8.8.8",
        address_family=4,
        destination_source="result",
        sent=1,
        received=0,
        duplicates=0,
        packets=(Timeout(),),
    )
    gateway.snapshots[5] = GatewaySnapshot(None, (ping,), ())
    report = collect_measurement(gateway, MemoryDataset(), MeasurementId(5))
    assert report.observations[0].features.latency_ms is None
    assert report.observations[0].features.loss_pct == 100.0
    assert report.rejected == 0
