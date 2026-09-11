import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import FakeResponse
from preditor_de_falhas_ml import (
    create_periodic_measurements,
    fetch_measurement,
    fetch_measurement_results,
    stop_measurement,
    write_measurement_ids,
)
from preditor_de_falhas_ml.atlas import (
    API,
    HUB_INTERVAL_SECONDS,
    HUB_SPECS,
    get_data,
    parse_measurement_ids_csv,
    read_measurement_ids,
)

RESULTS_URL = f"{API}measurements/12345/results/"

InstallMock = Callable[
    [Callable[[str, str, dict[str, Any]], object]],
    list[dict[str, Any]],
]


def test_fetch_measurement_results_get_with_window(
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    def responder(method: str, url: str, kwargs: dict[str, Any]) -> object:
        assert method == "GET"
        assert url == RESULTS_URL
        return ping_results_payload

    calls = mock_atlas_request(responder)
    frame = fetch_measurement_results(
        "test-key",
        12345,
        start=1710000000,
        stop=1710000900,
    )

    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == RESULTS_URL
    assert calls[0]["kwargs"]["params"] == {
        "start": 1710000000,
        "stop": 1710000900,
    }
    assert all(call["method"] != "POST" for call in calls)
    assert len(frame) == 1
    assert frame.iloc[0]["msm_id"] == 12345
    assert frame.iloc[0]["type"] == "ping"
    assert frame.iloc[0]["result"] == [{"rtt": 12.3}]


def test_fetch_measurement_results_omits_params_when_unset(
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    def responder(_method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        return ping_results_payload

    calls = mock_atlas_request(responder)
    fetch_measurement_results("test-key", 12345)

    assert "params" not in calls[0]["kwargs"]
    assert calls[0]["method"] == "GET"
    assert all(call["method"] != "POST" for call in calls)


def test_get_data_posts_then_reuses_fetch(
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    def responder(method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        if method == "POST":
            return {"measurements": [12345]}
        return ping_results_payload

    calls = mock_atlas_request(responder)
    frame = get_data("test-key")

    assert [call["method"] for call in calls] == ["POST", "GET"]
    assert calls[0]["url"] == f"{API}measurements/"
    assert calls[0]["kwargs"]["json"]["is_oneoff"] is True
    assert calls[1]["url"] == RESULTS_URL
    assert "params" not in calls[1]["kwargs"]
    assert len(frame) == 1


def test_create_periodic_measurements_posts_hub_matrix(
    mock_atlas_request: InstallMock,
) -> None:
    msm_ids = [101, 102, 103, 104, 105, 106]

    def responder(method: str, url: str, kwargs: dict[str, Any]) -> object:
        assert method == "POST"
        assert url == f"{API}measurements/"
        return {"measurements": msm_ids}

    calls = mock_atlas_request(responder)
    returned = create_periodic_measurements("test-key")

    assert returned == msm_ids
    assert len(calls) == 1
    payload = calls[0]["kwargs"]["json"]
    assert payload["is_oneoff"] is False
    assert payload["probes"] == [{"type": "countries", "value": "BR", "requested": 2}]
    definitions = payload["definitions"]
    assert len(definitions) == 6
    assert [item["target"] for item in definitions] == [
        spec.target for spec in HUB_SPECS
    ]
    assert [item["type"] for item in definitions] == [
        spec.measurement_type for spec in HUB_SPECS
    ]
    assert [item["packets"] for item in definitions] == [
        spec.packets for spec in HUB_SPECS
    ]
    for definition in definitions:
        assert definition["is_oneoff"] is False
        assert definition["interval"] == HUB_INTERVAL_SECONDS
        assert definition["af"] == 4
    pings = [item for item in definitions if item["type"] == "ping"]
    traces = [item for item in definitions if item["type"] == "traceroute"]
    assert len(pings) == 3
    assert len(traces) == 3
    assert all(item["packets"] == 5 for item in pings)
    assert all(item["size"] == 64 for item in pings)
    assert all(item["packets"] == 3 for item in traces)
    assert all(item["protocol"] == "ICMP" for item in traces)
    assert {item["target"] for item in definitions} == {
        "94.140.14.14",
        "208.67.222.222",
        "202.12.28.131",
    }


def test_create_periodic_measurements_rejects_incomplete_response(
    mock_atlas_request: InstallMock,
) -> None:
    def responder(_method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        return {"error": "no credits"}

    mock_atlas_request(responder)
    with pytest.raises(ValueError, match="não devolveu 6 msm_id"):
        create_periodic_measurements("test-key")


def test_fetch_measurement_gets_metadata(mock_atlas_request: InstallMock) -> None:
    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        assert method == "GET"
        assert url == f"{API}measurements/210717688/"
        return {"id": 210717688, "status": {"id": 4, "name": "Stopped"}}

    calls = mock_atlas_request(responder)
    meta = fetch_measurement("test-key", 210717688)

    assert meta["status"]["name"] == "Stopped"
    assert calls[0]["method"] == "GET"
    assert all(call["method"] != "DELETE" for call in calls)


def test_stop_measurement_deletes_and_accepts_204(
    mock_atlas_request: InstallMock,
) -> None:
    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        assert method == "DELETE"
        assert url == f"{API}measurements/210717688/"
        return None

    calls = mock_atlas_request(responder)
    stop_measurement("test-key", 210717688)

    assert [call["method"] for call in calls] == ["DELETE"]
    assert calls[0]["url"] == f"{API}measurements/210717688/"


def test_stop_measurement_rejects_non_204(mock_atlas_request: InstallMock) -> None:
    def responder(_method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        return FakeResponse({"error": "forbidden"}, status_code=403)

    mock_atlas_request(responder)
    with pytest.raises(ValueError, match="HTTP 403"):
        stop_measurement("test-key", 210717688)


def test_write_measurement_ids_omits_api_key(tmp_path: Path) -> None:
    path = tmp_path / "msm_ids.json"
    written = write_measurement_ids([11, 12, 13, 14, 15, 16], output_path=path)
    raw = written.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert "api_key" not in raw
    assert "test-key" not in raw
    assert payload["is_oneoff"] is False
    assert payload["interval"] == 900
    assert [row["msm_id"] for row in payload["measurements"]] == [
        11,
        12,
        13,
        14,
        15,
        16,
    ]
    assert payload["measurements"][0]["target"] == "94.140.14.14"
    assert payload["measurements"][0]["type"] == "ping"
    assert payload["measurements"][5]["target"] == "202.12.28.131"
    assert payload["measurements"][5]["type"] == "traceroute"
    assert read_measurement_ids(written) == [11, 12, 13, 14, 15, 16]


def test_parse_measurement_ids_csv() -> None:
    assert parse_measurement_ids_csv("210717688,210717689") == [210717688, 210717689]
    with pytest.raises(ValueError, match="vazia"):
        parse_measurement_ids_csv("  ,  ")
