"""Cria uma medição e registra a configuração com o saldo de créditos."""

from preditor_de_falhas_ml.application.ports import (
    DatasetStore,
    GatewayError,
    MeasurementGateway,
)
from preditor_de_falhas_ml.domain.ids import MeasurementId
from preditor_de_falhas_ml.domain.spec import MeasurementSpec


def _optional_credits(gateway: MeasurementGateway) -> int | None:
    try:
        return gateway.get_credits()
    except (GatewayError, ValueError):
        return None


def create_measurement(
    gateway: MeasurementGateway, store: DatasetStore, spec: MeasurementSpec
) -> MeasurementId:
    """Cria o ping no gateway, tenta ler o saldo e grava o evento ``created``."""
    measurement_id = gateway.create(spec)
    store.record_creation(measurement_id, spec, _optional_credits(gateway))
    return measurement_id
