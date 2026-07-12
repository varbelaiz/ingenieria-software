#!/usr/bin/env pwsh
# Prep para grabar el video de Fase 3.
# Levanta los stacks (data + ml), siembra bronze, corre dbt hasta ml_features y
# verifica. Deja las env vars host seteadas EN ESTA SESION, asi que los comandos
# de la demo (train / promote / uvicorn / curl) hay que correrlos en la MISMA
# terminal. Requiere Docker Desktop corriendo.
#
#   pwsh -File scripts/video-fase3-prep.ps1

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)  # raiz del repo

$data = @('--env-file', '.env.data', '-f', 'docker-compose.data.yml')
$ml   = @('-f', 'docker-compose.ml.yml')

# 0. Docker vivo?
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker no responde. Abri Docker Desktop y reintenta.' }

# 1. .env.data (lo pide docker-compose.data.yml)
if (-not (Test-Path .env.data)) { Copy-Item .env.data.example .env.data; Write-Host 'Creado .env.data' }

# 2. Env de sesion para los comandos host. train/API defaultean a 5432 (puerto
#    interno del contenedor); en el host el warehouse esta publicado en 5433.
$env:WAREHOUSE_HOST = 'localhost'; $env:WAREHOUSE_PORT = '5433'
$env:WAREHOUSE_USER = 'warehouse'; $env:WAREHOUSE_PASSWORD = 'warehouse'; $env:WAREHOUSE_DB = 'warehouse'
$env:DBT_WAREHOUSE_HOST = 'localhost'; $env:DBT_WAREHOUSE_PORT = '5433'
$env:DBT_WAREHOUSE_USER = 'warehouse'; $env:DBT_WAREHOUSE_PASSWORD = 'warehouse'; $env:DBT_WAREHOUSE_DB = 'warehouse'
$env:MLFLOW_TRACKING_URI = 'http://localhost:5000'
$env:MLFLOW_EXPERIMENT_NAME = 'well-production-forecast'
$env:MLFLOW_MODEL_NAME = 'well-production-forecast'
# MLflow imprime emojis al cerrar cada run; sin UTF-8 la consola Windows tira
# UnicodeEncodeError y el training crashea.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:API_KEY = ((Select-String '^API_KEY=' .env).Line -split '=', 2)[1]

# 3. Levantar stacks. down -v primero para arrancar pristino: sin volumenes viejos
#    no hay data stale (p.ej. filas con nulls que rompen los tests de dbt) ni un
#    champion viejo en MLflow que bloquee la promocion en vivo. MLflow queda VACIO:
#    los runs y el champion se crean durante la grabacion (pasos 3-4 del guion).
Write-Host 'Reset limpio (down -v)...'
docker compose @data down -v 2>$null
docker compose @ml down -v 2>$null
Write-Host 'Levantando warehouse + Dagster...'
docker compose @data up -d
Write-Host 'Levantando MLflow...'
docker compose @ml up -d

# 4. Esperar warehouse healthy
Write-Host 'Esperando warehouse (healthy)...' -NoNewline
$wid = docker compose @data ps -q warehouse
for ($i = 0; $i -lt 40; $i++) {
    $h = docker inspect --format '{{.State.Health.Status}}' $wid 2>$null
    if ($h -eq 'healthy') { break }
    Write-Host '.' -NoNewline; Start-Sleep 2
}
Write-Host ''
if ($h -ne 'healthy') { throw 'warehouse no llego a healthy' }

# 5. Esperar MLflow (best-effort, no bloquea)
Write-Host 'Esperando MLflow...' -NoNewline
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-WebRequest 'http://localhost:5000/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; break }
    catch { Write-Host '.' -NoNewline; Start-Sleep 2 }
}
Write-Host ''

# 6. Seed bronze + dbt hasta el feature store
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold ml_features `
    --project-dir data_platform/transform --profiles-dir data_platform/transform

# 7. Verificacion
Write-Host "`n=== Feature store (ml_features.well_monthly_features) ==="
docker compose @data exec -T warehouse psql -U warehouse -d warehouse `
    -c 'select count(*) as filas from ml_features.well_monthly_features;'

Write-Host "`nListo para grabar."
Write-Host '  Dagster : http://localhost:3001'
Write-Host '  MLflow  : http://localhost:5000'
Write-Host '  API_KEY, WAREHOUSE_* y MLFLOW_* estan seteadas en ESTA terminal.'
Write-Host '  Corre train/promote/uvicorn/curl aca mismo (ver docs/fase-3-video.md).'
