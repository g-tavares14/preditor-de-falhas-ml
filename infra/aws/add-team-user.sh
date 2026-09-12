#!/usr/bin/env bash
# Create an IAM user and add them to preditor-dados-leitura (S1.5b).
# Run by the AWS account owner only — once per teammate, different USER_NAME.
# Teammates do not run this. Does not set a password or access key.
set -euo pipefail

USER_NAME="${1:?usage: add-team-user.sh <iam-user-name>}"
GROUP_NAME="${GROUP_NAME:-preditor-dados-leitura}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-sa-east-1}}"

if ! aws sts get-caller-identity --region "${REGION}" >/dev/null 2>&1; then
  echo "No AWS credentials." >&2
  exit 1
fi

if aws iam get-user --user-name "${USER_NAME}" >/dev/null 2>&1; then
  echo "==> user ${USER_NAME} already exists"
else
  aws iam create-user \
    --user-name "${USER_NAME}" \
    --tags Key=Project,Value=preditor-de-falhas-ml Key=Card,Value=S1.5b \
    >/dev/null
  echo "==> created user ${USER_NAME}"
fi

aws iam add-user-to-group --group-name "${GROUP_NAME}" --user-name "${USER_NAME}"
echo "==> ${USER_NAME} in group ${GROUP_NAME}"
echo "Next: IAM console → user → Create login password (reset required)."
echo "Do not share the Lambda role or RIPE_ATLAS_API_KEY."
