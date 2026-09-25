import inspect
from typing import Any

import pytest

from preditor_de_falhas_ml.features import (
    FEATURE_COLUMNS,
    JOIN_KEY_COLUMNS,
    LABEL_COLUMNS,
    LEGACY_CURATED_COLUMNS,
    feature_row,
    label_row,
    row_identity,
    status_real,
)


def _xy(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    features = feature_row(record)
    return features, label_row(features)


def test_public_api_exports_split_not_combined() -> None:
    import preditor_de_falhas_ml as pkg

    assert hasattr(pkg, "feature_row")
    assert hasattr(pkg, "label_row")
    assert hasattr(pkg, "status_real")
    assert not hasattr(pkg, "curated_row")


def test_status_real_order() -> None:
    assert status_real(16.0, 10.0) == "FALHA"
    assert status_real(15.0, 101.0) == "RISCO"
    assert status_real(15.0, 100.0) == "OK"
    assert status_real(0.0, 12.3) == "OK"
    assert status_real(None, 200.0) == "RISCO"
    assert status_real(None, None) == "OK"


def test_feature_schema_excludes_status_real() -> None:
    assert "status_real" not in FEATURE_COLUMNS
    assert "status_real" in LABEL_COLUMNS
    assert JOIN_KEY_COLUMNS == ("msm_id", "timestamp", "prb_id")
    assert FEATURE_COLUMNS[:3] == JOIN_KEY_COLUMNS
    assert LABEL_COLUMNS[:3] == JOIN_KEY_COLUMNS
    assert LABEL_COLUMNS == ("msm_id", "timestamp", "prb_id", "status_real")
    assert LEGACY_CURATED_COLUMNS[-1] == "status_real"
    assert "status_real" not in inspect.getsource(feature_row)
    assert "status_real" in inspect.getsource(label_row)


def test_feature_row_ok_from_ping_fixture(
    ping_results_payload: list[dict[str, Any]],
) -> None:
    features, labels = _xy(ping_results_payload[0])
    assert list(features) == list(FEATURE_COLUMNS)
    assert list(labels) == list(LABEL_COLUMNS)
    assert "status_real" not in features
    assert labels["status_real"] == "OK"
    assert features["latencia_ms"] == 12.3
    assert features["perda_pacotes_pct"] == 0.0
    assert features["jitter_ms"] == 0.0
    assert features["ip"] == "8.8.8.8"
    assert features["prb_id"] == 9
    assert features["msm_id"] == 12345
    assert features["timestamp"] == "2024-03-09T16:00:00+00:00"
    assert features["n_hops"] is None
    assert features["pct_hops_timeout"] is None
    assert features["destino_respondeu"] is True
    assert row_identity(features) == (12345, "2024-03-09T16:00:00+00:00", 9)
    assert row_identity(features) == row_identity(labels)


def test_label_row_risco_high_latency() -> None:
    features, labels = _xy(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 1710000000,
            "dst_addr": "94.140.14.14",
            "sent": 5,
            "rcvd": 5,
            "dup": 0,
            "ttl": 50,
            "result": [{"rtt": 140.0}, {"rtt": 160.0}],
        }
    )
    assert "status_real" not in features
    assert labels["status_real"] == "RISCO"
    assert features["latencia_ms"] == 150.0
    assert features["rtt_min_ms"] == 140.0
    assert features["rtt_max_ms"] == 160.0
    assert features["perda_pacotes_pct"] == 0.0
    assert features["jitter_ms"] == 20.0
    assert row_identity(features) == row_identity(labels)


def test_label_row_falha_high_loss() -> None:
    features, labels = _xy(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 1710000000,
            "dst_addr": "94.140.14.14",
            "sent": 5,
            "rcvd": 4,
            "result": [{"rtt": 10.0}, {"rtt": 12.0}, {"rtt": 11.0}, {"rtt": 9.0}],
        }
    )
    assert features["perda_pacotes_pct"] == 20.0
    assert labels["status_real"] == "FALHA"
    assert features["latencia_ms"] == 10.5
    assert "status_real" not in features
    assert row_identity(features) == row_identity(labels)


def test_label_row_sent_zero_is_falha() -> None:
    features, labels = _xy(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 1710000000,
            "dst_addr": "8.8.8.8",
            "sent": 0,
            "rcvd": 0,
            "result": [],
        }
    )
    assert features["perda_pacotes_pct"] == 100.0
    assert features["latencia_ms"] is None
    assert features["jitter_ms"] == 0.0
    assert labels["status_real"] == "FALHA"
    assert features["destino_respondeu"] is False


def test_feature_row_negative_rtt_is_missing() -> None:
    features, labels = _xy(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 1710000000,
            "dst_addr": "202.12.28.131",
            "sent": 5,
            "rcvd": 0,
            "avg": -1,
            "min": -1,
            "max": -1,
            "result": [{"rtt": -1}, {"rtt": -1}],
        }
    )
    assert features["latencia_ms"] is None
    assert features["rtt_min_ms"] is None
    assert features["rtt_max_ms"] is None
    assert features["perda_pacotes_pct"] == 100.0
    assert labels["status_real"] == "FALHA"


def test_label_row_missing_rtt_keeps_loss_rule() -> None:
    features, labels = _xy(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 1710000000,
            "dst_addr": "8.8.8.8",
            "sent": 5,
            "rcvd": 5,
            "result": [{"x": "*"}, {"x": "*"}],
        }
    )
    assert features["perda_pacotes_pct"] == 0.0
    assert features["latencia_ms"] is None
    assert features["jitter_ms"] == 0.0
    assert labels["status_real"] == "OK"


def test_feature_row_traceroute_hops(
    traceroute_results_payload: list[dict[str, Any]],
) -> None:
    features, labels = _xy(traceroute_results_payload[0])
    assert features["n_hops"] == 3
    assert features["pct_hops_timeout"] == pytest.approx(1 / 3 * 100.0)
    assert features["destino_respondeu"] is True
    assert features["latencia_ms"] == 80.0
    assert features["perda_pacotes_pct"] == 0.0
    assert labels["status_real"] == "OK"
    assert features["dup"] is None
    assert features["ttl"] == 50
    assert row_identity(features) == row_identity(labels)


def test_label_row_traceroute_unanswered_is_falha() -> None:
    features, labels = _xy(
        {
            "type": "traceroute",
            "msm_id": 9,
            "prb_id": 3,
            "timestamp": 1710000000,
            "dst_addr": "202.12.28.131",
            "destination_ip_responded": False,
            "result": [
                {"hop": 1, "result": [{"x": "*"}]},
                {"hop": 2, "result": [{"x": "*"}]},
            ],
        }
    )
    assert features["perda_pacotes_pct"] == 100.0
    assert labels["status_real"] == "FALHA"
    assert features["n_hops"] == 2
    assert features["pct_hops_timeout"] == 100.0
    assert features["latencia_ms"] is None


def test_feature_and_label_join_is_one_to_one(
    ping_results_payload: list[dict[str, Any]],
    traceroute_results_payload: list[dict[str, Any]],
) -> None:
    records = [
        ping_results_payload[0],
        traceroute_results_payload[0],
        {
            "type": "ping",
            "msm_id": 7,
            "prb_id": 8,
            "timestamp": 1710000100,
            "dst_addr": "4.2.2.1",
            "sent": 8,
            "rcvd": 8,
            "result": [{"rtt": 110.0}],
        },
    ]
    pairs = [_xy(record) for record in records]
    keys = [row_identity(features) for features, _labels in pairs]
    assert len(keys) == len(set(keys))
    for features, labels in pairs:
        assert row_identity(features) == row_identity(labels)
        assert "status_real" not in features
        assert set(labels) == set(LABEL_COLUMNS)
