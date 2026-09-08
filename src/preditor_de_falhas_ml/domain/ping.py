"""Amostra de ping e o vetor X = [latência, perda, jitter]."""

from dataclasses import dataclass
from itertools import pairwise
from math import isfinite
from statistics import mean, pstdev

from preditor_de_falhas_ml.domain.ids import ObservationKey

FEATURE_COLUMNS = ("latency_ms", "loss_pct", "jitter_rtt_ms")
DIAGNOSTIC_COLUMNS = (
    "rtt_min_ms",
    "rtt_max_ms",
    "rtt_median_ms",
    "rtt_std_ms",
    "max_timeout_streak",
)


@dataclass(frozen=True, slots=True)
class Reply:
    """Resposta com RTT em milissegundos, finito e não negativo."""

    rtt_ms: float

    def __post_init__(self) -> None:
        rtt = self.rtt_ms
        if type(rtt) not in (int, float):
            raise ValueError(f"rtt inválido: {rtt!r}. Forneça milissegundos numéricos.")
        try:
            value = float(rtt)
        except OverflowError:
            raise ValueError(
                "rtt fora do limite numérico. Confira o RTT original."
            ) from None
        if value < 0 or not isfinite(value):
            raise ValueError(
                f"rtt inválido: {rtt!r}. Forneça milissegundos numéricos, finitos e não negativos."
            )
        object.__setattr__(self, "rtt_ms", value)


@dataclass(frozen=True, slots=True)
class Timeout:
    """Pacote sem resposta (timeout)."""


@dataclass(frozen=True, slots=True)
class PacketError:
    """Pacote com erro reportado pela probe."""

    message: str


Packet = Reply | Timeout | PacketError


@dataclass(frozen=True, slots=True)
class PingSample:
    """Ping ICMP já validado, independente do JSON do Atlas."""

    key: ObservationKey
    destination: str
    address_family: int
    destination_source: str
    sent: int
    received: int
    duplicates: int
    packets: tuple[Packet, ...]
    proto: str = "ICMP"
    size: int | None = None
    lts: int | None = None
    reply_ttl: int | None = None
    firmware: int | None = None
    measurement_version: str | None = None

    def __post_init__(self) -> None:
        if self.address_family not in (4, 6):
            raise ValueError(
                f"af inválido: {self.address_family!r}. Use 4 (IPv4) ou 6 (IPv6)."
            )
        if not isinstance(self.destination, str) or not self.destination:
            raise ValueError(
                f"dst_addr inválido: {self.destination!r}. Informe o destino."
            )
        if self.proto != "ICMP":
            raise ValueError(f"proto inválido: {self.proto!r}. Use ping ICMP.")
        if self.destination_source not in ("result", "definition"):
            raise ValueError(
                f"destination_source inválido: {self.destination_source!r}. Use result ou definition."
            )
        if self.sent != len(self.packets):
            raise ValueError(
                f"sent inválido: {self.sent!r}. Deve coincidir com os pacotes não duplicados ({len(self.packets)})."
            )
        replies = sum(isinstance(packet, Reply) for packet in self.packets)
        if self.received != replies:
            raise ValueError(
                f"rcvd inválido: {self.received!r}. Deve coincidir com as respostas ({replies})."
            )


@dataclass(frozen=True, slots=True)
class UnusableResult:
    """Resultado que não vira PingSample; com chave, a observação permanece em X."""

    index: int
    reason: str
    key: ObservationKey | None = None
    destination: str | None = None
    address_family: int | None = None


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """X = [latência, perda, jitter]. Ausências são None, não zero inventado."""

    latency_ms: float | None
    loss_pct: float | None
    jitter_rtt_ms: float | None

    def as_dict(self) -> dict[str, float | None]:
        return {
            "latency_ms": self.latency_ms,
            "loss_pct": self.loss_pct,
            "jitter_rtt_ms": self.jitter_rtt_ms,
        }


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Atributos auxiliares; não fazem parte de X."""

    rtt_min_ms: float | None
    rtt_max_ms: float | None
    rtt_median_ms: float | None
    rtt_std_ms: float | None
    max_timeout_streak: int | None
    rtt_count: int
    jitter_pair_count: int
    timeout_count: int
    error_count: int

    def as_dict(self) -> dict[str, int | float | None]:
        return {
            "rtt_min_ms": self.rtt_min_ms,
            "rtt_max_ms": self.rtt_max_ms,
            "rtt_median_ms": self.rtt_median_ms,
            "rtt_std_ms": self.rtt_std_ms,
            "max_timeout_streak": self.max_timeout_streak,
            "rtt_count": self.rtt_count,
            "jitter_pair_count": self.jitter_pair_count,
            "timeout_count": self.timeout_count,
            "error_count": self.error_count,
        }


@dataclass(frozen=True, slots=True)
class Observation:
    """Uma linha do dataset: identidade, X, diagnóstico e qualidade."""

    key: ObservationKey
    destination: str | None
    address_family: int | None
    proto: str | None
    destination_source: str | None
    sent: int | None
    received: int | None
    duplicates: int | None
    size: int | None
    lts: int | None
    reply_ttl: int | None
    firmware: int | None
    measurement_version: str | None
    features: FeatureVector
    diagnostics: Diagnostics
    quality: str = "ok"
    source_event_id: str | None = None
    collected_at: str | None = None
    credit_balance: int | None = None

    def as_row(self) -> dict[str, int | float | str | None]:
        return {
            "msm_id": self.key.measurement_id.value,
            "prb_id": self.key.probe_id.value,
            "timestamp": self.key.timestamp,
            "dst_addr": self.destination,
            "af": self.address_family,
            "proto": self.proto,
            "destination_source": self.destination_source,
            "sent": self.sent,
            "rcvd": self.received,
            "dup": self.duplicates,
            **self.diagnostics.as_dict(),
            "size": self.size,
            "lts": self.lts,
            "reply_ttl": self.reply_ttl,
            "fw": self.firmware,
            "mver": self.measurement_version,
            "quality": self.quality,
            "source_event_id": self.source_event_id,
            "collected_at": self.collected_at,
            "credit_balance": self.credit_balance,
            **self.features.as_dict(),
        }


def incomplete_observation(
    key: ObservationKey,
    *,
    reason: str,
    destination: str | None = None,
    address_family: int | None = None,
) -> Observation:
    """Mantém a identidade em X com métricas nulas quando o ping não fecha."""
    _ = reason
    empty = FeatureVector(None, None, None)
    diagnostics = Diagnostics(None, None, None, None, None, 0, 0, 0, 0)
    return Observation(
        key=key,
        destination=destination,
        address_family=address_family,
        proto=None,
        destination_source=None,
        sent=None,
        received=None,
        duplicates=None,
        size=None,
        lts=None,
        reply_ttl=None,
        firmware=None,
        measurement_version=None,
        features=empty,
        diagnostics=diagnostics,
        quality="incomplete",
    )


def features_from_sample(sample: PingSample) -> Observation:
    """Calcula X e o diagnóstico a partir dos pacotes, sem I/O.

    Latência: média dos RTTs. Perda: 100 * (sent - rcvd) / sent. Jitter: média
    das diferenças absolutas entre pares consecutivos com resposta, sem
    atravessar timeout ou erro. Sem observações, as métricas ficam None.
    """
    rtts: list[float | None] = []
    timeout_count = error_count = timeout_streak = max_timeout_streak = 0
    for packet in sample.packets:
        if isinstance(packet, Reply):
            rtts.append(packet.rtt_ms)
            timeout_streak = 0
        elif isinstance(packet, Timeout):
            rtts.append(None)
            timeout_count += 1
            timeout_streak += 1
            max_timeout_streak = max(max_timeout_streak, timeout_streak)
        else:
            rtts.append(None)
            error_count += 1
            timeout_streak = 0

    valid = [rtt for rtt in rtts if rtt is not None]
    differences = [
        abs(current - previous)
        for previous, current in pairwise(rtts)
        if previous is not None and current is not None
    ]
    ordered = sorted(valid)
    middle = ordered[(len(ordered) - 1) // 2 : len(ordered) // 2 + 1]
    sent = sample.sent
    features = FeatureVector(
        latency_ms=float(mean(valid)) if valid else None,
        loss_pct=100 * (sent - sample.received) / sent if sent else None,
        jitter_rtt_ms=float(mean(differences)) if differences else None,
    )
    diagnostics = Diagnostics(
        rtt_min_ms=min(valid) if valid else None,
        rtt_max_ms=max(valid) if valid else None,
        rtt_median_ms=float(mean(middle)) if middle else None,
        rtt_std_ms=pstdev(valid) if len(valid) >= 2 else None,
        max_timeout_streak=max_timeout_streak if sent else None,
        rtt_count=len(valid),
        jitter_pair_count=len(differences),
        timeout_count=timeout_count,
        error_count=error_count,
    )
    return Observation(
        key=sample.key,
        destination=sample.destination,
        address_family=sample.address_family,
        proto=sample.proto,
        destination_source=sample.destination_source,
        sent=sample.sent,
        received=sample.received,
        duplicates=sample.duplicates,
        size=sample.size,
        lts=sample.lts,
        reply_ttl=sample.reply_ttl,
        firmware=sample.firmware,
        measurement_version=sample.measurement_version,
        features=features,
        diagnostics=diagnostics,
        quality="ok",
    )
