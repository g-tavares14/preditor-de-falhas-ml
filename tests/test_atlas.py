from collections.abc import Callable
from typing import Any

from preditor_de_falhas_ml import fetch_measurement_results
from preditor_de_falhas_ml.atlas import API, get_data

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
    assert calls[1]["url"] == RESULTS_URL
    assert "params" not in calls[1]["kwargs"]
    assert len(frame) == 1
