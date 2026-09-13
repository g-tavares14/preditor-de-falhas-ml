"""Handler Lambda: lê o secret, orquestra o collector. Sem POST."""

from __future__ import annotations

import json
import logging
import os
from time import time
from typing import Any

from preditor_de_falhas_ml.atlas import parse_measurement_ids_csv
from preditor_de_falhas_ml.collector import DEFAULT_WINDOW_SECONDS, collect_measurements

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

DEFAULT_SECRET_NAME = "RIPE_ATLAS_API_KEY"


def lambda_handler(
    event: dict[str, Any] | None,
    context: object,
    *,
    secrets_client: Any | None = None,
    s3_client: Any | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    """GET-only. Env: S3_BUCKET, RIPE_ATLAS_MSM_IDS, SECRET_NAME.

    ``event`` pode sobrescrever ``start``/``stop``/``msm_ids`` no invoke
    manual (ex.: GET histórico de IDs Stopped). Logs nunca incluem a key.
    """
    payload = event or {}
    bucket = os.environ["S3_BUCKET"]
    secret_name = os.environ.get("SECRET_NAME", DEFAULT_SECRET_NAME)
    secrets, s3 = _clients(secrets_client, s3_client)
    api_key = load_api_key(secrets, secret_name)
    msm_ids = _msm_ids(payload)
    start, stop = _window(payload, now=now)
    LOGGER.info(
        "collector start msm_ids=%s window=[%s,%s] bucket=%s",
        msm_ids,
        start,
        stop,
        bucket,
    )
    summary = collect_measurements(
        api_key,
        msm_ids,
        bucket=bucket,
        start=start,
        stop=stop,
        s3_client=s3,
    )
    LOGGER.info(
        "collector done raw_rows=%s curated_appended=%s raw_keys=%s",
        summary["raw_rows"],
        summary["curated_appended"],
        summary["raw_keys"],
    )
    return summary


def load_api_key(secrets_client: Any, secret_name: str) -> str:
    """GetSecretValue. Aceita string crua ou JSON com a key. Não loga o valor."""
    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret_string = response["SecretString"]
    if not isinstance(secret_string, str) or not secret_string.strip():
        raise ValueError(f"secret {secret_name} sem SecretString.")
    return parse_secret_string(secret_string)


def parse_secret_string(secret_string: str) -> str:
    text = secret_string.strip()
    if text.startswith("{"):
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("secret JSON inválido.")
        for key in ("RIPE_ATLAS_API_KEY", "api_key"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise ValueError("secret JSON sem RIPE_ATLAS_API_KEY.")
    return text


def _msm_ids(event: dict[str, Any]) -> list[int]:
    raw = event.get("msm_ids")
    if raw is None:
        raw = os.environ.get("RIPE_ATLAS_MSM_IDS", "")
    if isinstance(raw, list):
        return [int(item) for item in raw]
    return parse_measurement_ids_csv(str(raw))


def _window(event: dict[str, Any], *, now: int | None) -> tuple[int, int]:
    if event.get("start") is not None and event.get("stop") is not None:
        return int(event["start"]), int(event["stop"])
    stop = int(now if now is not None else time())
    window = int(os.environ.get("COLLECT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS))
    if window <= 0:
        raise ValueError("COLLECT_WINDOW_SECONDS deve ser > 0.")
    return stop - window, stop


def _clients(
    secrets_client: Any | None,
    s3_client: Any | None,
) -> tuple[Any, Any]:
    if secrets_client is not None and s3_client is not None:
        return secrets_client, s3_client
    import boto3

    secrets = secrets_client or boto3.client("secretsmanager")
    s3 = s3_client or boto3.client("s3")
    return secrets, s3
