"""GET Atlas (S1.2) + rótulo (S1.3) + I/O S3. Sem POST.

S2.1: curated em dois arquivos — ``curated/features.csv`` (X) e
``curated/labels.csv`` (Y). ``curated/log_rede.csv`` está superseded:
não se grava mais nele; a migração lê se existir.
"""

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from preditor_de_falhas_ml.atlas import fetch_measurement_results
from preditor_de_falhas_ml.features import (
    FEATURE_COLUMNS,
    LABEL_COLUMNS,
    LEGACY_CURATED_COLUMNS,
    feature_row,
    label_row,
    row_identity,
)

FEATURES_KEY = "curated/features.csv"
LABELS_KEY = "curated/labels.csv"
LEGACY_CURATED_KEY = "curated/log_rede.csv"
DEFAULT_WINDOW_SECONDS = 1200

_INT_COLUMNS = frozenset({"msm_id", "prb_id", "ttl", "dup", "n_hops"})
_FLOAT_COLUMNS = frozenset(
    {
        "latencia_ms",
        "rtt_min_ms",
        "rtt_max_ms",
        "perda_pacotes_pct",
        "jitter_ms",
        "pct_hops_timeout",
    }
)
_BOOL_COLUMNS = frozenset({"destino_respondeu"})


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
    """Para cada msm_id: GET results, grava JSONL raw e append X/Y.

    Não cria medição. A janela é ``start``/``stop`` unix (UTC).
    Não escreve ``curated/log_rede.csv``.
    """
    collected_at = datetime.fromtimestamp(stop, tz=UTC)
    migration = migrate_legacy_curated(s3_client, bucket)
    summary: dict[str, Any] = {
        "bucket": bucket,
        "start": start,
        "stop": stop,
        "raw_keys": [],
        "features_key": FEATURES_KEY,
        "labels_key": LABELS_KEY,
        "raw_rows": 0,
        "curated_appended": 0,
        "features_appended": 0,
        "labels_appended": 0,
        "legacy_migrated": migration["features_appended"],
        "measurements": [],
    }
    existing_features = _read_csv(s3_client, bucket, FEATURES_KEY, FEATURE_COLUMNS)
    existing_labels = _read_csv(s3_client, bucket, LABELS_KEY, LABEL_COLUMNS)
    feature_keys = {row_identity(row) for row in existing_features}
    label_keys = {row_identity(row) for row in existing_labels}
    new_features: list[dict[str, Any]] = []
    new_labels: list[dict[str, Any]] = []

    for msm_id in msm_ids:
        frame = fetch_measurement_results(api_key, msm_id, start=start, stop=stop)
        records = _frame_records(frame)
        raw_key = raw_object_key(msm_id, collected_at)
        written = _merge_raw_jsonl(s3_client, bucket, raw_key, records)
        added = 0
        for record in records:
            features = feature_row(record)
            labels = label_row(features)
            identity = row_identity(features)
            appended_pair = False
            if identity not in feature_keys:
                feature_keys.add(identity)
                new_features.append(features)
                appended_pair = True
            if identity not in label_keys:
                label_keys.add(identity)
                new_labels.append(labels)
                appended_pair = True
            if appended_pair:
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

    if new_features:
        _write_csv(
            s3_client,
            bucket,
            FEATURES_KEY,
            existing_features + new_features,
            FEATURE_COLUMNS,
        )
    if new_labels:
        _write_csv(
            s3_client,
            bucket,
            LABELS_KEY,
            existing_labels + new_labels,
            LABEL_COLUMNS,
        )
    summary["features_appended"] = len(new_features)
    summary["labels_appended"] = len(new_labels)
    summary["curated_appended"] = max(len(new_features), len(new_labels))
    return summary


def migrate_legacy_curated(s3_client: Any, bucket: str) -> dict[str, Any]:
    """Parte ``curated/log_rede.csv`` em features + labels. Idempotente.

    No-op se o objeto legado não existir. Não apaga nem regrava o legado.
    Preserva ``status_real`` já gravado; se a coluna vier vazia, aplica
    ``label_row``.
    """
    summary: dict[str, Any] = {
        "bucket": bucket,
        "source_key": LEGACY_CURATED_KEY,
        "source_found": False,
        "source_rows": 0,
        "features_key": FEATURES_KEY,
        "labels_key": LABELS_KEY,
        "features_appended": 0,
        "labels_appended": 0,
    }
    legacy_rows = _read_csv(
        s3_client,
        bucket,
        LEGACY_CURATED_KEY,
        LEGACY_CURATED_COLUMNS,
    )
    if not legacy_rows:
        return summary
    summary["source_found"] = True
    summary["source_rows"] = len(legacy_rows)

    existing_features = _read_csv(s3_client, bucket, FEATURES_KEY, FEATURE_COLUMNS)
    existing_labels = _read_csv(s3_client, bucket, LABELS_KEY, LABEL_COLUMNS)
    feature_keys = {row_identity(row) for row in existing_features}
    label_keys = {row_identity(row) for row in existing_labels}
    new_features: list[dict[str, Any]] = []
    new_labels: list[dict[str, Any]] = []

    for row in legacy_rows:
        features = {column: row.get(column) for column in FEATURE_COLUMNS}
        labels = label_row(features)
        existing_status = row.get("status_real")
        if existing_status:
            labels["status_real"] = existing_status
        identity = row_identity(features)
        if identity not in feature_keys:
            feature_keys.add(identity)
            new_features.append(features)
        if identity not in label_keys:
            label_keys.add(identity)
            new_labels.append(labels)

    if new_features:
        _write_csv(
            s3_client,
            bucket,
            FEATURES_KEY,
            existing_features + new_features,
            FEATURE_COLUMNS,
        )
    if new_labels:
        _write_csv(
            s3_client,
            bucket,
            LABELS_KEY,
            existing_labels + new_labels,
            LABEL_COLUMNS,
        )
    summary["features_appended"] = len(new_features)
    summary["labels_appended"] = len(new_labels)
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


def _read_csv(
    s3_client: Any,
    bucket: str,
    key: str,
    columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    text = _s3_get_text(s3_client, bucket, key)
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        rows.append(_parse_csv_row(raw, columns))
    return rows


def _write_csv(
    s3_client: Any,
    bucket: str,
    key: str,
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(columns),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(_format_csv_row(row, columns))
    _s3_put_text(
        s3_client,
        bucket,
        key,
        buffer.getvalue(),
        content_type="text/csv",
    )


def _parse_csv_row(raw: dict[str, str], columns: tuple[str, ...]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for column in columns:
        parsed[column] = _parse_cell(column, raw.get(column, ""))
    return parsed


def _parse_cell(column: str, value: str) -> object:
    if value == "":
        return None
    if column in _INT_COLUMNS:
        try:
            return int(value)
        except ValueError:
            return value
    if column in _FLOAT_COLUMNS:
        try:
            return float(value)
        except ValueError:
            return value
    if column in _BOOL_COLUMNS:
        if value == "True":
            return True
        if value == "False":
            return False
        return value
    return value


def _format_csv_row(row: dict[str, Any], columns: tuple[str, ...]) -> dict[str, object]:
    formatted: dict[str, object] = {}
    for column in columns:
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
