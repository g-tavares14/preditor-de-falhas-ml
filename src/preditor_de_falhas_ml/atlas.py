"""Requests ao RIPE Atlas: créditos, POST (one-off/periódico), GET e JSONL."""

import json
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any, NamedTuple

import pandas as pd
import requests

API = "https://atlas.ripe.net/api/v2/"
DEFAULT_TARGET = "8.8.8.8"
DEFAULT_OUTPUT_DIR = Path("data/raw")
DEFAULT_MSM_IDS_PATH = Path("data/msm_ids.json")
HUB_INTERVAL_SECONDS = 900
HUB_PING_PACKETS = 5
HUB_TRACEROUTE_PACKETS = 3
HUB_PROBE_COUNT = 2
HUB_COUNTRY_CODE = "BR"
HUB_ADDRESS_FAMILY = 4
HUB_TARGET_ADGUARD = "94.140.14.14"
HUB_TARGET_OPENDNS = "208.67.222.222"
HUB_TARGET_APNIC = "202.12.28.131"
# Intenção original (cota global; retry se liberar — não entra neste POST):
# 8.8.8.8, 1.1.1.1, 202.12.27.33. Ver docs/dataset-fonte-atlas.md.


class HubSpec(NamedTuple):
    target: str
    role: str
    measurement_type: str
    packets: int


HUB_SPECS: tuple[HubSpec, ...] = (
    HubSpec(HUB_TARGET_ADGUARD, "estável", "ping", HUB_PING_PACKETS),
    HubSpec(HUB_TARGET_ADGUARD, "estável", "traceroute", HUB_TRACEROUTE_PACKETS),
    HubSpec(HUB_TARGET_OPENDNS, "estável", "ping", HUB_PING_PACKETS),
    HubSpec(HUB_TARGET_OPENDNS, "estável", "traceroute", HUB_TRACEROUTE_PACKETS),
    HubSpec(HUB_TARGET_APNIC, "caminho longo", "ping", HUB_PING_PACKETS),
    HubSpec(HUB_TARGET_APNIC, "caminho longo", "traceroute", HUB_TRACEROUTE_PACKETS),
)


def _request(method: str, url: str, api_key: str, **kwargs: Any) -> Any:
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": f"Key {api_key}",
            "Accept": "application/json",
        },
        timeout=30,
        **kwargs,
    )
    return response.json()


def get_credits(api_key: str) -> int:
    return _request("GET", f"{API}credits/", api_key)["current_balance"]


def fetch_measurement(api_key: str, msm_id: int) -> dict[str, Any]:
    """GET `/measurements/{msm_id}/` (metadados, inclusive status)."""
    payload = _request("GET", f"{API}measurements/{msm_id}/", api_key)
    if not isinstance(payload, dict):
        raise ValueError(
            f"GET /measurements/{msm_id}/ não devolveu objeto. Resposta: {payload}."
        )
    return payload


def stop_measurement(api_key: str, msm_id: int) -> None:
    """DELETE `/measurements/{msm_id}/` — para a série; o histórico GET permanece."""
    response = requests.request(
        "DELETE",
        f"{API}measurements/{msm_id}/",
        headers={
            "Authorization": f"Key {api_key}",
            "Accept": "application/json",
        },
        timeout=30,
    )
    if response.status_code == 204:
        return
    detail = ""
    if getattr(response, "content", None):
        try:
            detail = f" Resposta: {response.json()}."
        except ValueError:
            detail = ""
    raise ValueError(
        f"DELETE /measurements/{msm_id}/ falhou (HTTP {response.status_code}).{detail}"
    )


def read_measurement_ids(path: Path) -> list[int]:
    """Lê msm_id do JSON gravado por write_measurement_ids (sem a API key)."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("measurements") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path} não tem measurements[] com msm_id.")
    return [int(row["msm_id"]) for row in rows]


def parse_measurement_ids_csv(value: str) -> list[int]:
    """Parseia `RIPE_ATLAS_MSM_IDS=id1,id2,…`."""
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("lista de msm_id vazia.")
    return [int(part) for part in parts]


def fetch_measurement_results(
    api_key: str,
    msm_id: int,
    *,
    start: int | None = None,
    stop: int | None = None,
) -> pd.DataFrame:
    """GET `/measurements/{msm_id}/results/`. Sem POST, sem poll, sem features."""
    extra: dict[str, Any] = {}
    params: dict[str, int] = {}
    if start is not None:
        params["start"] = start
    if stop is not None:
        params["stop"] = stop
    if params:
        extra["params"] = params
    results = _request(
        "GET",
        f"{API}measurements/{msm_id}/results/",
        api_key,
        **extra,
    )
    return pd.DataFrame(results)


def _hub_definition(spec: HubSpec) -> dict[str, Any]:
    kind = (
        "traceroute ICMP"
        if spec.measurement_type == "traceroute"
        else spec.measurement_type
    )
    definition: dict[str, Any] = {
        "target": spec.target,
        "af": HUB_ADDRESS_FAMILY,
        "type": spec.measurement_type,
        "description": f"Preditor de falhas ML - {kind} {spec.target} ({spec.role})",
        "packets": spec.packets,
        "interval": HUB_INTERVAL_SECONDS,
        "is_oneoff": False,
    }
    if spec.measurement_type == "ping":
        definition["size"] = 64
    if spec.measurement_type == "traceroute":
        definition["protocol"] = "ICMP"
    return definition


def create_periodic_measurements(api_key: str) -> list[int]:
    """POST das 6 medições periódicas do hub. Setup do dataset; não é collector."""
    created = _request(
        "POST",
        f"{API}measurements/",
        api_key,
        json={
            "definitions": [_hub_definition(spec) for spec in HUB_SPECS],
            "probes": [
                {
                    "type": "countries",
                    "value": HUB_COUNTRY_CODE,
                    "requested": HUB_PROBE_COUNT,
                }
            ],
            "is_oneoff": False,
        },
    )
    raw_ids = created.get("measurements") if isinstance(created, dict) else None
    if not isinstance(raw_ids, list) or len(raw_ids) != len(HUB_SPECS):
        raise ValueError(
            f"POST /measurements/ não devolveu {len(HUB_SPECS)} msm_id. "
            f"Resposta: {created}. "
            "Confira RIPE_ATLAS_API_KEY (permissão create) e o payload periódico."
        )
    return [int(msm_id) for msm_id in raw_ids]


def write_measurement_ids(
    msm_ids: list[int],
    output_path: Path = DEFAULT_MSM_IDS_PATH,
) -> Path:
    """Grava os 6 msm_id sem a API key. Arquivo local / Secret — não o .env no git."""
    if len(msm_ids) != len(HUB_SPECS):
        raise ValueError(
            f"Esperado {len(HUB_SPECS)} msm_id para persistir, veio {len(msm_ids)}: "
            f"{msm_ids}."
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "interval": HUB_INTERVAL_SECONDS,
        "is_oneoff": False,
        "country_code": HUB_COUNTRY_CODE,
        "probe_count": HUB_PROBE_COUNT,
        "measurements": [
            {
                "msm_id": msm_id,
                "target": spec.target,
                "role": spec.role,
                "type": spec.measurement_type,
                "packets": spec.packets,
            }
            for msm_id, spec in zip(msm_ids, HUB_SPECS, strict=True)
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def get_data(
    api_key: str,
    *,
    target: str = DEFAULT_TARGET,
    address_family: int = 4,
    country_code: str = "BR",
    probe_count: int = 1,
    packets: int = 16,
) -> pd.DataFrame:
    created = _request(
        "POST",
        f"{API}measurements/",
        api_key,
        json={
            "definitions": [
                {
                    "target": target,
                    "af": address_family,
                    "type": "ping",
                    "description": f"Preditor de falhas ML - ping {target}",
                    "packets": packets,
                    "size": 64,
                }
            ],
            "probes": [
                {
                    "type": "countries",
                    "value": country_code.upper(),
                    "requested": probe_count,
                }
            ],
            "is_oneoff": True,
        },
    )
    measurement_id = int(created["measurements"][0])
    frame = fetch_measurement_results(api_key, measurement_id)
    deadline = 30
    while frame.empty and deadline > 0:
        sleep(2)
        deadline -= 2
        frame = fetch_measurement_results(api_key, measurement_id)
    return frame


def append_data(
    frame: pd.DataFrame,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    file = Path(output_dir) / "measurements.jsonl"
    if frame.empty:
        return file
    file.parent.mkdir(parents=True, exist_ok=True)
    frame.to_json(
        file,
        orient="records",
        lines=True,
        force_ascii=False,
        mode="a",
    )
    return file
