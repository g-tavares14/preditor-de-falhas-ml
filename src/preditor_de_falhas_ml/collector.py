"""GET Atlas (S1.2) + rótulo (S1.3) + I/O S3. Sem POST."""

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from preditor_de_falhas_ml.atlas import fetch_measurement_results
from preditor_de_falhas_ml.features import (
    CURATED_CSV_COLUMNS,
    curated_row,
    row_identity,
)

CURATED_KEY = "curated/log_rede.csv"
DEFAULT_WINDOW_SECONDS = 1200


def raw_object_key(msm_id: int, when: datetime) -> str:
    """Path canônico: raw/measurements/yyyy=/mm=/dd=/{msm_id}.jsonl (UTC)."""
    return f"raw/measurements/yyyy={when:%Y}/mm={when:%m}/dd={when:%d}/{msm_id}.jsonl"


def collect_measurements(
    api_key: str,
    msm_ids: list[int],
    *,
    bucket: str,
    start: int,
    stop: int,
    s3_client: Any,
) -> dict[str, Any]:
    """Para cada msm_id: GET results, grava JSONL raw e append curated.

    Não cria medição. A janela é ``start``/``stop`` unix (UTC).
    """
    collected_at = datetime.fromtimestamp(stop, tz=UTC)
    summary: dict[str, Any] = {
        "bucket": bucket,
        "start": start,
        "stop": stop,
        "raw_keys": [],
        "curated_key": CURATED_KEY,
        "raw_rows": 0,
        "curated_appended": 0,
        "measurements": [],
    }
    curated_existing = _read_curated(s3_client, bucket)
    curated_keys = {row_identity(row) for row in curated_existing}
    new_curated: list[dict[str, Any]] = []

    for msm_id in msm_ids:
        frame = fetch_measurement_results(api_key, msm_id, start=start, stop=stop)
        records = _frame_records(frame)
        raw_key = raw_object_key(msm_id, collected_at)
        written = _merge_raw_jsonl(s3_client, bucket, raw_key, records)
        added = 0
        for record in records:
            row = curated_row(record)
            identity = row_identity(row)
            if identity in curated_keys:
                continue
            curated_keys.add(identity)
            new_curated.append(row)
            added += 1
        summary["raw_keys"].append(raw_key)
        summary["raw_rows"] += written
        summary["measurements"].append(
            {
                "msm_id": msm_id,
                "raw_key": raw_key,
                "fetched": len(records),
                "raw_written": written,
                "curated_appended": added,
            }
        )

    if new_curated:
        _write_curated(s3_client, bucket, curated_existing + new_curated)
    summary["curated_appended"] = len(new_curated)
    return summary


def _frame_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    records = frame.to_dict(orient="records")
    return [record for record in records if isinstance(record, dict)]


def _merge_raw_jsonl(
    s3_client: Any,
    bucket: str,
    key: str,
    records: list[dict[str, Any]],
) -> int:
    existing = _parse_jsonl(_s3_get_text(s3_client, bucket, key))
    seen = {_raw_identity(item) for item in existing}
    merged = list(existing)
    added = 0
    for record in records:
        identity = _raw_identity(record)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(record)
        added += 1
    if added or not existing:
        _s3_put_text(
            s3_client,
            bucket,
            key,
            _dump_jsonl(merged),
            content_type="application/x-ndjson",
        )
    return added


def _raw_identity(record: dict[str, Any]) -> tuple[object, object, object]:
    return (record.get("msm_id"), record.get("timestamp"), record.get("prb_id"))


def _read_curated(s3_client: Any, bucket: str) -> list[dict[str, Any]]:
    text = _s3_get_text(s3_client, bucket, CURATED_KEY)
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        rows.append(_parse_curated_row(raw))
    return rows


def _write_curated(
    s3_client: Any,
    bucket: str,
    rows: list[dict[str, Any]],
) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(CURATED_CSV_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(_format_curated_row(row))
    _s3_put_text(
        s3_client,
        bucket,
        CURATED_KEY,
        buffer.getvalue(),
        content_type="text/csv",
    )


def _parse_curated_row(raw: dict[str, str]) -> dict[str, Any]:
    def maybe_int(value: str) -> int | str | None:
        if value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return value

    def maybe_float(value: str) -> float | str | None:
        if value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return value

    def maybe_bool(value: str) -> bool | str | None:
        if value == "":
            return None
        if value == "True":
            return True
        if value == "False":
            return False
        return value

    return {
        "msm_id": maybe_int(raw.get("msm_id", "")),
        "timestamp": raw.get("timestamp") or None,
        "prb_id": maybe_int(raw.get("prb_id", "")),
        "ip": raw.get("ip") or None,
        "latencia_ms": maybe_float(raw.get("latencia_ms", "")),
        "rtt_min_ms": maybe_float(raw.get("rtt_min_ms", "")),
        "rtt_max_ms": maybe_float(raw.get("rtt_max_ms", "")),
        "perda_pacotes_pct": maybe_float(raw.get("perda_pacotes_pct", "")),
        "jitter_ms": maybe_float(raw.get("jitter_ms", "")),
        "ttl": maybe_int(raw.get("ttl", "")),
        "dup": maybe_int(raw.get("dup", "")),
        "n_hops": maybe_int(raw.get("n_hops", "")),
        "destino_respondeu": maybe_bool(raw.get("destino_respondeu", "")),
        "pct_hops_timeout": maybe_float(raw.get("pct_hops_timeout", "")),
        "status_real": raw.get("status_real") or None,
    }


def _format_curated_row(row: dict[str, Any]) -> dict[str, object]:
    formatted: dict[str, object] = {}
    for column in CURATED_CSV_COLUMNS:
        value = row.get(column)
        formatted[column] = "" if value is None else value
    return formatted


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _dump_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return (
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
    )


def _s3_get_text(s3_client: Any, bucket: str, key: str) -> str:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if _is_missing_key(exc):
            return ""
        raise
    body = response["Body"]
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return str(raw)


def _s3_put_text(
    s3_client: Any,
    bucket: str,
    key: str,
    text: str,
    *,
    content_type: str,
) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType=content_type,
    )


def _is_missing_key(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return True
    text = str(exc)
    return type(exc).__name__ == "NoSuchKey" or "NoSuchKey" in text
