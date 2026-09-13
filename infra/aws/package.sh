#!/usr/bin/env bash
# Build a reproducible Lambda zip: package + pandas + requests.
# boto3/botocore stay out of the zip (provided by the Python 3.12 runtime).
# Justification: one monorepo artifact; no extra layer. Same import path
# as local (`preditor_de_falhas_ml.handler.lambda_handler`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="${ROOT}/dist/lambda-build"
ZIP="${ROOT}/dist/preditor-falhas-collector.zip"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install: https://docs.astral.sh/uv/" >&2
  exit 1
fi

rm -rf "${BUILD}"
mkdir -p "${BUILD}" "${ROOT}/dist"

# Pin from the lockfile; drop AWS SDK (runtime) and the workspace itself.
uv export --frozen --no-dev --no-emit-workspace --no-hashes \
  | grep -v -E '^(boto3|botocore|s3transfer|jmespath)==' \
  > "${ROOT}/dist/requirements-lambda.txt"

uv pip install \
  --python 3.12 \
  --target "${BUILD}" \
  --only-binary :all: \
  -r "${ROOT}/dist/requirements-lambda.txt"

cp -R "${ROOT}/src/preditor_de_falhas_ml" "${BUILD}/preditor_de_falhas_ml"

find "${BUILD}" -type d -name '__pycache__' -exec rm -rf {} +
find "${BUILD}" -type d -name '*.dist-info' -exec rm -rf {} +
find "${BUILD}" -type f -name '*.pyc' -exec rm -f {} +

rm -f "${ZIP}"
(
  cd "${BUILD}"
  zip -qr "${ZIP}" .
)

bytes="$(wc -c < "${ZIP}")"
echo "==> ${ZIP} (${bytes} bytes)"
python3 - "${ZIP}" <<'PY'
import sys
import zipfile

path = sys.argv[1]
with zipfile.ZipFile(path) as archive:
    names = archive.namelist()
need = (
    "preditor_de_falhas_ml/handler.py",
    "preditor_de_falhas_ml/atlas.py",
    "preditor_de_falhas_ml/features.py",
    "preditor_de_falhas_ml/collector.py",
)
missing = [item for item in need if item not in names]
if missing:
    raise SystemExit(f"zip missing {missing}")
if any(name.startswith("boto3/") for name in names):
    raise SystemExit("zip must not include boto3 (Lambda runtime)")
print(f"==> zip entries: {len(names)}")
PY
