"""Coleta definição e resultados, persiste o snapshot e devolve o relatório."""

from dataclasses import replace

from preditor_de_falhas_ml.application.ports import (
    CollectReport,
    DatasetStore,
    GatewayError,
    MeasurementGateway,
)
from preditor_de_falhas_ml.domain.ids import MeasurementId
from preditor_de_falhas_ml.domain.spec import ResultFilters


def _optional_credits(gateway: MeasurementGateway) -> int | None:
    try:
        return gateway.get_credits()
    except (GatewayError, ValueError):
        return None


def collect_measurement(
    gateway: MeasurementGateway,
    store: DatasetStore,
    measurement_id: MeasurementId,
    filters: ResultFilters | None = None,
) -> CollectReport:
    """Busca, projeta e arquiva. Falha de transporte vira snapshot com erro."""
    filters = filters or ResultFilters()
    balance = _optional_credits(gateway)
    try:
        snapshot = gateway.load_snapshot(measurement_id, filters)
    except (GatewayError, ValueError) as error:
        report = store.record_snapshot(
            measurement_id,
            None,
            (),
            error=str(error),
            credit_balance=balance,
        )
        raise
    report = store.record_snapshot(
        measurement_id,
        snapshot.definition,
        snapshot.items,
        credit_balance=balance,
    )
    return replace(report, raw_results=snapshot.raw_results, credit_balance=balance)
