import json
from pathlib import Path

NOTEBOOKS = Path(__file__).resolve().parents[1] / "notebooks"
GET_NOTEBOOK = NOTEBOOKS / "01_coleta_atlas_raw.ipynb"
POST_NOTEBOOK = NOTEBOOKS / "02_post_medicoes_periodicas.ipynb"


def _code_source(path: Path) -> str:
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in cells
        if cell.get("cell_type") == "code"
    )


def _all_source(path: Path) -> str:
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return "\n".join("".join(cell.get("source", [])) for cell in cells)


def test_get_notebook_imports_package_and_avoids_raw_http() -> None:
    code = _code_source(GET_NOTEBOOK)
    text = _all_source(GET_NOTEBOOK)
    assert "from preditor_de_falhas_ml import" in code
    assert "fetch_measurement_results" in code
    assert "append_data" in code
    assert "import requests" not in code
    assert "requests.request" not in code
    assert "requests.get" not in code
    assert "get_data(" not in code
    assert "create_periodic_measurements" not in code
    assert "data/raw/" in text
    assert "atlas._request" in text
    assert "GRAVAR_RAW = True" in code
    assert "status_real" not in code


def test_post_notebook_imports_package_and_avoids_raw_http() -> None:
    code = _code_source(POST_NOTEBOOK)
    text = _all_source(POST_NOTEBOOK)
    assert "from preditor_de_falhas_ml import" in code
    assert "create_periodic_measurements" in code
    assert "write_measurement_ids" in code
    assert "get_credits" in code
    assert "HUB_SPECS" in code
    assert "import requests" not in code
    assert "requests.request" not in code
    assert "get_data(" not in code
    assert "CRIAR_MEDICOES = False" in code
    assert "docs/dataset-fonte-atlas.md" in text
    assert "01_coleta_atlas_raw.ipynb" in text
