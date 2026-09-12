#!/usr/bin/env bash
# Deploy S1.4 + S1.5 + S1.5b + S1.7 (secret, role, S3, team group, Lambda,
# EventBridge). Does not print secret values. Requires AWS CLI v2, uv, zip.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="${ROOT}/infra/cloudformation/s1-secrets-iam-s3.yaml"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-sa-east-1}}"
STACK_NAME="${STACK_NAME:-preditor-falhas-s1}"
BUCKET_NAME="${BUCKET_NAME:-preditor-falhas-ml}"
SECRET_NAME="${SECRET_NAME:-RIPE_ATLAS_API_KEY}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-preditor-falhas-collector}"
PACKAGE_KEY="${COLLECTOR_PACKAGE_KEY:-artifacts/lambda/preditor-falhas-collector.zip}"
MSM_IDS="${RIPE_ATLAS_MSM_IDS:-}"
SCHEDULE_STATE="${SCHEDULE_STATE:-DISABLED}"
WINDOW="${COLLECT_WINDOW_SECONDS:-1200}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
  exit 1
fi

echo "==> Region: ${REGION}"
echo "==> Stack:  ${STACK_NAME}"
echo "==> Bucket: ${BUCKET_NAME}"
echo "==> ScheduleState: ${SCHEDULE_STATE} (kill-switch: keep DISABLED until live IDs)"
echo "==> RIPE_ATLAS_MSM_IDS set: $([ -n "${MSM_IDS}" ] && echo yes || echo no)"

if ! aws sts get-caller-identity --region "${REGION}" >/dev/null 2>&1; then
  echo "No AWS credentials. Prefer: aws login (CLI >= 2.32)." >&2
  echo "This Cloud Agent can also use env AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION." >&2
  exit 1
fi

echo "==> Package collector zip"
chmod +x "${ROOT}/infra/aws/package.sh"
"${ROOT}/infra/aws/package.sh"

echo "==> Upload zip to s3://${BUCKET_NAME}/${PACKAGE_KEY}"
aws s3 cp \
  "${ROOT}/dist/preditor-falhas-collector.zip" \
  "s3://${BUCKET_NAME}/${PACKAGE_KEY}" \
  --region "${REGION}" \
  --only-show-errors

aws cloudformation deploy \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "BucketName=${BUCKET_NAME}" \
    "SecretName=${SECRET_NAME}" \
    "LambdaFunctionName=${LAMBDA_FUNCTION_NAME}" \
    "AtlasMeasurementIds=${MSM_IDS}" \
    "ScheduleState=${SCHEDULE_STATE}" \
    "CollectorPackageKey=${PACKAGE_KEY}" \
    "CollectWindowSeconds=${WINDOW}"

echo "==> Refresh function code (CFN does not notice same-key object changes)"
aws lambda update-function-code \
  --region "${REGION}" \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --s3-bucket "${BUCKET_NAME}" \
  --s3-key "${PACKAGE_KEY}" \
  --query '{FunctionName:FunctionName,LastModified:LastModified,CodeSize:CodeSize}' \
  --output table
aws lambda wait function-updated-v2 \
  --region "${REGION}" \
  --function-name "${LAMBDA_FUNCTION_NAME}"

echo "==> Prefix placeholders (empty objects; not dataset rows)"
aws s3api put-object --region "${REGION}" --bucket "${BUCKET_NAME}" --key "raw/measurements/.keep" >/dev/null
aws s3api put-object --region "${REGION}" --bucket "${BUCKET_NAME}" --key "curated/.keep" >/dev/null

if [[ -n "${RIPE_ATLAS_API_KEY:-}" ]]; then
  echo "==> Putting RIPE_ATLAS_API_KEY (value not printed)"
  aws secretsmanager put-secret-value \
    --region "${REGION}" \
    --secret-id "${SECRET_NAME}" \
    --secret-string "${RIPE_ATLAS_API_KEY}" \
    --output text \
    --query Name >/dev/null
else
  echo "==> Skip secret value: set RIPE_ATLAS_API_KEY in the environment and re-run, or:"
  echo "    aws secretsmanager put-secret-value --region ${REGION} --secret-id ${SECRET_NAME} --secret-string \"\$RIPE_ATLAS_API_KEY\""
fi

echo "==> Stack outputs"
aws cloudformation describe-stacks \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs" \
  --output table

echo "Next: ${ROOT}/infra/aws/verify.sh"
echo "Manual invoke (schedule stays ${SCHEDULE_STATE}): ${ROOT}/infra/aws/invoke.sh"
echo "Kill-switch: aws events disable-rule --name preditor-falhas-collector-15min --region ${REGION}"
