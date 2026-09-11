import json
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

    def fail_create(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("collector must not call create_periodic_measurements")

    monkeypatch.setattr("preditor_de_falhas_ml.cli.get_data", fail_get_data)
    monkeypatch.setattr(
        "preditor_de_falhas_ml.cli.create_periodic_measurements",
        fail_create,
    )

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


def test_cli_create_periodic_posts_and_prints_credits(
    monkeypatch: pytest.MonkeyPatch,
    mock_atlas_request: InstallMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    balances = iter([100_000, 99_790])

    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        if method == "GET" and url.endswith("credits/"):
            return {"current_balance": next(balances)}
        if method == "POST":
            return {"measurements": [101, 102, 103, 104, 105, 106]}
        raise AssertionError(f"unexpected {method} {url}")

    def fail_get_data(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("createPeriodic must not call get_data")

    calls = mock_atlas_request(responder)
    monkeypatch.setattr("preditor_de_falhas_ml.cli.get_data", fail_get_data)

    code = main(["createPeriodic"])

    assert code == 0
    assert [call["method"] for call in calls] == ["GET", "POST", "GET"]
    assert calls[1]["url"].endswith("measurements/")
    assert calls[1]["kwargs"]["json"]["is_oneoff"] is False
    printed = capsys.readouterr().out
    assert "Créditos antes: 100000" in printed
    assert "Créditos depois: 99790" in printed
    assert "export RIPE_ATLAS_MSM_IDS=101,102,103,104,105,106" in printed
    assert "msm_id=101" in printed
    assert "94.140.14.14" in printed
    assert "202.12.28.131" in printed


def test_cli_create_periodic_writes_ids_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_atlas_request: InstallMock,
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    ids_file = tmp_path / "msm_ids.json"

    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        if method == "GET" and url.endswith("credits/"):
            return {"current_balance": 1}
        return {"measurements": [201, 202, 203, 204, 205, 206]}

    mock_atlas_request(responder)
    code = main(["createPeriodic", "--ids-file", str(ids_file)])

    assert code == 0
    text = ids_file.read_text(encoding="utf-8")
    assert "test-key" not in text
    assert "201" in text
    assert '"is_oneoff": false' in text


def test_cli_create_periodic_wait_uses_existing_fetch(
    monkeypatch: pytest.MonkeyPatch,
    mock_atlas_request: InstallMock,
    ping_results_payload: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    monkeypatch.setattr("preditor_de_falhas_ml.cli.sleep", lambda _seconds: None)
    monkeypatch.setattr("preditor_de_falhas_ml.cli.time", lambda: 1_710_000_900)

    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        if method == "GET" and url.endswith("credits/"):
            return {"current_balance": 50}
        if method == "POST":
            return {"measurements": [301, 302, 303, 304, 305, 306]}
        assert method == "GET"
        assert "/results/" in url
        return ping_results_payload

    calls = mock_atlas_request(responder)
    code = main(["createPeriodic", "--wait-seconds", "900"])

    assert code == 0
    methods = [call["method"] for call in calls]
    assert methods[:3] == ["GET", "POST", "GET"]
    assert methods[3:] == ["GET"] * 6
    assert all("/results/" in call["url"] for call in calls[3:])
    printed = capsys.readouterr().out
    assert "GET msm_id=301 linhas=1" in printed


def test_cli_stop_periodic_uses_env_ids(
    monkeypatch: pytest.MonkeyPatch,
    mock_atlas_request: InstallMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    monkeypatch.setenv("RIPE_ATLAS_MSM_IDS", "210717688,210717689")
    balances = iter([100_000, 100_000])

    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        if method == "GET" and url.endswith("credits/"):
            return {"current_balance": next(balances)}
        if method == "DELETE":
            return None
        if method == "GET" and "/measurements/" in url:
            msm_id = int(url.rstrip("/").split("/")[-1])
            return {"id": msm_id, "status": {"id": 4, "name": "Stopped"}}
        raise AssertionError(f"unexpected {method} {url}")

    def fail_create(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("stopPeriodic must not call create_periodic_measurements")

    def fail_get_data(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("stopPeriodic must not call get_data")

    calls = mock_atlas_request(responder)
    monkeypatch.setattr(
        "preditor_de_falhas_ml.cli.create_periodic_measurements",
        fail_create,
    )
    monkeypatch.setattr("preditor_de_falhas_ml.cli.get_data", fail_get_data)

    code = main(["stopPeriodic"])

    assert code == 0
    methods = [call["method"] for call in calls]
    assert methods == ["GET", "DELETE", "GET", "DELETE", "GET", "GET"]
    assert calls[1]["url"].endswith("measurements/210717688/")
    assert calls[3]["url"].endswith("measurements/210717689/")
    printed = capsys.readouterr().out
    assert "Créditos antes: 100000" in printed
    assert "msm_id=210717688 status=Stopped" in printed
    assert "msm_id=210717689 status=Stopped" in printed
    assert "Créditos depois: 100000" in printed


def test_cli_stop_periodic_reads_ids_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_atlas_request: InstallMock,
) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    ids_file = tmp_path / "msm_ids.json"
    ids_file.write_text(
        json.dumps(
            {
                "measurements": [
                    {"msm_id": 401, "target": "94.140.14.14", "type": "ping"},
                    {"msm_id": 402, "target": "94.140.14.14", "type": "traceroute"},
                ]
            }
        ),
        encoding="utf-8",
    )

    def responder(method: str, url: str, _kwargs: dict[str, Any]) -> object:
        if method == "GET" and url.endswith("credits/"):
            return {"current_balance": 1}
        if method == "DELETE":
            return None
        return {"id": 401, "status": {"id": 4, "name": "Stopped"}}

    calls = mock_atlas_request(responder)
    code = main(["stopPeriodic", "--ids-file", str(ids_file)])

    assert code == 0
    deleted = [call["url"] for call in calls if call["method"] == "DELETE"]
    assert deleted[0].endswith("measurements/401/")
    assert deleted[1].endswith("measurements/402/")


def test_cli_stop_periodic_requires_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    monkeypatch.delenv("RIPE_ATLAS_MSM_IDS", raising=False)
    with pytest.raises(ValueError, match="--ids-file ou RIPE_ATLAS_MSM_IDS"):
        main(["stopPeriodic"])
