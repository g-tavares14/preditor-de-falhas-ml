from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

Responder = Callable[[str, str, dict[str, Any]], object]


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload


@pytest.fixture
def ping_results_payload() -> list[dict[str, Any]]:
    import json

    raw = (FIXTURES / "ping_results.json").read_text(encoding="utf-8")
    payload: list[dict[str, Any]] = json.loads(raw)
    return payload


@pytest.fixture
def mock_atlas_request(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Responder], list[dict[str, Any]]]:
    def install(responder: Responder) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
            calls.append({"method": method, "url": url, "kwargs": kwargs})
            return FakeResponse(responder(method, url, kwargs))

        monkeypatch.setattr(
            "preditor_de_falhas_ml.atlas.requests.request",
            fake_request,
        )
        return calls

    return install
