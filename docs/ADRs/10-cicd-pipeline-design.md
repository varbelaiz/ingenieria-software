---
status: Aceptado
date: 2026-04-28
decision-makers: Valentino Arbelaiz
consulted:
informed:
---

# Diseño del Pipeline CI/CD con OIDC y Branch Protection

## Contexto y Declaración del Problema

El proyecto usa GitHub Actions como plataforma de CI/CD al estar el repositorio en GitHub. Se deben definir la estrategia de autenticación con AWS, el diseño de los jobs del pipeline y las reglas de protección de ramas.

## Impulsores de la Decisión

* Ejecutar lint, tests y escaneo de seguridad automáticamente en cada PR y push.
* Desplegar a staging (`develop`) y prod (`main`) sin intervención manual.
* Autenticar con AWS sin gestionar credenciales estáticas de larga duración.
* Impedir merges que rompan el pipeline.
* Evitar deploys innecesarios cuando los cambios no afectan la API ni el stack de monitoreo.

## Opciones Consideradas — Autenticación con AWS

* **IAM Access Keys estáticas** guardadas como secrets en GitHub.
* **OIDC (OpenID Connect)** con un IAM role que GitHub Actions asume por request.

## Resultado de la Decisión

**Autenticación:** OIDC con `aws-actions/configure-aws-credentials` y `role-to-assume`.  
**Branch protection:** CI requerido (`lint` y `test`) + PR obligatorio antes de mergear.

Las IAM Access Keys estáticas son credenciales de larga duración: si se filtran, son válidas hasta ser rotadas manualmente. OIDC genera credenciales temporales por request mediante un token firmado por GitHub, lo que es la práctica recomendada de AWS para autenticación desde pipelines. El IAM role restringe el acceso únicamente a los refs `main` y `develop`, acotando el blast radius ante un token comprometido.

El pipeline de CI se divide en tres jobs paralelos: `lint` (pre-commit hooks), `test` (pytest con coverage) y `scan` (Trivy). Los dos primeros son requeridos por branch protection; `scan` es informativo. El pipeline de CD usa path filtering (`dorny/paths-filter`) para correr `build-and-push` solo cuando cambia código de la API, y `deploy` cuando cambia la API o el stack de monitoreo, evitando deploys innecesarios.

### Consecuencias

**Pros**

* OIDC elimina la gestión de credenciales estáticas y reduce el riesgo de filtración.
* Branch protection garantiza que ningún merge pase sin CI verde.
* Los jobs paralelos reducen el tiempo total del pipeline respecto a una ejecución secuencial.
* El path filtering evita rebuilds y deploys ante cambios que no afectan la aplicación (docs, tests).

**Cons**

* El IAM role de OIDC se crea solo en el workspace `prod` de Terraform (ver ADR-09), generando una dependencia de inicialización entre workspaces.
* No se requiere review de otro miembro del equipo como condición de merge, lo que puede permitir merges sin segunda revisión.

### Confirmación

Confirmado en `.github/workflows/ci.yml`: jobs `lint`, `test` y `scan` en paralelo. Confirmado en `.github/workflows/cd.yml`: autenticación OIDC con `role-to-assume`, path filtering con `dorny/paths-filter`, deploy vía SSM. Confirmado en branch protection de GitHub: `CI / lint` y `CI / test` marcados como Required.
