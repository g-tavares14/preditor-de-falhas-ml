import csv
import inspect
import io
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from preditor_de_falhas_ml import collector, handler
from preditor_de_falhas_ml.collector import (
    FEATURES_KEY,
    LABELS_KEY,
    LEGACY_CURATED_KEY,
    collect_measurements,
    migrate_legacy_curated,
    raw_object_key,
)
from preditor_de_falhas_ml.features import FEATURE_COLUMNS, LABEL_COLUMNS

LEGACY_CSV = (
    "msm_id,timestamp,prb_id,ip,latencia_ms,rtt_min_ms,rtt_max_ms,"
    "perda_pacotes_pct,jitter_ms,ttl,dup,n_hops,destino_respondeu,"
    "pct_hops_timeout,status_real\n"
    "1,2024-03-09T16:00:00+00:00,9,8.8.8.8,12.3,12.3,12.3,0.0,0.0,117,0,,True,,OK\n"
    "2,2024-03-09T16:00:00+00:00,9,94.140.14.14,150.0,140.0,160.0,0.0,20.0,"
    "50,0,,True,,RISCO\n"
    "3,2024-03-09T16:00:00+00:00,9,1.1.1.1,10.5,9.0,12.0,20.0,1.0,50,0,,True,,FALHA\n"
)


class FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise FakeClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key]), "Bucket": Bucket}

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> dict[str, str]:
        self.objects[Key] = Body
        self.puts.append(Key)
        return {"Bucket": Bucket, "ContentType": ContentType}


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _join_keys(rows: list[dict[str, str]]) -> list[tuple[str, str, str]]:
    return [(row["msm_id"], row["timestamp"], row["prb_id"]) for row in rows]


def test_collector_and_handler_do_not_post() -> None:
    for module in (collector, handler):
        source = inspect.getsource(module)
        assert "create_periodic_measurements" not in source
        assert "get_data" not in source
        assert "createPeriodic" not in source


def test_collect_writes_features_and_labels_not_log_rede(
    monkeypatch: pytest.MonkeyPatch,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_fetch(
        api_key: str,
        msm_id: int,
        *,
        start: int | None = None,
        stop: int | None = None,
    ) -> pd.DataFrame:
        assert api_key == "test-key"
        calls.append({"msm_id": msm_id, "start": start, "stop": stop})
        return pd.DataFrame(ping_results_payload)

    monkeypatch.setattr(
        "preditor_de_falhas_ml.collector.fetch_measurement_results",
        fake_fetch,
    )
    s3 = FakeS3()
    summary = collect_measurements(
        "test-key",
        [12345],
        bucket="preditor-falhas-ml",
        start=1710000000,
        stop=1710000900,
        s3_client=s3,
    )

    assert calls == [{"msm_id": 12345, "start": 1710000000, "stop": 1710000900}]
    raw_key = raw_object_key(12345, datetime.fromtimestamp(1710000900, tz=UTC))
    assert summary["raw_keys"] == [raw_key]
    assert summary["raw_rows"] == 1
    assert summary["curated_appended"] == 1
    assert summary["features_key"] == FEATURES_KEY
    assert summary["labels_key"] == LABELS_KEY
    assert raw_key in s3.objects
    assert LEGACY_CURATED_KEY not in s3.objects
    assert LEGACY_CURATED_KEY not in s3.puts

    features_text = s3.objects[FEATURES_KEY].decode("utf-8")
    labels_text = s3.objects[LABELS_KEY].decode("utf-8")
    assert features_text.splitlines()[0].split(",") == list(FEATURE_COLUMNS)
    assert labels_text.splitlines()[0].split(",") == list(LABEL_COLUMNS)
    assert "status_real" not in features_text.splitlines()[0]
    assert "status_real" in labels_text.splitlines()[0]
    assert "8.8.8.8" in features_text
    assert "12345" in features_text
    assert "12345" in labels_text
    assert "OK" in labels_text
    assert "OK" not in features_text.splitlines()[0]

    features = _csv_rows(features_text)
    labels = _csv_rows(labels_text)
    assert _join_keys(features) == _join_keys(labels)
    assert len(features) == 1
    assert "status_real" not in features[0]
    assert labels[0]["status_real"] == "OK"


def test_collect_is_idempotent_on_msm_timestamp_prb(
    monkeypatch: pytest.MonkeyPatch,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    monkeypatch.setattr(
        "preditor_de_falhas_ml.collector.fetch_measurement_results",
        lambda *_args, **_kwargs: pd.DataFrame(ping_results_payload),
    )
    s3 = FakeS3()
    kwargs: dict[str, Any] = {
        "bucket": "preditor-falhas-ml",
        "start": 1710000000,
        "stop": 1710000900,
        "s3_client": s3,
    }
    first = collect_measurements("test-key", [12345], **kwargs)
    second = collect_measurements("test-key", [12345], **kwargs)
    assert first["curated_appended"] == 1
    assert second["curated_appended"] == 0
    assert second["features_appended"] == 0
    assert second["labels_appended"] == 0
    assert second["raw_rows"] == 0
    for key in (FEATURES_KEY, LABELS_KEY):
        lines = [line for line in s3.objects[key].decode("utf-8").splitlines() if line]
        assert len(lines) == 2
    assert LEGACY_CURATED_KEY not in s3.puts


def test_collect_empty_frame_writes_nothing_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "preditor_de_falhas_ml.collector.fetch_measurement_results",
        lambda *_args, **_kwargs: pd.DataFrame(),
    )
    s3 = FakeS3()
    summary = collect_measurements(
        "test-key",
        [99],
        bucket="preditor-falhas-ml",
        start=1,
        stop=2,
        s3_client=s3,
    )
    assert summary["raw_rows"] == 0
    assert summary["curated_appended"] == 0
    assert summary["legacy_migrated"] == 0
    assert FEATURES_KEY not in s3.objects
    assert LABELS_KEY not in s3.objects
    assert LEGACY_CURATED_KEY not in s3.objects


def test_migrate_legacy_log_rede_is_noop_when_missing() -> None:
    s3 = FakeS3()
    summary = migrate_legacy_curated(s3, "preditor-falhas-ml")
    assert summary["source_found"] is False
    assert summary["source_rows"] == 0
    assert summary["features_appended"] == 0
    assert summary["labels_appended"] == 0
    assert FEATURES_KEY not in s3.objects
    assert LABELS_KEY not in s3.objects
    assert s3.puts == []


def test_migrate_legacy_log_rede_splits_ok_risco_falha() -> None:
    s3 = FakeS3()
    s3.objects[LEGACY_CURATED_KEY] = LEGACY_CSV.encode("utf-8")
    first = migrate_legacy_curated(s3, "preditor-falhas-ml")
    assert first["source_found"] is True
    assert first["source_rows"] == 3
    assert first["features_appended"] == 3
    assert first["labels_appended"] == 3
    assert LEGACY_CURATED_KEY not in s3.puts
    assert s3.objects[LEGACY_CURATED_KEY] == LEGACY_CSV.encode("utf-8")

    features = _csv_rows(s3.objects[FEATURES_KEY].decode("utf-8"))
    labels = _csv_rows(s3.objects[LABELS_KEY].decode("utf-8"))
    assert _join_keys(features) == _join_keys(labels)
    assert [row["status_real"] for row in labels] == ["OK", "RISCO", "FALHA"]
    assert all("status_real" not in row for row in features)
    assert list(features[0]) == list(FEATURE_COLUMNS)
    assert list(labels[0]) == list(LABEL_COLUMNS)

    second = migrate_legacy_curated(s3, "preditor-falhas-ml")
    assert second["features_appended"] == 0
    assert second["labels_appended"] == 0
    assert len(_csv_rows(s3.objects[FEATURES_KEY].decode("utf-8"))) == 3
    assert len(_csv_rows(s3.objects[LABELS_KEY].decode("utf-8"))) == 3


def test_collect_migrates_legacy_then_appends_without_rewriting_log_rede(
    monkeypatch: pytest.MonkeyPatch,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    monkeypatch.setattr(
        "preditor_de_falhas_ml.collector.fetch_measurement_results",
        lambda *_args, **_kwargs: pd.DataFrame(ping_results_payload),
    )
    s3 = FakeS3()
    s3.objects[LEGACY_CURATED_KEY] = LEGACY_CSV.encode("utf-8")
    summary = collect_measurements(
        "test-key",
        [12345],
        bucket="preditor-falhas-ml",
        start=1710000000,
        stop=1710000900,
        s3_client=s3,
    )
    assert summary["legacy_migrated"] == 3
    assert summary["curated_appended"] == 1
    assert LEGACY_CURATED_KEY not in s3.puts
    features = _csv_rows(s3.objects[FEATURES_KEY].decode("utf-8"))
    labels = _csv_rows(s3.objects[LABELS_KEY].decode("utf-8"))
    assert _join_keys(features) == _join_keys(labels)
    assert len(features) == 4
    assert {row["status_real"] for row in labels} == {"OK", "RISCO", "FALHA"}
    assert "status_real" not in features[0]
