#!/usr/bin/env bash
# Manual invoke of preditor-falhas-collector. Does not print secrets.
# Optional: INVOKE_PAYLOAD=/path/to.json (start/stop/msm_ids overrides).
set -euo pipefail

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-sa-east-1}}"
FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-preditor-falhas-collector}"
OUT="${INVOKE_OUT:-${TMPDIR:-/tmp}/preditor-falhas-collector-invoke.json}"
PAYLOAD="${INVOKE_PAYLOAD:-}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found." >&2
  exit 1
fi

args=(
  --region "${REGION}"
  --function-name "${FUNCTION_NAME}"
  --cli-binary-format raw-in-base64-out
  --log-type Tail
)
if [[ -n "${PAYLOAD}" ]]; then
  args+=(--payload "fileb://${PAYLOAD}")
else
  args+=(--payload '{}')
fi

echo "==> invoke ${FUNCTION_NAME} (payload secrets must not include the API key)"
aws lambda invoke "${args[@]}" "${OUT}" > "${OUT}.meta.json"

python3 - "${OUT}.meta.json" "${OUT}" <<'PY'
import base64
import json
import sys

meta_path, out_path = sys.argv[1], sys.argv[2]
meta = json.loads(open(meta_path, encoding="utf-8").read())
body = open(out_path, encoding="utf-8").read()
print("StatusCode:", meta.get("StatusCode"))
print("FunctionError:", meta.get("FunctionError") or "none")
print("Response:", body)
log = meta.get("LogResult")
if log:
    decoded = base64.b64decode(log).decode("utf-8", errors="replace")
    print("--- CloudWatch tail ---")
    print(decoded)
PY
