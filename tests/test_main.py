"""Entrada no terminal com HTTP simulado, sem consumir créditos."""

import json
import runpy
import sys
from unittest.mock import patch

import pytest
import requests

from preditor_de_falhas_ml.adapters.cli import main


@pytest.fixture(autouse=True)
def working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("RIPE_ATLAS_API_KEY", "test-key")
    with patch("requests.Session.send") as send:

        def route(request, **kwargs):
            parts = request.url.split("?")[0].rstrip("/").split("/")
            if request.method == "GET" and parts[-2] == "measurements":
                return response(
                    {
                        "id": int(parts[-1]),
                        "type": "ping",
                        "af": 4,
                        "target": "8.8.8.8",
                        "size": 64,
                    }
                )
            return send.return_value

        send.side_effect = route
        yield send


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    return result


def test_no_arguments_show_help_without_credentials_or_http(monkeypatch, http, capsys):
    monkeypatch.delenv("RIPE_ATLAS_API_KEY")
    assert main([]) == 0
    output = capsys.readouterr()
    assert "create-sample" in output.out
    assert "results" in output.out
    assert output.err == ""
    http.assert_not_called()


def test_python_module_entry_point_shows_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["preditor_de_falhas_ml", "--help"])
    monkeypatch.delitem(sys.modules, "preditor_de_falhas_ml.__main__", raising=False)
    with patch("requests.Session") as session, pytest.raises(SystemExit) as caught:
        runpy.run_module("preditor_de_falhas_ml", run_name="__main__")
    assert caught.value.code == 0
    assert "credits" in capsys.readouterr().out
    session.assert_not_called()


@pytest.mark.parametrize("key", [None, "", "invalid key"])
def test_missing_or_invalid_key_fails_before_http(monkeypatch, http, capsys, key):
    if key is None:
        monkeypatch.delenv("RIPE_ATLAS_API_KEY")
    else:
        monkeypatch.setenv("RIPE_ATLAS_API_KEY", key)
    assert main(["credits"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Erro:" in output.err
    if key:
        assert key not in output.err
    http.assert_not_called()


def test_results_work_without_api_key(monkeypatch, http, capsys):
    monkeypatch.delenv("RIPE_ATLAS_API_KEY")
    http.return_value = response([])
    assert main(["results", "12345"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    for call in http.call_args_list:
        assert "Authorization" not in call.args[0].headers


@pytest.mark.parametrize(
    "argv",
    [
        ["unknown"],
        ["create-sample"],
        ["create-sample", "--country-code", "BR", "--probe-count", "two"],
        ["results"],
        ["results", "abc"],
        ["features"],
        ["features", "abc"],
    ],
)
def test_invalid_syntax_fails_before_http(http, capsys, argv):
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == 2
    assert capsys.readouterr().out == ""
    http.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "invalid_value"),
    [
        (["create-sample", "--country-code", "BRA"], "BRA"),
        (["create-sample", "--country-code", "BR", "--probe-count", "0"], "0"),
        (["create-sample", "--country-code", "BR", "--packets", "17"], "17"),
        (["results", "-1"], "-1"),
        (["features", "0"], "0"),
        (["create-sample", "--country-code", "BR", "--interval", "60"], "interval"),
    ],
)
def test_invalid_values_fail_before_http(http, capsys, argv, invalid_value):
    assert main(argv) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert invalid_value in output.err
    http.assert_not_called()


def test_credits_print_zero_balance_and_close_session(http, capsys):
    http.return_value = response({"current_balance": 0})
    with patch("requests.Session.close") as close:
        assert main(["credits"]) == 0
    assert capsys.readouterr() == ("Créditos: 0\n", "")
    close.assert_called_once()
    http.assert_called_once()
    assert http.call_args.args[0].url.endswith("/credits/")
    assert http.call_args.args[0].headers["Authorization"] == "Key test-key"


@pytest.mark.parametrize(
    ("options", "probes", "packets", "target"),
    [
        ([], 1, 16, "8.8.8.8"),
        (
            ["--probe-count", "2", "--packets", "4", "--target", "1.1.1.1"],
            2,
            4,
            "1.1.1.1",
        ),
    ],
)
def test_creation_passes_parameters_and_prints_id_without_polling(
    http, capsys, options, probes, packets, target
):
    http.return_value = response({"measurements": [12345]}, 201)
    assert main(["create-sample", "--country-code", "br", *options]) == 0
    assert capsys.readouterr() == ("ID da medição: 12345\n", "")
    posted = [
        call.args[0] for call in http.call_args_list if call.args[0].method == "POST"
    ]
    assert len(posted) == 1
    payload = json.loads(posted[0].body)
    assert payload["probes"] == [
        {"type": "countries", "value": "BR", "requested": probes}
    ]
    assert payload["definitions"][0]["packets"] == packets
    assert payload["definitions"][0]["target"] == target


def test_recurring_create_sends_interval_and_duration(http, capsys):
    http.return_value = response({"measurements": [9]}, 201)
    assert (
        main(
            [
                "create-sample",
                "--country-code",
                "BR",
                "--interval",
                "300",
                "--duration",
                "60",
            ]
        )
        == 0
    )
    posted = [
        call.args[0] for call in http.call_args_list if call.args[0].method == "POST"
    ]
    payload = json.loads(posted[0].body)
    assert payload["is_oneoff"] is False
    assert payload["interval"] == 300
    assert payload["stop_time"] > 0
    assert capsys.readouterr().out == "ID da medição: 9\n"


def test_results_print_valid_json_preserving_raw_fields(http, capsys):
    results = [
        {
            "type": "ping",
            "msm_id": 12345,
            "prb_id": 1,
            "timestamp": 100,
            "af": 4,
            "dst_addr": "8.8.8.8",
            "sent": 1,
            "rcvd": 1,
            "result": [{"rtt": 10}],
            "future_field": {"ação": None},
        }
    ]
    http.return_value = response(results)
    assert main(["results", "12345"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == results
    assert output.err == ""


@pytest.mark.parametrize("status", [401, 429, 503])
def test_http_failure_goes_to_stderr_without_response_body_or_retry(
    http, capsys, status
):
    http.return_value = response({"detail": "test-key"}, status)
    assert main(["create-sample", "--country-code", "BR"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert f"HTTP {status}" in output.err
    assert "antes de reenviar" in output.err
    assert "test-key" not in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize(
    "error_type",
    [requests.Timeout, requests.ConnectionError, requests.RequestException],
)
def test_transport_failure_does_not_expose_diagnostics_or_repeat_creation(
    http, capsys, error_type
):
    http.side_effect = error_type("transport diagnostic containing test-key")
    with patch("requests.Session.close") as close:
        assert main(["create-sample", "--country-code", "BR"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "antes de reenviar" in output.err
    assert "test-key" not in output.err
    assert "Traceback" not in output.err
    close.assert_called_once()


def test_invalid_api_response_is_reported_as_error(http, capsys):
    http.return_value = response({"current_balance": "invalid"})
    assert main(["credits"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "current_balance" in output.err
    assert "Traceback" not in output.err


def test_features_keep_each_probe_and_timestamp_separate(http, capsys):
    base = {
        "type": "ping",
        "msm_id": 209319472,
        "af": 4,
        "dst_addr": "8.8.8.8",
        "sent": 2,
        "rcvd": 2,
        "result": [{"rtt": 10}, {"rtt": 14}],
    }
    http.return_value = response(
        [
            {**base, "prb_id": 1, "timestamp": 100},
            {**base, "prb_id": 2, "timestamp": 100},
            {**base, "prb_id": 1, "timestamp": 200},
        ]
    )
    assert main(["features", "209319472"]) == 0
    output = capsys.readouterr()
    rows = json.loads(output.out)
    assert [(row["prb_id"], row["timestamp"]) for row in rows] == [
        (1, 100),
        (2, 100),
        (1, 200),
    ]
    for row in rows:
        assert row["msm_id"] == 209319472
        assert [row["latency_ms"], row["loss_pct"], row["jitter_rtt_ms"]] == [12, 0, 4]


def test_features_keep_incomplete_and_reject_only_without_key(http, capsys):
    valid = {
        "type": "ping",
        "msm_id": 42,
        "prb_id": 1,
        "timestamp": 100,
        "af": 4,
        "dst_addr": "8.8.8.8",
        "sent": 1,
        "rcvd": 1,
        "result": [{"rtt": 10}],
    }
    http.return_value = response([valid, {"not": "a ping"}])
    assert main(["features", "42"]) == 1
    output = capsys.readouterr()
    assert [row["prb_id"] for row in json.loads(output.out)] == [1]
    assert "Registro rejeitado" in output.err
    assert "Traceback" not in output.err
