#!/usr/bin/env bash
# Deploy S1.4 + S1.5 (Secrets Manager, Lambda IAM role, S3 raw/curated).
# Does not print secret values. Requires AWS CLI v2 and credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="${ROOT}/infra/cloudformation/s1-secrets-iam-s3.yaml"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-sa-east-1}}"
STACK_NAME="${STACK_NAME:-preditor-falhas-s1}"
BUCKET_NAME="${BUCKET_NAME:-preditor-falhas-ml}"
SECRET_NAME="${SECRET_NAME:-RIPE_ATLAS_API_KEY}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-preditor-falhas-collector}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
  exit 1
fi

echo "==> Region: ${REGION}"
echo "==> Stack:  ${STACK_NAME}"
echo "==> Bucket: ${BUCKET_NAME}"

if ! aws sts get-caller-identity --region "${REGION}" >/dev/null 2>&1; then
  echo "No AWS credentials. Prefer: aws login (CLI >= 2.32)." >&2
  echo "This Cloud Agent can also use env AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION." >&2
  exit 1
fi

aws cloudformation deploy \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "BucketName=${BUCKET_NAME}" \
    "SecretName=${SECRET_NAME}" \
    "LambdaFunctionName=${LAMBDA_FUNCTION_NAME}"

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
