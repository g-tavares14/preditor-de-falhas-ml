from typing import Any

import pytest

from preditor_de_falhas_ml.features import (
    CURATED_COLUMNS,
    curated_row,
    row_identity,
    status_real,
)


def test_status_real_order() -> None:
    assert status_real(16.0, 10.0) == "FALHA"
    assert status_real(15.0, 101.0) == "RISCO"
    assert status_real(15.0, 100.0) == "OK"
    assert status_real(0.0, 12.3) == "OK"
    assert status_real(None, 200.0) == "RISCO"
    assert status_real(None, None) == "OK"


def test_curated_row_ok_from_ping_fixture(
    ping_results_payload: list[dict[str, Any]],
) -> None:
    row = curated_row(ping_results_payload[0])
    assert all(column in row for column in CURATED_COLUMNS)
    assert row["status_real"] == "OK"
    assert row["latencia_ms"] == 12.3
    assert row["perda_pacotes_pct"] == 0.0
    assert row["jitter_ms"] == 0.0
    assert row["ip"] == "8.8.8.8"
    assert row["prb_id"] == 9
    assert row["msm_id"] == 12345
    assert row["timestamp"] == "2024-03-09T16:00:00+00:00"
    assert row["n_hops"] is None
    assert row["pct_hops_timeout"] is None
    assert row["destino_respondeu"] is True
    assert row_identity(row) == (12345, "2024-03-09T16:00:00+00:00", 9)


def test_curated_row_risco_high_latency() -> None:
    row = curated_row(
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
    assert row["status_real"] == "RISCO"
    assert row["latencia_ms"] == 150.0
    assert row["rtt_min_ms"] == 140.0
    assert row["rtt_max_ms"] == 160.0
    assert row["perda_pacotes_pct"] == 0.0
    assert row["jitter_ms"] == 20.0


def test_curated_row_falha_high_loss() -> None:
    row = curated_row(
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
    assert row["perda_pacotes_pct"] == 20.0
    assert row["status_real"] == "FALHA"
    assert row["latencia_ms"] == 10.5


def test_curated_row_sent_zero_is_falha() -> None:
    row = curated_row(
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
    assert row["perda_pacotes_pct"] == 100.0
    assert row["latencia_ms"] is None
    assert row["jitter_ms"] == 0.0
    assert row["status_real"] == "FALHA"
    assert row["destino_respondeu"] is False


def test_curated_row_negative_rtt_is_missing() -> None:
    row = curated_row(
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
    assert row["latencia_ms"] is None
    assert row["rtt_min_ms"] is None
    assert row["rtt_max_ms"] is None
    assert row["perda_pacotes_pct"] == 100.0
    assert row["status_real"] == "FALHA"


def test_curated_row_missing_rtt_keeps_loss_rule() -> None:
    row = curated_row(
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
    assert row["perda_pacotes_pct"] == 0.0
    assert row["latencia_ms"] is None
    assert row["jitter_ms"] == 0.0
    assert row["status_real"] == "OK"


def test_curated_row_traceroute_hops(
    traceroute_results_payload: list[dict[str, Any]],
) -> None:
    row = curated_row(traceroute_results_payload[0])
    assert row["n_hops"] == 3
    assert row["pct_hops_timeout"] == pytest.approx(1 / 3 * 100.0)
    assert row["destino_respondeu"] is True
    assert row["latencia_ms"] == 80.0
    assert row["perda_pacotes_pct"] == 0.0
    assert row["status_real"] == "OK"
    assert row["dup"] is None
    assert row["ttl"] == 50


def test_curated_row_traceroute_unanswered_is_falha() -> None:
    row = curated_row(
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
    assert row["perda_pacotes_pct"] == 100.0
    assert row["status_real"] == "FALHA"
    assert row["n_hops"] == 2
    assert row["pct_hops_timeout"] == 100.0
    assert row["latencia_ms"] is None
