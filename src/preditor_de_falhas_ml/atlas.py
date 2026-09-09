"""Requests ao RIPE Atlas: créditos, ping novo, DataFrame e histórico JSONL."""

from pathlib import Path
from time import sleep
from typing import Any

import pandas as pd
import requests

API = "https://atlas.ripe.net/api/v2/"
DEFAULT_TARGET = "8.8.8.8"
DEFAULT_OUTPUT_DIR = Path("data/raw")


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
    measurement_id = created["measurements"][0]
    results = _request(
        "GET",
        f"{API}measurements/{measurement_id}/results/",
        api_key,
    )
    deadline = 30
    while not results and deadline > 0:
        sleep(2)
        deadline -= 2
        results = _request(
            "GET",
            f"{API}measurements/{measurement_id}/results/",
            api_key,
        )
    return pd.DataFrame(results)


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
