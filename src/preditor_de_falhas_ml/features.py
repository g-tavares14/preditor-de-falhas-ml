"""Funções puras: registro Atlas bruto → vetor curated + status_real.

Sem HTTP, Path, CSV ou pandas. Entrada: dict (JSON Atlas ping/traceroute).
O CSV curated da disciplina usa os nomes em português abaixo.

Rótulo ``status_real`` (nesta ordem):

1. ``perda_pacotes_pct`` > 15 → ``FALHA``
2. senão ``latencia_ms`` > 100 → ``RISCO``
3. senão → ``OK``

Jitter (``jitter_ms``): média das diferenças absolutas sucessivas
``|rtt[i] − rtt[i−1]|`` nos RTTs válidos, na ordem do resultado (mean
absolute successive difference). Menos de dois RTTs válidos → ``0.0``.
"""

from datetime import UTC, datetime
from typing import Any

STATUS_FALHA = "FALHA"
STATUS_RISCO = "RISCO"
STATUS_OK = "OK"

LOSS_FALHA_PCT = 15.0
LATENCY_RISCO_MS = 100.0

CURATED_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "prb_id",
    "ip",
    "latencia_ms",
    "rtt_min_ms",
    "rtt_max_ms",
    "perda_pacotes_pct",
    "jitter_ms",
    "ttl",
    "dup",
    "n_hops",
    "destino_respondeu",
    "pct_hops_timeout",
    "status_real",
)

# msm_id entra no CSV só como chave operacional de idempotência (S1.7).
# As 14 colunas da disciplina seguem na ordem canônica.
CURATED_CSV_COLUMNS: tuple[str, ...] = ("msm_id", *CURATED_COLUMNS)


def _valid_rtt(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float) and value >= 0:
        return float(value)
    return None


def status_real(
    perda_pacotes_pct: float | None,
    latencia_ms: float | None,
) -> str:
    """Aplica a ordem travada do rótulo (perda primeiro, depois latência)."""
    if perda_pacotes_pct is not None and perda_pacotes_pct > LOSS_FALHA_PCT:
        return STATUS_FALHA
    if latencia_ms is not None and latencia_ms > LATENCY_RISCO_MS:
        return STATUS_RISCO
    return STATUS_OK


def curated_row(record: dict[str, Any]) -> dict[str, Any]:
    """Converte um objeto Atlas (ping ou traceroute) no schema ampliado."""
    kind = str(record.get("type") or "")
    rtts = _valid_rtts(record, kind)
    sent = _as_int(record.get("sent"))
    rcvd = _as_int(record.get("rcvd"))
    hops = _traceroute_hops(record) if kind == "traceroute" else []
    destino = _destino_respondeu(record, kind, rcvd, hops)
    perda = _perda_pacotes_pct(sent, rcvd, kind, destino)
    latencia = _mean(rtts)
    rtt_min = min(rtts) if rtts else _valid_rtt(record.get("min"))
    rtt_max = max(rtts) if rtts else _valid_rtt(record.get("max"))
    if latencia is None:
        latencia = _valid_rtt(record.get("avg"))
    n_hops, pct_timeout = _hop_stats(hops) if kind == "traceroute" else (None, None)
    return {
        "msm_id": record.get("msm_id"),
        "timestamp": _timestamp_iso(record.get("timestamp")),
        "prb_id": record.get("prb_id"),
        "ip": record.get("dst_addr") or record.get("dst_name") or record.get("from"),
        "latencia_ms": latencia,
        "rtt_min_ms": rtt_min,
        "rtt_max_ms": rtt_max,
        "perda_pacotes_pct": perda,
        "jitter_ms": _jitter_ms(rtts),
        "ttl": _ttl(record, hops),
        "dup": _as_int(record.get("dup")) if kind == "ping" else None,
        "n_hops": n_hops,
        "destino_respondeu": destino,
        "pct_hops_timeout": pct_timeout,
        "status_real": status_real(perda, latencia),
    }


def row_identity(row: dict[str, Any]) -> tuple[object, object, object]:
    """Chave de idempotência: msm_id + timestamp + prb_id."""
    return (row.get("msm_id"), row.get("timestamp"), row.get("prb_id"))


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _jitter_ms(rtts: list[float]) -> float:
    if len(rtts) < 2:
        return 0.0
    diffs = [abs(rtts[index] - rtts[index - 1]) for index in range(1, len(rtts))]
    return sum(diffs) / len(diffs)


def _timestamp_iso(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return datetime.fromtimestamp(int(value), tz=UTC).isoformat()
    return None


def _valid_rtts(record: dict[str, Any], kind: str) -> list[float]:
    if kind == "traceroute":
        hops = _traceroute_hops(record)
        if not hops:
            return []
        return _rtts_from_items(hops[-1].get("result"))
    rtts = _rtts_from_items(record.get("result"))
    if rtts:
        return rtts
    fallback = _valid_rtt(record.get("avg"))
    return [fallback] if fallback is not None else []


def _rtts_from_items(items: object) -> list[float]:
    rtts: list[float] = []
    if not isinstance(items, list):
        return rtts
    for item in items:
        if not isinstance(item, dict) or "x" in item:
            continue
        rtt = _valid_rtt(item.get("rtt"))
        if rtt is not None:
            rtts.append(rtt)
    return rtts


def _perda_pacotes_pct(
    sent: int | None,
    rcvd: int | None,
    kind: str,
    destino: bool | None,
) -> float:
    if sent == 0:
        return 100.0
    if sent is not None and rcvd is not None and sent > 0:
        return (sent - rcvd) / sent * 100.0
    if kind == "traceroute":
        return 0.0 if destino else 100.0
    return 100.0


def _traceroute_hops(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("result")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _hop_timed_out(hop: dict[str, Any]) -> bool:
    items = hop.get("result")
    if not isinstance(items, list) or not items:
        return True
    for item in items:
        if not isinstance(item, dict):
            continue
        if "x" in item:
            continue
        if item.get("from") or _valid_rtt(item.get("rtt")) is not None:
            return False
    return True


def _hop_stats(hops: list[dict[str, Any]]) -> tuple[int, float]:
    n_hops = len(hops)
    if n_hops == 0:
        return 0, 0.0
    timed_out = sum(1 for hop in hops if _hop_timed_out(hop))
    return n_hops, timed_out / n_hops * 100.0


def _destino_respondeu(
    record: dict[str, Any],
    kind: str,
    rcvd: int | None,
    hops: list[dict[str, Any]],
) -> bool | None:
    if kind == "traceroute":
        flagged = record.get("destination_ip_responded")
        if isinstance(flagged, bool):
            return flagged
        dst = record.get("dst_addr")
        if not hops or not dst:
            return False
        for item in hops[-1].get("result") or []:
            if isinstance(item, dict) and item.get("from") == dst:
                return True
        return False
    if rcvd is not None:
        return rcvd > 0
    return None


def _ttl(record: dict[str, Any], hops: list[dict[str, Any]]) -> int | None:
    top = _as_int(record.get("ttl"))
    if top is not None:
        return top
    if not hops:
        return None
    items = hops[-1].get("result")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict):
            hop_ttl = _as_int(item.get("ttl"))
            if hop_ttl is not None:
                return hop_ttl
    return None
