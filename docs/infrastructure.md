# Infraestructura

La infraestructura está definida como código con Terraform en el directorio `infra/`. Se despliega en AWS y soporta dos ambientes independientes mediante workspaces.

## Ambientes

| Workspace | Rama git | Uso |
|-----------|----------|-----|
| `staging` | `develop` | Validación pre-producción |
| `prod` | `main` | Producción |

Cada workspace crea sus propios recursos aislados en AWS.

## Backend de estado

El estado de Terraform se almacena en S3:

- **Bucket**: `ing-soft-tf-state`
- **Región**: `us-east-2`

## Recursos por ambiente

| Recurso | Detalle |
|---------|---------|
| **EC2** | `t3.micro`, Amazon Linux 2023; ejecuta el stack Docker Compose |
| **ECR** | Repositorio `api-{workspace}`; lifecycle policy retiene las últimas 5 imágenes |
| **Secrets Manager** | `api/api-key-{workspace}` y `grafana/admin-password-{workspace}` |
| **Security Group** | Inbound en puertos 8000 (API), 3000 (Grafana), 9090 (Prometheus) |
| **IAM Instance Profile** | Permite a la EC2 leer de ECR y Secrets Manager |
| **IAM OIDC Role** | Solo en `prod`; usado por GitHub Actions para asumir permisos de deploy |

## Variables sensibles

Los valores reales nunca se commitean. Se pasan como variables de entorno al momento de aplicar:

```bash
TF_VAR_api_key=<valor>
TF_VAR_grafana_admin_password=<valor>
```

En producción, los secretos viven en AWS Secrets Manager. La EC2 los lee al iniciar con el script `scripts/write_runtime_env.sh`.
