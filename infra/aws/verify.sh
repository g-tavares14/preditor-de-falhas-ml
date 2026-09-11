#!/usr/bin/env bash
# Prove S1.4/S1.5 without printing secret values.
set -euo pipefail

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-sa-east-1}}"
STACK_NAME="${STACK_NAME:-preditor-falhas-s1}"
BUCKET_NAME="${BUCKET_NAME:-preditor-falhas-ml}"
SECRET_NAME="${SECRET_NAME:-RIPE_ATLAS_API_KEY}"

fail=0
note() { printf '%s\n' "$*"; }
ok() { printf 'OK  %s\n' "$*"; }
bad() { printf 'FAIL %s\n' "$*"; fail=1; }

if ! aws sts get-caller-identity --region "${REGION}" >/dev/null 2>&1; then
  bad "aws sts get-caller-identity (no credentials)"
  exit 1
fi
ok "sts get-caller-identity"

account="$(aws sts get-caller-identity --query Account --output text)"
role_arn="$(aws cloudformation describe-stacks \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaRoleArn'].OutputValue" \
  --output text)"
secret_arn="$(aws cloudformation describe-stacks \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='SecretArn'].OutputValue" \
  --output text)"
fn_name="$(aws cloudformation describe-stacks \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionName'].OutputValue" \
  --output text)"
fn_name="${fn_name:-preditor-falhas-collector}"

if aws secretsmanager describe-secret --region "${REGION}" --secret-id "${SECRET_NAME}" \
  --query '{Name:Name,ARN:ARN}' --output table >/dev/null; then
  ok "secretsmanager describe-secret ${SECRET_NAME}"
else
  bad "secretsmanager describe-secret ${SECRET_NAME}"
fi

# Length only — never print SecretString
secret_len="$(aws secretsmanager get-secret-value \
  --region "${REGION}" \
  --secret-id "${SECRET_NAME}" \
  --query 'length(SecretString)' \
  --output text 2>/dev/null || echo 0)"
if [[ "${secret_len}" =~ ^[0-9]+$ ]] && (( secret_len > 0 )); then
  ok "GetSecretValue succeeded (SecretString length=${secret_len}; value not printed)"
else
  bad "GetSecretValue / empty secret"
fi

pab="$(aws s3api get-public-access-block --region "${REGION}" --bucket "${BUCKET_NAME}" --output json 2>/dev/null || echo '{}')"
if echo "${pab}" | grep -q '"BlockPublicAcls": true' \
  && echo "${pab}" | grep -q '"BlockPublicPolicy": true' \
  && echo "${pab}" | grep -q '"IgnorePublicAcls": true' \
  && echo "${pab}" | grep -q '"RestrictPublicBuckets": true'; then
  ok "S3 Block Public Access all-on"
else
  bad "S3 Block Public Access not fully on: ${pab}"
fi

own="$(aws s3api get-bucket-ownership-controls --region "${REGION}" --bucket "${BUCKET_NAME}" --output json 2>/dev/null || echo '{}')"
if echo "${own}" | grep -q '"ObjectOwnership": "BucketOwnerEnforced"'; then
  ok "S3 ObjectOwnership BucketOwnerEnforced (ACLs off)"
else
  bad "S3 ObjectOwnership not BucketOwnerEnforced: ${own}"
fi

if aws s3api head-object --region "${REGION}" --bucket "${BUCKET_NAME}" --key "raw/measurements/.keep" >/dev/null 2>&1 \
  && aws s3api head-object --region "${REGION}" --bucket "${BUCKET_NAME}" --key "curated/.keep" >/dev/null 2>&1; then
  ok "prefix placeholders raw/measurements/.keep and curated/.keep"
else
  bad "prefix placeholders missing (run deploy.sh)"
fi

# Optional PutObject with caller identity (not the Lambda role). Object is deleted.
probe_key="raw/measurements/_verify/${account}.txt"
if printf 'verify\n' | aws s3 cp - "s3://${BUCKET_NAME}/${probe_key}" --region "${REGION}" >/dev/null \
  && aws s3 rm "s3://${BUCKET_NAME}/${probe_key}" --region "${REGION}" >/dev/null; then
  ok "optional PutObject+delete as caller (not Lambda role)"
else
  note "optional PutObject as caller skipped/failed (IAM user may be write-restricted; Lambda role is the writer)"
fi

if [[ -n "${role_arn}" && "${role_arn}" != "None" ]]; then
  note "==> iam simulate-principal-policy for ${role_arn}"
  sim="$(aws iam simulate-principal-policy \
    --policy-source-arn "${role_arn}" \
    --action-names secretsmanager:GetSecretValue s3:PutObject s3:GetObject logs:PutLogEvents \
    --resource-arns \
      "${secret_arn}" \
      "arn:aws:s3:::${BUCKET_NAME}/raw/measurements/x.jsonl" \
      "arn:aws:s3:::${BUCKET_NAME}/curated/log_rede.csv" \
      "arn:aws:logs:${REGION}:${account}:log-group:/aws/lambda/${fn_name}:*" \
    --output json)"
  if printf '%s' "${sim}" | python3 -c '
import json,sys
doc=json.load(sys.stdin)
denied=False
for r in doc.get("EvaluationResults", []):
    name=r.get("EvalActionName")
    decision=r.get("EvalDecision")
    print(f"  {decision:12} {name}")
    if decision != "allowed":
        denied=True
sys.exit(2 if denied else 0)
'; then
    ok "role simulation GetSecretValue + Put/GetObject + PutLogEvents = allowed"
  else
    bad "role simulation denied something"
    echo "${sim}"
  fi
else
  bad "LambdaRoleArn output missing"
fi

note ""
note "Region used: ${REGION}  Account: ${account}"
if [[ "${fail}" -ne 0 ]]; then
  note "Verification failed."
  exit 1
fi
note "Verification passed (secret value was not printed)."
