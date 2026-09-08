"""Validação de entradas antes de qualquer acesso HTTP."""

from unittest.mock import patch

import pytest

from preditor_de_falhas_ml import AtlasClient


@pytest.mark.parametrize("api_key", [None, 42, "", " ", "key\n", "a b", "á", "a\x00b"])
def test_invalid_key_does_not_create_session(api_key):
    with patch("requests.Session") as session:
        with pytest.raises(ValueError, match="Chave de API inválida"):
            AtlasClient(api_key)
    session.assert_not_called()


@pytest.mark.parametrize(
    "timeout", [0, -1, True, "30", None, float("inf"), float("nan")]
)
def test_invalid_timeout_does_not_create_session(timeout):
    with patch("requests.Session") as session:
        with pytest.raises(ValueError, match="timeout inválido"):
            AtlasClient("test-key", timeout=timeout)
    session.assert_not_called()


@pytest.mark.parametrize(
    "country", [None, 12, "", "B", "BRA", "B1", "BŔ", "ß", "BR,US"]
)
def test_invalid_country_does_not_send_request(country):
    with patch("requests.Session.send") as send, AtlasClient("test-key") as atlas:
        with pytest.raises(ValueError, match="country_code inválido"):
            atlas.create_sample(country_code=country)
    send.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("probe_count", 0),
        ("probe_count", -1),
        ("probe_count", True),
        ("probe_count", 1.5),
        ("probe_count", "1"),
        ("packets", 0),
        ("packets", 17),
        ("packets", True),
        ("packets", 3.0),
        ("packets", "3"),
    ],
)
def test_invalid_sample_counts_do_not_send_request(field, value):
    with patch("requests.Session.send") as send, AtlasClient("test-key") as atlas:
        with pytest.raises(ValueError, match=f"{field} inválido"):
            atlas.create_sample(country_code="BR", **{field: value})
    send.assert_not_called()


@pytest.mark.parametrize("measurement_id", [None, True, 0, -1, 1.0, "42", "../credits"])
def test_invalid_measurement_id_does_not_send_request(measurement_id):
    with patch("requests.Session.send") as send, AtlasClient("test-key") as atlas:
        with pytest.raises(ValueError, match="measurement_id inválido"):
            atlas.get_results(measurement_id)
    send.assert_not_called()
