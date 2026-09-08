"""Persistência schema v2: X de três colunas e observação incompleta permanece."""

import json

from fakes import sample
from preditor_de_falhas_ml.adapters.file_dataset import FileDataset, dataset_schema
from preditor_de_falhas_ml.domain.ids import MeasurementId, ObservationKey, ProbeId
from preditor_de_falhas_ml.domain.ping import UnusableResult
from preditor_de_falhas_ml.domain.spec import CountrySelection, MeasurementSpec


def test_schema_separates_x_from_diagnostics():
    schema = dataset_schema()
    assert schema["schema_version"] == 2
    assert schema["x_columns"] == ["latency_ms", "loss_pct", "jitter_rtt_ms"]
    assert "target" not in schema
    assert "rtt_min_ms" in schema["diagnostic_columns"]


def test_roundtrip_keeps_incomplete_row_and_credits(tmp_path):
    store = FileDataset(tmp_path)
    store.prepare()
    spec = MeasurementSpec(
        target="1.1.1.1", address_family=4, selection=CountrySelection("BR")
    )
    store.record_creation(MeasurementId(9), spec, credit_balance=44)
    created = json.loads((tmp_path / "raw.jsonl").read_text().splitlines()[0])
    payload = json.loads(created["payload_json"])
    assert payload["credit_balance"] == 44
    assert payload["configuration"]["target"] == "1.1.1.1"

    report = store.record_snapshot(
        MeasurementId(9),
        None,
        (
            sample([10, 14], msm=9, prb=1, ts=100),
            UnusableResult(
                1,
                "quebrado",
                key=ObservationKey(MeasurementId(9), ProbeId(2), 100),
                destination="1.1.1.1",
                address_family=4,
            ),
            UnusableResult(2, "sem chave"),
        ),
        credit_balance=40,
    )
    assert report.accepted == 2
    assert report.rejected == 1
    assert report.observations[1].quality == "incomplete"
    rebuilt = store.rebuild()
    assert rebuilt.total_rows == 2
    csv_header = (tmp_path / "dataset.csv").read_text().splitlines()[0]
    assert "latency_ms" in csv_header
    assert "credit_balance" in csv_header


def test_schema_v1_is_rejected(tmp_path):
    (tmp_path / "schema.json").write_text(json.dumps({"schema_version": 1}))
    store = FileDataset(tmp_path)
    try:
        store.prepare()
    except ValueError as error:
        assert "schema 2" in str(error).lower() or "versão 1" in str(error)
    else:
        raise AssertionError("schema v1 deveria falhar")
