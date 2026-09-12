import logging
from typing import Any

import pytest

from preditor_de_falhas_ml.handler import lambda_handler, parse_secret_string


class FakeSecrets:
    def __init__(self, secret_string: str) -> None:
        self.secret_string = secret_string
        self.calls: list[str] = []

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        self.calls.append(SecretId)
        return {"SecretString": self.secret_string}


def test_parse_secret_string_raw_and_json() -> None:
    assert parse_secret_string("plain-key") == "plain-key"
    assert parse_secret_string('{"RIPE_ATLAS_API_KEY":"json-key"}') == "json-key"
    assert parse_secret_string('{"api_key":"alt"}') == "alt"


def test_lambda_handler_uses_collector_and_never_logs_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("S3_BUCKET", "preditor-falhas-ml")
    monkeypatch.setenv("RIPE_ATLAS_MSM_IDS", "210717688,210717689")
    monkeypatch.setenv("SECRET_NAME", "RIPE_ATLAS_API_KEY")
    monkeypatch.delenv("COLLECT_WINDOW_SECONDS", raising=False)

    seen: list[dict[str, Any]] = []

    def fake_collect(
        api_key: str,
        msm_ids: list[int],
        *,
        bucket: str,
        start: int,
        stop: int,
        s3_client: object,
    ) -> dict[str, Any]:
        seen.append(
            {
                "api_key": api_key,
                "msm_ids": msm_ids,
                "bucket": bucket,
                "start": start,
                "stop": stop,
                "s3_client": s3_client,
            }
        )
        return {
            "raw_rows": 2,
            "curated_appended": 2,
            "raw_keys": ["raw/measurements/x.jsonl"],
        }

    monkeypatch.setattr(
        "preditor_de_falhas_ml.handler.collect_measurements",
        fake_collect,
    )
    secrets = FakeSecrets("super-secret-atlas-key")
    s3 = object()

    with caplog.at_level(logging.INFO):
        summary = lambda_handler(
            {},
            None,
            secrets_client=secrets,
            s3_client=s3,
            now=1_800_000_000,
        )

    assert seen[0]["api_key"] == "super-secret-atlas-key"
    assert seen[0]["msm_ids"] == [210717688, 210717689]
    assert seen[0]["start"] == 1_800_000_000 - 1200
    assert seen[0]["stop"] == 1_800_000_000
    assert summary["raw_rows"] == 2
    assert secrets.calls == ["RIPE_ATLAS_API_KEY"]
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "super-secret-atlas-key" not in logged
    assert "210717688" in logged


def test_lambda_handler_event_overrides_window_and_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("S3_BUCKET", "preditor-falhas-ml")
    monkeypatch.setenv("RIPE_ATLAS_MSM_IDS", "1,2,3")
    captured: dict[str, Any] = {}

    def fake_collect(
        api_key: str,
        msm_ids: list[int],
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["api_key"] = api_key
        captured["msm_ids"] = msm_ids
        captured.update(kwargs)
        return {"raw_rows": 0, "curated_appended": 0, "raw_keys": []}

    monkeypatch.setattr(
        "preditor_de_falhas_ml.handler.collect_measurements",
        fake_collect,
    )
    lambda_handler(
        {
            "msm_ids": "210717688",
            "start": 1789160000,
            "stop": 1789170000,
        },
        None,
        secrets_client=FakeSecrets("k"),
        s3_client=object(),
    )
    assert captured["msm_ids"] == [210717688]
    assert captured["start"] == 1789160000
    assert captured["stop"] == 1789170000
