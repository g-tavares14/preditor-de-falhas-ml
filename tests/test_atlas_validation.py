"""Validação de entradas do gateway antes de qualquer acesso HTTP."""

from unittest.mock import patch

import pytest

from preditor_de_falhas_ml.adapters.atlas import AtlasGateway
from preditor_de_falhas_ml.application.ports import GatewayError
from preditor_de_falhas_ml.domain.ids import MeasurementId
from preditor_de_falhas_ml.domain.spec import ResultFilters


@pytest.mark.parametrize("api_key", [42, "", " ", "key\n", "a b", "á", "a\x00b"])
def test_invalid_key_does_not_create_session(api_key):
    with patch("requests.Session") as session:
        with pytest.raises(ValueError, match="Chave de API inválida"):
            AtlasGateway(api_key)
    session.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, True, "30", float("inf"), float("nan")])
def test_invalid_timeout_does_not_create_session(timeout):
    with patch("requests.Session") as session:
        with pytest.raises(ValueError, match="timeout inválido"):
            AtlasGateway("test-key", timeout=timeout)
    session.assert_not_called()


def test_create_and_credits_without_key_do_not_send():
    from preditor_de_falhas_ml.domain.spec import CountrySelection, MeasurementSpec

    with patch("requests.Session.send") as send, AtlasGateway(None) as atlas:
        with pytest.raises(GatewayError, match="Chave de API ausente"):
            atlas.get_credits()
        with pytest.raises(GatewayError, match="Chave de API ausente"):
            atlas.create(
                MeasurementSpec(
                    target="8.8.8.8",
                    address_family=4,
                    selection=CountrySelection("BR"),
                )
            )
    send.assert_not_called()


@pytest.mark.parametrize("measurement_id", [None, True, 0, -1, 1.0, "42"])
def test_invalid_measurement_id_does_not_send_request(measurement_id):
    with patch("requests.Session.send") as send, AtlasGateway("test-key") as atlas:
        with pytest.raises(ValueError, match="measurement_id inválido"):
            atlas.load_snapshot(MeasurementId(measurement_id), ResultFilters())
    send.assert_not_called()
