# Infraestructura

La infraestructura está definida como código con Terraform en `infra/` y se despliega en AWS. Soporta dos ambientes independientes mediante Terraform Workspaces.

## Arquitectura implementada

Cada ambiente corre en una única instancia EC2 que aloja la API, Prometheus y Grafana bajo Docker Compose:

```
workspace prod (branch: main)        workspace staging (branch: develop)
┌──────────────────────────┐         ┌──────────────────────────┐
│  EC2 t3.micro  app-prod  │         │  EC2 t3.micro app-staging│
│  ┌────────────────────┐  │         │  ┌────────────────────┐  │
│  │   API (ECR image)  │  │         │  │   API (ECR image)  │  │
│  │   Prometheus       │  │         │  │   Prometheus       │  │
│  │   Grafana          │  │         │  │   Grafana          │  │
│  └────────────────────┘  │         │  └────────────────────┘  │
└──────────────────────────┘         └──────────────────────────┘
         ECR api-prod                        ECR api-staging
```

## Estrategia de branches y ambientes (Git Flow)

El mapeo entre branches y ambientes sigue una estrategia de Git Flow:

| Branch    | Ambiente  | Terraform Workspace |
|-----------|-----------|---------------------|
| `develop` | staging   | `staging`           |
| `main`    | prod      | `prod`              |

Todo cambio pasa primero por `develop` → staging antes de mergear a `main` → prod. Las feature branches se integran a `develop` mediante PR con CI requerido.

La alternativa considerada era usar `workflow_dispatch` para triggear deploys manualmente a cualquier ambiente desde cualquier branch. Se descartó porque requiere intervención humana en cada deploy, lo que introduce inconsistencias (¿qué está desplegado en cada ambiente?) y elimina la trazabilidad automática que da el mapeo branch→ambiente.

## Recursos por ambiente

| Recurso | Detalle |
|---------|---------|
| **EC2** | `t3.micro`, Amazon Linux 2023; ejecuta el stack Docker Compose |
| **ECR** | Repositorio `api-{workspace}`; lifecycle policy retiene las últimas 5 imágenes |
| **Secrets Manager** | `api/api-key-{workspace}` y `grafana/admin-password-{workspace}` |
| **Security Group** | Inbound en puertos 8000 (API), 3000 (Grafana), 9090 (Prometheus) |
| **IAM Instance Profile** | Permite a la EC2 leer de ECR y Secrets Manager |
| **IAM OIDC Role** | Solo en workspace `prod`; usado por GitHub Actions para asumir permisos de deploy en ambos ambientes |

## Backend de estado

El estado de Terraform se almacena remotamente en S3 para permitir colaboración entre miembros del equipo:

- **Bucket**: `ing-soft-tf-state`
- **Región**: `us-east-2`
- **Locking**: nativo con `use_lockfile = true` (sin DynamoDB)

## Variables sensibles

Los valores reales nunca se commitean. Se pasan como variables de entorno al momento de aplicar:

```bash
TF_VAR_api_key=<valor>
TF_VAR_grafana_admin_password=<valor>
```

En producción, los secretos viven en AWS Secrets Manager y son inyectados en `.env` al iniciar la instancia mediante `scripts/write_runtime_env.sh`.
