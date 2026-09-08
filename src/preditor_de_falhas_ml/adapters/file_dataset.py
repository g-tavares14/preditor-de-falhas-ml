"""Dataset em JSONL/CSV com lock; a fórmula de X fica no domínio."""

import csv
import fcntl
import json
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, TextIO
from uuid import uuid4

from preditor_de_falhas_ml.application.ports import (
    CollectReport,
    SnapshotRecord,
)
from preditor_de_falhas_ml.application.project import project_events
from preditor_de_falhas_ml.domain.ids import MeasurementId, ObservationKey, ProbeId
from preditor_de_falhas_ml.domain.ping import (
    DIAGNOSTIC_COLUMNS,
    FEATURE_COLUMNS,
    PacketError,
    PingSample,
    Reply,
    Timeout,
    UnusableResult,
)
from preditor_de_falhas_ml.domain.spec import MeasurementDefinition, MeasurementSpec

SCHEMA_VERSION = 2

_METADATA = {
    "msm_id": ("integer", "id", False),
    "prb_id": ("integer", "id", False),
    "timestamp": ("integer", "unix_seconds", False),
    "dst_addr": ("string", "IPv4/IPv6", True),
    "af": ("integer", "address_family", True),
    "proto": ("string", None, True),
    "destination_source": ("string", None, True),
    "sent": ("integer", "packets", True),
    "rcvd": ("integer", "packets", True),
    "dup": ("integer", "packets", True),
    "rtt_count": ("integer", "responses", False),
    "jitter_pair_count": ("integer", "pairs", False),
    "timeout_count": ("integer", "packets", False),
    "error_count": ("integer", "packets", False),
    "size": ("integer", "payload_bytes", True),
    "lts": ("integer", "seconds", True),
    "reply_ttl": ("integer", "remaining_ttl", True),
    "fw": ("integer", "version", True),
    "mver": ("string", "version", True),
    "quality": ("string", None, False),
    "source_event_id": ("string", "id", False),
    "collected_at": ("string", "ISO-8601 UTC", False),
    "credit_balance": ("integer", "credits", True),
}


def dataset_schema() -> dict[str, Any]:
    """Nomes, tipos e papéis da versão atual, sem alvo global."""
    columns = {
        name: {"type": kind, "unit": unit, "nullable": nullable, "role": "metadata"}
        for name, (kind, unit, nullable) in _METADATA.items()
    }
    for name in FEATURE_COLUMNS:
        columns[name] = {
            "type": "float",
            "unit": "percent" if name == "loss_pct" else "ms",
            "nullable": True,
            "role": "feature",
        }
    for name in DIAGNOSTIC_COLUMNS:
        columns[name] = {
            "type": "integer" if name == "max_timeout_streak" else "float",
            "unit": "packets" if name == "max_timeout_streak" else "ms",
            "nullable": True,
            "role": "diagnostic",
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "observation_key": ["msm_id", "prb_id", "timestamp"],
        "x_columns": list(FEATURE_COLUMNS),
        "diagnostic_columns": list(DIAGNOSTIC_COLUMNS),
        "csv_columns": list(columns),
        "csv_null": "",
        "columns": columns,
        "rules": {
            "rtt": "Respostas numéricas finitas >= 0, excluindo duplicatas.",
            "latency_ms": "Média dos RTTs válidos; null sem respostas.",
            "loss_pct": "100 * (sent - rcvd) / sent; null se sent=0.",
            "jitter_rtt_ms": (
                "Média das diferenças absolutas entre pares consecutivos válidos, "
                "sem atravessar timeout ou erro; null sem pares."
            ),
            "quality": "ok quando o ping fecha; incomplete mantém a chave com X nulo.",
        },
    }


def _serialize_item(item: PingSample | UnusableResult) -> dict[str, Any]:
    if isinstance(item, UnusableResult):
        key = item.key
        return {
            "kind": "unusable",
            "index": item.index,
            "reason": item.reason,
            "msm_id": None if key is None else key.measurement_id.value,
            "prb_id": None if key is None else key.probe_id.value,
            "timestamp": None if key is None else key.timestamp,
            "dst_addr": item.destination,
            "af": item.address_family,
        }
    packets = []
    for packet in item.packets:
        if isinstance(packet, Reply):
            packets.append({"kind": "reply", "rtt_ms": packet.rtt_ms})
        elif isinstance(packet, Timeout):
            packets.append({"kind": "timeout"})
        else:
            packets.append({"kind": "error", "message": packet.message})
    return {
        "kind": "sample",
        "msm_id": item.key.measurement_id.value,
        "prb_id": item.key.probe_id.value,
        "timestamp": item.key.timestamp,
        "dst_addr": item.destination,
        "af": item.address_family,
        "destination_source": item.destination_source,
        "proto": item.proto,
        "sent": item.sent,
        "rcvd": item.received,
        "dup": item.duplicates,
        "packets": packets,
        "size": item.size,
        "lts": item.lts,
        "reply_ttl": item.reply_ttl,
        "fw": item.firmware,
        "mver": item.measurement_version,
    }


def _deserialize_item(payload: dict[str, Any]) -> PingSample | UnusableResult:
    if payload.get("kind") == "unusable":
        key = None
        if (
            type(payload.get("msm_id")) is int
            and type(payload.get("prb_id")) is int
            and type(payload.get("timestamp")) is int
        ):
            key = ObservationKey(
                MeasurementId(payload["msm_id"]),
                ProbeId(payload["prb_id"]),
                payload["timestamp"],
            )
        return UnusableResult(
            index=payload["index"],
            reason=payload["reason"],
            key=key,
            destination=payload.get("dst_addr"),
            address_family=payload.get("af"),
        )
    packets: list[Reply | Timeout | PacketError] = []
    for packet in payload["packets"]:
        kind = packet["kind"]
        if kind == "reply":
            packets.append(Reply(packet["rtt_ms"]))
        elif kind == "timeout":
            packets.append(Timeout())
        else:
            packets.append(PacketError(packet["message"]))
    return PingSample(
        key=ObservationKey(
            MeasurementId(payload["msm_id"]),
            ProbeId(payload["prb_id"]),
            payload["timestamp"],
        ),
        destination=payload["dst_addr"],
        address_family=payload["af"],
        destination_source=payload["destination_source"],
        sent=payload["sent"],
        received=payload["rcvd"],
        duplicates=payload["dup"],
        packets=tuple(packets),
        proto=payload.get("proto", "ICMP"),
        size=payload.get("size"),
        lts=payload.get("lts"),
        reply_ttl=payload.get("reply_ttl"),
        firmware=payload.get("fw"),
        measurement_version=payload.get("mver"),
    )


def _serialize_definition(
    definition: MeasurementDefinition | None,
) -> dict[str, Any] | None:
    if definition is None:
        return None
    return {
        "id": definition.measurement_id.value,
        "type": definition.type,
        "target": definition.target,
        "af": definition.address_family,
        "size": definition.size,
    }


def _deserialize_definition(payload: object) -> MeasurementDefinition | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Definição incompatível")
    return MeasurementDefinition(
        measurement_id=MeasurementId(payload["id"]),
        type=payload["type"],
        target=payload["target"],
        address_family=payload["af"],
        size=payload.get("size"),
    )


class FileDataset:
    """Histórico JSONL e CSV atômico em um diretório."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def prepare(self) -> None:
        with _locked(self.directory):
            _load_events(self.directory)
            with (self.directory / "raw.jsonl").open("a", encoding="utf-8"):
                pass

    def record_creation(
        self,
        measurement_id: MeasurementId,
        spec: MeasurementSpec,
        credit_balance: int | None,
    ) -> None:
        _record(
            self.directory,
            "created",
            measurement_id,
            {
                "configuration": spec.as_configuration(),
                "credit_balance": credit_balance,
            },
        )

    def record_snapshot(
        self,
        measurement_id: MeasurementId,
        definition: MeasurementDefinition | None,
        items: Sequence[PingSample | UnusableResult],
        *,
        error: str | None = None,
        credit_balance: int | None = None,
    ) -> CollectReport:
        if error is None:
            state = "empty" if not items else "results_present"
        else:
            if items:
                raise ValueError(
                    "results inválido. Informe itens sem erro ou erro sem itens."
                )
            state = "request_failed"
        payload = {
            "measurement": _serialize_definition(definition),
            "items": [_serialize_item(item) for item in items],
            "state": state,
            "error": error,
            "credit_balance": credit_balance,
        }
        report = _record(self.directory, "snapshot", measurement_id, payload)
        return CollectReport(
            **{**report, "state": state, "measurement_id": measurement_id.value}
        )

    def rebuild(self) -> CollectReport:
        with _locked(self.directory):
            return _export(self.directory, _load_events(self.directory), full=True)


@contextmanager
def _locked(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".dataset.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                f"Dataset em uso: {directory}. Aguarde a outra execução terminar."
            ) from None
        yield


def _load_events(directory: Path) -> list[dict[str, Any]]:
    schema_path = directory / "schema.json"
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise ValueError(
                f"Schema inválido: {schema_path}. Restaure o arquivo antes de continuar."
            ) from None
        version = schema.get("schema_version") if isinstance(schema, dict) else None
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Schema incompatível: {schema_path} (versão {version!r}). "
                f"Use outro diretório ou recrie o histórico no schema {SCHEMA_VERSION}."
            )
        if schema != dataset_schema():
            raise ValueError(
                f"Schema incompatível: {schema_path}. "
                "Use outro diretório ou recrie o histórico."
            )
    path = directory / "raw.jsonl"
    if not path.exists():
        if (directory / "dataset.csv").exists() or (
            directory / "rejected.jsonl"
        ).exists():
            raise ValueError(
                f"Histórico ausente em {directory}. Restaure raw.jsonl antes de reconstruir os arquivos existentes."
            )
        return []
    events = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
                if (
                    not isinstance(event, dict)
                    or event.get("schema_version") != SCHEMA_VERSION
                    or event.get("kind") not in ("created", "snapshot")
                    or type(event.get("measurement_id")) is not int
                    or event["measurement_id"] <= 0
                    or not isinstance(event.get("event_id"), str)
                    or not isinstance(event.get("collected_at"), str)
                    or not isinstance(event.get("payload_json"), str)
                ):
                    raise ValueError("Evento incompatível")
                payload = json.loads(event["payload_json"])
                if not isinstance(payload, dict):
                    raise ValueError("Payload incompatível")
            except (ValueError, TypeError):
                raise ValueError(
                    f"Histórico inválido em {path}, linha {number}. "
                    "Restaure a linha; nenhum evento será descartado automaticamente."
                ) from None
            events.append(event)
    return events


def _snapshot_records(events: Sequence[dict[str, Any]]) -> list[SnapshotRecord]:
    records = []
    for event in events:
        if event["kind"] != "snapshot":
            continue
        payload = json.loads(event["payload_json"])
        items = tuple(_deserialize_item(item) for item in payload.get("items", []))
        records.append(
            SnapshotRecord(
                measurement_id=MeasurementId(event["measurement_id"]),
                event_id=event["event_id"],
                collected_at=event["collected_at"],
                items=items,
                error=payload.get("error"),
                credit_balance=payload.get("credit_balance"),
            )
        )
    return records


@contextmanager
def _atomic_file(path: Path) -> Iterator[TextIO]:
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _export(
    directory: Path, events: list[dict[str, Any]], *, full: bool
) -> CollectReport:
    rows, rejected = project_events(_snapshot_records(events))
    schema = dataset_schema()
    with _atomic_file(directory / "dataset.csv") as stream:
        writer = csv.DictWriter(stream, fieldnames=schema["csv_columns"])
        writer.writeheader()
        writer.writerows(row.as_row() for row in rows)
    with _atomic_file(directory / "rejected.jsonl") as stream:
        for rejection in rejected:
            stream.write(
                json.dumps(
                    {
                        "source_event_id": rejection.source_event_id,
                        "measurement_id": rejection.measurement_id,
                        "result_index": rejection.result_index,
                        "reason": rejection.reason,
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )
    with _atomic_file(directory / "schema.json") as stream:
        json.dump(schema, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    current_id = events[-1]["event_id"] if events else None
    if full:
        current_rows = tuple(rows)
        current_errors = tuple(rejected)
        state = "rebuild"
    else:
        current_rows = tuple(row for row in rows if row.source_event_id == current_id)
        current_errors = tuple(
            error for error in rejected if error.source_event_id == current_id
        )
        state = "rebuild"
    return CollectReport(
        measurement_id=events[-1]["measurement_id"] if events else None,
        state=state,
        total_rows=len(rows),
        total_rejected=len(rejected),
        accepted=len(current_rows),
        rejected=len(current_errors),
        observations=current_rows,
        rejections=current_errors,
        dataset_path=str(directory / "dataset.csv"),
        credit_balance=None,
    )


def _record(
    directory: Path, kind: str, measurement_id: MeasurementId, payload: dict[str, Any]
) -> dict[str, Any]:
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": uuid4().hex,
        "collected_at": datetime.now(UTC).isoformat(),
        "kind": kind,
        "measurement_id": measurement_id.value,
        "payload_json": json.dumps(payload, ensure_ascii=False),
    }
    directory = Path(directory)
    with _locked(directory):
        events = _load_events(directory)
        with (directory / "raw.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        report = _export(directory, [*events, event], full=False)
        return {
            "measurement_id": report.measurement_id,
            "state": report.state,
            "total_rows": report.total_rows,
            "total_rejected": report.total_rejected,
            "accepted": report.accepted,
            "rejected": report.rejected,
            "observations": report.observations,
            "rejections": report.rejections,
            "dataset_path": report.dataset_path,
            "credit_balance": payload.get("credit_balance"),
        }
