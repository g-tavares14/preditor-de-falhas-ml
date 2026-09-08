"""Contrato HTTP do AtlasGateway, sem rede ou consumo de créditos."""

import json
from unittest.mock import patch

import pytest
import requests

from preditor_de_falhas_ml.adapters.atlas import AtlasGateway, parse_result
from preditor_de_falhas_ml.application.ports import GatewayError
from preditor_de_falhas_ml.domain.ids import MeasurementId, ProbeId
from preditor_de_falhas_ml.domain.ping import PingSample, UnusableResult
from preditor_de_falhas_ml.domain.spec import (
    CountrySelection,
    MeasurementSpec,
    ResultFilters,
)


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    result.headers["Content-Type"] = "application/json"
    return result


def spec(**kwargs) -> MeasurementSpec:
    return MeasurementSpec(
        target=kwargs.get("target", "8.8.8.8"),
        address_family=kwargs.get("address_family", 4),
        selection=CountrySelection(
            kwargs.get("country_code", "BR"), kwargs.get("probe_count", 1)
        ),
        packets=kwargs.get("packets", 16),
        interval=kwargs.get("interval"),
        duration=kwargs.get("duration"),
    )


@pytest.fixture
def http():
    with patch("requests.Session.send") as send:
        yield send


def test_authenticated_create_and_public_filters(http):
    raw_results = [
        {
            "type": "ping",
            "msm_id": 12345,
            "prb_id": 678,
            "dst_addr": "8.8.8.8",
            "af": 4,
            "timestamp": 1788800000,
            "sent": 3,
            "rcvd": 2,
            "result": [{"rtt": 12.3}, {"x": "*"}, {"rtt": 14.8}],
            "future_field": {"value": None},
        }
    ]
    http.side_effect = [
        response({"measurements": [12345]}, 201),
        response({"id": 12345, "type": "ping", "af": 4, "target": "8.8.8.8"}),
        response(raw_results),
    ]
    with AtlasGateway("test-key", timeout=12.5) as atlas:
        measurement_id = atlas.create(spec(country_code="BR", probe_count=2, packets=4))
        assert measurement_id.value == 12345
        snapshot = atlas.load_snapshot(
            measurement_id, ResultFilters(probe_id=ProbeId(678), start=10, stop=20)
        )
    assert isinstance(snapshot.items[0], PingSample)
    assert snapshot.raw_results == tuple(raw_results)
    create, definition, results = [call.args[0] for call in http.call_args_list]
    assert json.loads(create.body)["definitions"][0]["packets"] == 4
    assert json.loads(create.body)["probes"] == [
        {"type": "countries", "value": "BR", "requested": 2}
    ]
    assert "probe=678" in results.url
    assert "start=10" in results.url
    assert "stop=20" in results.url
    assert definition.url.endswith("/measurements/12345/")
    for call in http.call_args_list:
        assert call.args[0].headers["Authorization"] == "Key test-key"
        assert call.kwargs["timeout"] == 12.5
        assert call.kwargs["allow_redirects"] is False


def test_unauthenticated_results_do_not_send_authorization(http):
    http.side_effect = [
        response({"id": 42, "type": "ping", "af": 4, "target": "1.1.1.1"}),
        response([]),
    ]
    with AtlasGateway(None) as atlas:
        snapshot = atlas.load_snapshot(MeasurementId(42), ResultFilters())
    assert snapshot.raw_results == ()
    for call in http.call_args_list:
        assert "Authorization" not in call.args[0].headers


def test_recurring_spec_sends_interval_and_stop_time(http):
    http.return_value = response({"measurements": [9]}, 201)
    with AtlasGateway("test-key", clock=lambda: 1000.0) as atlas:
        atlas.create(
            spec(target="1.1.1.1", address_family=6, interval=300, duration=60)
        )
    payload = json.loads(http.call_args.args[0].body)
    assert payload["is_oneoff"] is False
    assert payload["interval"] == 300
    assert payload["stop_time"] == 1060
    assert payload["definitions"][0]["target"] == "1.1.1.1"
    assert payload["definitions"][0]["af"] == 6


def test_http_errors_become_gateway_error_without_exposing_key(http):
    http.return_value = response({"detail": "test-key"}, 401)
    with AtlasGateway("test-key") as atlas:
        with pytest.raises(GatewayError, match="HTTP 401") as caught:
            atlas.create(spec())
    assert "test-key" not in str(caught.value)
    assert "antes de reenviar" in str(caught.value)
    assert caught.value.creating is True
    http.assert_called_once()


def test_network_error_is_wrapped_preserving_cause(http):
    original = requests.Timeout("Original transport diagnostic")
    http.side_effect = original
    with AtlasGateway("test-key") as atlas:
        with pytest.raises(GatewayError) as caught:
            atlas.create(spec())
    assert caught.value.__cause__ is original
    assert "antes de reenviar" in str(caught.value)
    assert "test-key" not in str(caught.value)
    http.assert_called_once()


def test_parse_result_accepts_other_targets_and_keeps_malformed_with_key():
    usable = parse_result(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 3,
            "af": 4,
            "dst_addr": "1.1.1.1",
            "result": [{"rtt": 10}],
        },
        index=0,
        measurement_id=MeasurementId(1),
        definition=None,
    )
    assert isinstance(usable, PingSample)
    assert usable.destination == "1.1.1.1"
    broken = parse_result(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 3,
            "af": 4,
            "dst_addr": "1.1.1.1",
            "result": [{"rtt": 10, "x": "*"}],
        },
        index=1,
        measurement_id=MeasurementId(1),
        definition=None,
    )
    assert isinstance(broken, UnusableResult)
    assert broken.key is not None


def test_inconsistent_atlas_counters_still_parse_from_packets():
    parsed = parse_result(
        {
            "type": "ping",
            "msm_id": 1,
            "prb_id": 2,
            "timestamp": 3,
            "af": 4,
            "dst_addr": "8.8.8.8",
            "sent": 9,
            "rcvd": 9,
            "result": [{"rtt": 10}],
        },
        index=0,
        measurement_id=MeasurementId(1),
        definition=None,
    )
    assert isinstance(parsed, PingSample)
    assert parsed.sent == 1
    assert parsed.received == 1


def test_context_closes_session(http):
    with patch("requests.Session.close") as close:
        with pytest.raises(LookupError, match="caller error"):
            with AtlasGateway("test-key") as atlas:
                raise LookupError("caller error")
        atlas.close()
        close.assert_called_once()
        with pytest.raises(ValueError, match="Cliente fechado"):
            atlas.get_credits()
    http.assert_not_called()
