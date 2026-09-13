import inspect
import io
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from preditor_de_falhas_ml import collector, handler
from preditor_de_falhas_ml.collector import (
    CURATED_KEY,
    collect_measurements,
    raw_object_key,
)
from preditor_de_falhas_ml.features import CURATED_CSV_COLUMNS


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


def test_collector_and_handler_do_not_post() -> None:
    for module in (collector, handler):
        source = inspect.getsource(module)
        assert "create_periodic_measurements" not in source
        assert "get_data" not in source
        assert "createPeriodic" not in source


def test_collect_writes_raw_and_curated(
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
    assert raw_key in s3.objects
    curated = s3.objects[CURATED_KEY].decode("utf-8")
    header = curated.splitlines()[0]
    assert header.split(",") == list(CURATED_CSV_COLUMNS)
    assert "OK" in curated
    assert "8.8.8.8" in curated
    assert "12345" in curated


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
    assert second["raw_rows"] == 0
    curated_lines = [
        line for line in s3.objects[CURATED_KEY].decode("utf-8").splitlines() if line
    ]
    assert len(curated_lines) == 2


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
    assert CURATED_KEY not in s3.objects
