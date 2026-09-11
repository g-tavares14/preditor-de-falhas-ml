from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from preditor_de_falhas_ml.cli import main

InstallMock = Callable[
    [Callable[[str, str, dict[str, Any]], object]],
    list[dict[str, Any]],
]


def test_cli_get_results_fetches_window_and_never_posts(
    monkeypatch: pytest.MonkeyPatch,
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")

    def responder(_method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        return ping_results_payload

    def fail_get_data(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("collector must not call get_data")

    calls = mock_atlas_request(responder)
    monkeypatch.setattr("preditor_de_falhas_ml.cli.get_data", fail_get_data)

    code = main(
        [
            "getResults",
            "--msm-id",
            "12345",
            "--start",
            "1710000000",
            "--stop",
            "1710000900",
        ]
    )

    assert code == 0
    assert [call["method"] for call in calls] == ["GET"]
    assert calls[0]["url"].endswith("measurements/12345/results/")
    assert calls[0]["kwargs"]["params"] == {
        "start": 1710000000,
        "stop": 1710000900,
    }
    printed = capsys.readouterr().out
    assert "12345" in printed
    assert "ping" in printed


def test_cli_get_results_does_not_write_without_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")

    def responder(_method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        return ping_results_payload

    mock_atlas_request(responder)
    written: list[object] = []

    def spy_append(*args: object, **kwargs: object) -> None:
        written.append((args, kwargs))

    monkeypatch.setattr("preditor_de_falhas_ml.cli.append_data", spy_append)

    code = main(
        [
            "getResults",
            "--msm-id",
            "12345",
            "--start",
            "1710000000",
            "--stop",
            "1710000900",
        ]
    )

    assert code == 0
    assert written == []
    assert list(tmp_path.rglob("*.jsonl")) == []
    assert not (tmp_path / "data").exists()


def test_cli_get_results_appends_when_output_dir_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")

    def responder(_method: str, _url: str, _kwargs: dict[str, Any]) -> object:
        return ping_results_payload

    mock_atlas_request(responder)
    output_dir = tmp_path / "raw"

    code = main(
        [
            "getResults",
            "--msm-id",
            "12345",
            "--start",
            "1710000000",
            "--stop",
            "1710000900",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert code == 0
    jsonl = output_dir / "measurements.jsonl"
    assert jsonl.exists()
    text = jsonl.read_text(encoding="utf-8")
    assert "12345" in text
    assert "ping" in text


def test_cli_get_results_requires_msm_id_start_stop() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["getResults"])
    assert exc.value.code != 0
