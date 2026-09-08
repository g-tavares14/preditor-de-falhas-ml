"""Contrato HTTP do cliente Atlas, sem rede ou consumo de créditos."""

import json
import traceback
from unittest.mock import patch

import pytest
import requests

from preditor_de_falhas_ml import AtlasClient


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    result.headers["Content-Type"] = "application/json"
    return result


@pytest.fixture
def http():
    with patch("requests.Session.send") as send:
        yield send


def test_authenticated_flow_preserves_raw_results(http):
    raw_results = [
        {
            "msm_id": 12345,
            "prb_id": 678,
            "dst_addr": "8.8.8.8",
            "timestamp": 1788800000,
            "sent": 3,
            "rcvd": 2,
            "result": [{"rtt": 12.3}, {"x": "*"}, {"rtt": 14.8}],
            "future_field": {"value": None},
        }
    ]
    http.side_effect = [
        response({"current_balance": 0}),
        response({"measurements": [12345]}, 201),
        response(raw_results),
    ]
    with AtlasClient("test-key", timeout=12.5) as atlas:
        assert atlas.get_credits() == 0
        measurement_id = atlas.create_sample(
            country_code=" br ", probe_count=2, packets=4
        )
        assert measurement_id == 12345
        results = atlas.get_results(measurement_id)
        assert results == raw_results
        assert json.loads(json.dumps(results)) == raw_results

    assert http.call_count == 3
    credits, creation, results = [call.args[0] for call in http.call_args_list]
    assert credits.method == "GET"
    assert credits.url == "https://atlas.ripe.net/api/v2/credits/"
    assert credits.body is None
    assert creation.method == "POST"
    assert creation.url == "https://atlas.ripe.net/api/v2/measurements/"
    assert creation.headers["Content-Type"] == "application/json"
    assert json.loads(creation.body) == {
        "definitions": [
            {
                "target": "8.8.8.8",
                "af": 4,
                "type": "ping",
                "description": "Preditor de falhas ML - ping 8.8.8.8",
                "packets": 4,
            }
        ],
        "probes": [{"type": "countries", "value": "BR", "requested": 2}],
        "is_oneoff": True,
    }
    assert results.method == "GET"
    assert results.url == "https://atlas.ripe.net/api/v2/measurements/12345/results/"
    for call in http.call_args_list:
        prepared = call.args[0]
        assert prepared.headers["Authorization"] == "Key test-key"
        assert prepared.headers["Accept"] == "application/json"
        assert "test-key" not in prepared.url
        assert call.kwargs["timeout"] == 12.5
        assert call.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("netrc_host", ["default", "machine atlas.ripe.net"])
def test_explicit_key_overrides_netrc_and_preserves_environment(
    http, monkeypatch, tmp_path, netrc_host
):
    netrc = tmp_path / ".netrc"
    netrc.write_text(f"{netrc_host} login ignored-user password ignored-password\n")
    netrc.chmod(0o600)
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("https_proxy", "http://proxy.example:8080")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    ca_bundle = tmp_path / "ca.pem"
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_bundle))
    http.side_effect = [
        response({"current_balance": 123}),
        response({"measurements": [42]}, 201),
        response([]),
    ]

    with AtlasClient("test-key") as atlas:
        assert atlas.get_credits() == 123
        measurement_id = atlas.create_sample(country_code="BR")
        assert atlas.get_results(measurement_id) == []

    assert http.call_count == 3
    for call in http.call_args_list:
        assert call.args[0].headers["Authorization"] == "Key test-key"
        assert call.kwargs["proxies"]["https"] == "http://proxy.example:8080"
        assert call.kwargs["verify"] == str(ca_bundle)


def test_sample_defaults_and_no_polling(http):
    http.return_value = response({"measurements": [42]}, 201)
    with AtlasClient("test-key") as atlas:
        assert atlas.create_sample(country_code="BR") == 42
    http.assert_called_once()
    payload = json.loads(http.call_args.args[0].body)
    assert payload["definitions"][0]["packets"] == 3
    assert payload["probes"][0]["requested"] == 1
    assert http.call_args.kwargs["timeout"] == 30.0


def test_empty_results_are_valid(http):
    http.return_value = response([])
    with AtlasClient("test-key") as atlas:
        assert atlas.get_results(42) == []


@pytest.mark.parametrize("status", [301, 400, 401, 403, 404, 429, 500, 503])
def test_http_errors_include_status_without_exposing_key_or_retrying(http, status):
    http.return_value = response({"detail": "test-key"}, status)
    http.return_value.headers["Retry-After"] = "60"
    with AtlasClient("test-key") as atlas:
        with pytest.raises(requests.HTTPError, match=f"HTTP {status}") as caught:
            atlas.create_sample(country_code="BR")
    assert "test-key" not in str(caught.value)
    assert "POST /measurements/" in str(caught.value)
    assert "antes de reenviar" in str(caught.value)
    assert caught.value.response is http.return_value
    assert caught.value.response.headers["Retry-After"] == "60"
    http.assert_called_once()


@pytest.mark.parametrize(
    "error_type",
    [
        requests.Timeout,
        requests.ReadTimeout,
        requests.ConnectTimeout,
        requests.ConnectionError,
        requests.exceptions.SSLError,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.InvalidHeader,
        requests.RequestException,
    ],
)
def test_network_errors_preserve_original_diagnostics_and_do_not_repeat_post(
    http, error_type
):
    prepared = requests.Request("POST", "https://atlas.ripe.net/api/v2/measurements/")
    prepared = prepared.prepare()
    original = error_type("Original transport diagnostic", request=prepared)
    cause = OSError("Original underlying cause")
    original.__cause__ = cause
    http.side_effect = original
    with AtlasClient("test-key") as atlas:
        with pytest.raises(error_type) as caught:
            atlas.create_sample(country_code="BR")
    assert caught.value is original
    assert caught.value.request is prepared
    assert caught.value.__cause__ is cause
    assert str(caught.value) == "Original transport diagnostic"
    notes = "\n".join(caught.value.__notes__)
    assert "antes de reenviar" in notes
    assert "POST /measurements/" in notes
    assert "test-key" not in notes
    diagnostic = "".join(traceback.format_exception(caught.value))
    assert "Original underlying cause" in diagnostic
    assert "Original transport diagnostic" in diagnostic
    assert "unittest/mock.py" in diagnostic
    http.assert_called_once()


@pytest.mark.parametrize(
    ("method", "kwargs", "data", "message"),
    [
        ("get_credits", {}, [], "current_balance"),
        ("get_credits", {}, {}, "current_balance"),
        ("get_credits", {}, {"current_balance": "123"}, "current_balance"),
        ("get_credits", {}, {"current_balance": True}, "current_balance"),
        ("create_sample", {"country_code": "BR"}, [], "ID inteiro"),
        ("create_sample", {"country_code": "BR"}, {}, "ID inteiro"),
        ("create_sample", {"country_code": "BR"}, {"measurements": []}, "ID inteiro"),
        (
            "create_sample",
            {"country_code": "BR"},
            {"measurements": [1, 2]},
            "ID inteiro",
        ),
        (
            "create_sample",
            {"country_code": "BR"},
            {"measurements": [True]},
            "ID inteiro",
        ),
        ("create_sample", {"country_code": "BR"}, {"measurements": [0]}, "ID inteiro"),
        (
            "create_sample",
            {"country_code": "BR"},
            {"measurements": ["42"]},
            "ID inteiro",
        ),
        ("get_results", {"measurement_id": 42}, {}, "lista de objetos"),
        ("get_results", {"measurement_id": 42}, [None], "lista de objetos"),
    ],
)
def test_malformed_response(http, method, kwargs, data, message):
    http.return_value = response(data)
    with AtlasClient("test-key") as atlas:
        with pytest.raises(ValueError, match=message):
            getattr(atlas, method)(**kwargs)


def test_non_json_response_is_reported_without_body(http):
    http.return_value = response(None)
    http.return_value._content = b"<html>test-key</html>"
    with AtlasClient("test-key") as atlas:
        with pytest.raises(ValueError, match="JSON válido") as caught:
            atlas.create_sample(country_code="BR")
    assert "test-key" not in "".join(traceback.format_exception(caught.value))
    assert "antes de reenviar" in str(caught.value)
    http.assert_called_once()


def test_context_closes_session_without_suppressing_callers_error(http):
    with patch("requests.Session.close") as close:
        with pytest.raises(LookupError, match="caller error"):
            with AtlasClient("test-key") as atlas:
                raise LookupError("caller error")
        atlas.close()
        close.assert_called_once()
        with pytest.raises(ValueError, match="Cliente fechado"):
            atlas.get_credits()
        with pytest.raises(ValueError, match="Cliente fechado"):
            with atlas:
                pass
    http.assert_not_called()
