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
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id ${secret_name} \
  --region ${region} \
  --query SecretString \
  --output text)

cat > /opt/app/.env <<ENVFILE
ECR_REGISTRY=${ecr_registry}
ECR_REPOSITORY=${ecr_repo}
ENVIRONMENT=${env_name}
API_KEY=$API_KEY
ENVFILE

# ─── Stack ───────────────────────────────────────────────────────────────────
docker compose -f docker-compose.prod.yml up -d
