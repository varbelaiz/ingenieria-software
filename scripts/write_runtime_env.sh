#!/bin/bash
set -euo pipefail

: "${AWS_REGION:?missing AWS_REGION}"
: "${ENVIRONMENT:?missing ENVIRONMENT}"
: "${ECR_REGISTRY:?missing ECR_REGISTRY}"
: "${ECR_REPOSITORY:?missing ECR_REPOSITORY}"

ENV_FILE=${ENV_FILE:-.env}
API_KEY_SECRET_NAME=${API_KEY_SECRET_NAME:-api/api-key-${ENVIRONMENT}}
GRAFANA_ADMIN_PASSWORD_SECRET_NAME=${GRAFANA_ADMIN_PASSWORD_SECRET_NAME:-grafana/admin-password-${ENVIRONMENT}}
GF_SECURITY_ADMIN_USER=${GF_SECURITY_ADMIN_USER:-admin}

dotenv_quote() {
  local value=$1
  value=${value//\'/\'\\\'\'}
  printf "'%s'" "$value"
}

API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id "$API_KEY_SECRET_NAME" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text)

GRAFANA_ADMIN_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id "$GRAFANA_ADMIN_PASSWORD_SECRET_NAME" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text)

tmp_file="${ENV_FILE}.tmp"
umask 077
{
  printf 'ECR_REGISTRY=%s\n' "$ECR_REGISTRY"
  printf 'ECR_REPOSITORY=%s\n' "$ECR_REPOSITORY"
  printf 'ENVIRONMENT=%s\n' "$ENVIRONMENT"
  printf 'API_KEY='
  dotenv_quote "$API_KEY"
  printf '\n'
  printf 'GF_SECURITY_ADMIN_USER=%s\n' "$GF_SECURITY_ADMIN_USER"
  printf 'GF_SECURITY_ADMIN_PASSWORD='
  dotenv_quote "$GRAFANA_ADMIN_PASSWORD"
  printf '\n'
} > "$tmp_file"

mv "$tmp_file" "$ENV_FILE"
chmod 600 "$ENV_FILE"
