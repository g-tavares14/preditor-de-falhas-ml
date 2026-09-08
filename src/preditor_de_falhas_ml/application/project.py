"""Projeção latest-wins das observações; sem arquivos e sem HTTP."""

from collections.abc import Sequence
from dataclasses import replace

from preditor_de_falhas_ml.application.ports import Rejection, SnapshotRecord
from preditor_de_falhas_ml.domain.ids import ObservationKey
from preditor_de_falhas_ml.domain.ping import (
    Observation,
    PingSample,
    UnusableResult,
    features_from_sample,
    incomplete_observation,
)


def project_items(
    items: Sequence[PingSample | UnusableResult],
    *,
    measurement_id: int,
    event_id: str,
    collected_at: str,
    credit_balance: int | None,
) -> tuple[list[Observation], list[Rejection]]:
    """Amostras viram X; item com chave incompleta permanece; sem chave rejeita."""
    rows: list[Observation] = []
    rejected: list[Rejection] = []
    for item in items:
        if isinstance(item, PingSample):
            rows.append(
                replace(
                    features_from_sample(item),
                    source_event_id=event_id,
                    collected_at=collected_at,
                    credit_balance=credit_balance,
                )
            )
            continue
        if item.key is None:
            rejected.append(
                Rejection(
                    source_event_id=event_id,
                    measurement_id=measurement_id,
                    result_index=item.index,
                    reason=item.reason,
                )
            )
            continue
        rows.append(
            replace(
                incomplete_observation(
                    item.key,
                    reason=item.reason,
                    destination=item.destination,
                    address_family=item.address_family,
                ),
                source_event_id=event_id,
                collected_at=collected_at,
                credit_balance=credit_balance,
            )
        )
    return rows, rejected


def project_events(
    events: Sequence[SnapshotRecord],
) -> tuple[list[Observation], list[Rejection]]:
    """Último snapshot por (msm_id, prb_id, timestamp) vence; falha de consulta não apaga X."""
    latest: dict[ObservationKey, Observation] = {}
    rejected: list[Rejection] = []
    for event in events:
        if event.error is not None and not event.items:
            continue
        rows, rejections = project_items(
            event.items,
            measurement_id=event.measurement_id.value,
            event_id=event.event_id,
            collected_at=event.collected_at,
            credit_balance=event.credit_balance,
        )
        rejected.extend(rejections)
        for row in rows:
            latest[row.key] = row
    observations = sorted(
        latest.values(),
        key=lambda row: (
            row.key.timestamp,
            row.key.probe_id.value,
            row.key.measurement_id.value,
        ),
    )
    return observations, rejected
