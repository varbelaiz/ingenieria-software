#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log) 2>&1

# ─── Docker + Compose ────────────────────────────────────────────────────────
yum update -y
yum install -y docker git
systemctl enable --now docker

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ─── Repo ────────────────────────────────────────────────────────────────────
git clone -b ${branch} https://github.com/${github_org}/${github_repo}.git /opt/app
cd /opt/app

# ─── ECR login (via EC2 instance profile) ────────────────────────────────────
aws ecr get-login-password --region ${region} | \
  docker login --username AWS --password-stdin ${ecr_registry}

# ─── Runtime env (.env is gitignored, survives git pull) ─────────────────────
AWS_REGION=${region} \
ENVIRONMENT=${env_name} \
ECR_REGISTRY=${ecr_registry} \
ECR_REPOSITORY=${ecr_repo} \
API_KEY_SECRET_NAME=${api_key_secret_name} \
GRAFANA_ADMIN_PASSWORD_SECRET_NAME=${grafana_admin_password_secret_name} \
GF_SECURITY_ADMIN_USER=admin \
ENV_FILE=/opt/app/.env \
bash scripts/write_runtime_env.sh

# ─── Stack ───────────────────────────────────────────────────────────────────
docker compose -f docker-compose.prod.yml up -d
bash scripts/sync_grafana_admin_password.sh
