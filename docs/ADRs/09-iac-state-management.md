---
status: Aceptado
date: 2026-04-28
decision-makers: Valentino Arbelaiz
consulted:
informed:
---

# Gestión de Estado de Terraform, Workspaces y Topología de Instancias

## Contexto y Declaración del Problema

Al adoptar Terraform como herramienta de IaC, se necesita decidir dónde guardar el state file, cómo separar los recursos de los ambientes `staging` y `prod`, y cómo distribuir los servicios (API y monitoreo) en instancias EC2.

## Impulsores de la Decisión

* Permitir que varios integrantes del equipo apliquen cambios de infraestructura sin pisar el state del otro.
* Evitar commitear el state al repositorio (contiene valores sensibles como ARNs, IPs y outputs de recursos).
* Mantener un único codebase de Terraform reutilizable para ambos ambientes.
* Minimizar la duplicación de código de infraestructura.
* Mantener costos dentro del presupuesto disponible para el proyecto.

## Opciones Consideradas — Topología de instancias

* **API y monitoreo en instancias separadas** — EC2 dedicada para la API, EC2 dedicada para Prometheus + Grafana, por ambiente.
* **API y monitoreo consolidados en una única instancia** por ambiente.

## Opciones Consideradas — State

* **State local** (archivo `terraform.tfstate` ignorado por git).
* **S3 como backend remoto** con bloqueo nativo (`use_lockfile = true`).
* **Terraform Cloud** como backend administrado.

## Opciones Consideradas — Separación de Ambientes

* **Dos directorios separados** (`infra/prod/`, `infra/staging/`) con su propio state.
* **Terraform Workspaces** sobre un único codebase.
* **Un solo ambiente** sin separación staging/prod.

## Resultado de la Decisión

**Topología:** API y monitoreo consolidados en una única `t3.micro` por ambiente.  
**State:** S3 como backend remoto con `use_lockfile = true`.  
**Ambientes:** Terraform Workspaces (`prod`, `staging`).

La topología ideal separa API y monitoreo en instancias distintas: aísla fallos (un problema en Grafana no afecta a la API), permite escalar cada servicio independientemente y asigna security groups específicos a cada rol. Sin embargo, Grafana requiere al menos una `t4g.nano` para funcionar de forma estable. Con cuatro instancias en total (API + monitoreo × dos ambientes) el costo mensual excedía el presupuesto del proyecto. Ante esa restricción se priorizó mantener el ambiente de staging — requerido explícitamente por el PRD — por sobre la separación de servicios. Validar cambios directamente en prod sin staging es un riesgo mayor que consolidar servicios en una misma instancia.

El state local no permite colaboración: cada miembro tendría su propia versión y los `apply` concurrentes corromperían el estado. Terraform Cloud agrega una cuenta externa innecesaria para el alcance del proyecto. S3 resuelve ambos problemas con recursos que ya se tienen en AWS y sin dependencias externas adicionales.

Los directorios separados implican duplicar todos los archivos `.tf` — cualquier cambio de infraestructura requeriría aplicarse en dos lugares. Workspaces permiten usar el mismo código parametrizado por `terraform.workspace`, eliminando la duplicación.

Un detalle de diseño resultante: el OIDC provider de GitHub Actions y el IAM role para CD son recursos globales de la cuenta AWS (no por ambiente), por lo que se crean únicamente en el workspace `prod` usando `count = local.is_prod ? 1 : 0`. Esto implica que el workspace `staging` depende de que `prod` haya sido inicializado primero.

### Consecuencias

**Pros**

* Consolidar servicios en una instancia mantiene el costo dentro del presupuesto y preserva el ambiente de staging.
* Un único codebase Terraform cubre ambos ambientes sin duplicación.
* El state remoto en S3 permite que cualquier miembro del equipo aplique cambios de forma segura.
* `use_lockfile = true` evita applies concurrentes sin necesitar una tabla DynamoDB adicional.

**Cons**

* La consolidación de servicios en una instancia elimina el aislamiento de fallos entre la API y el stack de monitoreo.
* Si el workspace `prod` es destruido, el workspace `staging` pierde el OIDC provider y el CD deja de funcionar.
* Terraform Workspaces comparten el mismo backend bucket, lo que requiere cuidado al seleccionar el workspace activo antes de cada `apply`.

### Confirmación

Confirmado en `infra/main.tf`: backend S3 con `use_lockfile = true`. Confirmado en `infra/app.tf`, `infra/iam.tf`, `infra/ecr.tf`: todos los recursos usan `terraform.workspace` para diferenciar ambientes. Confirmado en `infra/iam.tf`: OIDC provider e IAM role de GitHub Actions con `count = local.is_prod ? 1 : 0`.
