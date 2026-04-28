# Ops

## Deploy

El pipeline de CD se dispara automáticamente con cada push a las ramas principales:

| Rama | Ambiente |
|------|----------|
| `develop` | staging |
| `main` | prod |

El CD detecta qué cambió y actúa en consecuencia:

- Si cambiaron archivos de la API (`app/`, `Dockerfile`, `pyproject.toml`, `uv.lock`): construye una nueva imagen Docker y la sube a ECR.
- Si cambiaron archivos del stack (`grafana/`, `prometheus/`, `docker-compose.prod.yml`) o la imagen: conecta a la EC2 via AWS SSM, hace pull de la imagen y reinicia el stack.

No se requiere acceso SSH directo a la instancia.

## Secretos

Los secretos viven en **AWS Secrets Manager**:

- `api/api-key-{env}` — API key de la aplicación
- `grafana/admin-password-{env}` — contraseña admin de Grafana

Al iniciar o reiniciar, la EC2 ejecuta `scripts/write_runtime_env.sh`, que lee ambos secretos y genera el archivo `.env` con permisos restringidos.

Para **rotar un secreto**: actualizar el valor en AWS Secrets Manager y luego triggerear un nuevo deploy (push a la rama correspondiente). El próximo arranque del stack tomará el valor nuevo.

## Monitoreo en producción

- Grafana: `http://<EC2_IP>:3000`
- Credenciales: las almacenadas en Secrets Manager (`grafana/admin-password-{env}`)
- Prometheus: `http://<EC2_IP>:9090`

La IP pública de la instancia está disponible como output de Terraform (`app_public_ip`).

## Load testing remoto

Para correr Locust contra el ambiente de producción o staging, ver [Load Testing](load-testing.md#ejecución-contra-aws). Conviene ejecutarlo cerca de la instancia para obtener latencias representativas.
