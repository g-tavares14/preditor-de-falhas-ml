"""Identificadores de medição, probe e observação."""

from dataclasses import dataclass
from typing import Any


def require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    """Exige inteiro real (não bool) maior ou igual a ``minimum``."""
    if type(value) is not int or value < minimum:
        raise ValueError(
            f"{field} inválido: {value!r}. "
            f"Informe um inteiro maior ou igual a {minimum}."
        )
    return value


@dataclass(frozen=True, slots=True)
class MeasurementId:
    """Identificador positivo de uma medição no Atlas."""

    value: int

    def __post_init__(self) -> None:
        require_int(self.value, "measurement_id", minimum=1)


@dataclass(frozen=True, slots=True)
class ProbeId:
    """Identificador positivo de uma probe."""

    value: int

    def __post_init__(self) -> None:
        require_int(self.value, "prb_id", minimum=1)


@dataclass(frozen=True, slots=True)
class ObservationKey:
    """Uma linha de X: medição, probe e instante Unix em segundos."""

    measurement_id: MeasurementId
    probe_id: ProbeId
    timestamp: int

    def __post_init__(self) -> None:
        require_int(self.timestamp, "timestamp")
