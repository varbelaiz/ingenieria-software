# ADR-24: CI/CD para pipelines de ML

```
status: Propuesto
date: 2026-06-25
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La consigna exige que los pipelines de procesamiento se desplieguen mediante CI/CD. En
esta entrega no hay servicio live en produccion, por lo que el objetivo practico es que
cada PR valide automaticamente los componentes de ML Engineering: feature store,
training, registry, orquestacion y contrato API.

## Impulsores de la decision

* Mantener checks automaticos por PR.
* No depender de secretos reales ni servicios externos.
* Reutilizar la infraestructura de GitHub Actions ya existente.
* Validar dbt, Dagster, training smoke y tests de API/registry.
* Dejar comandos locales equivalentes para reproducir fallas.

## Opciones consideradas

* **GitHub Actions** - CI ya configurado en el repo, con soporte para service containers y
  jobs independientes.
* **Deploy manual/local** - rapido para una demo, pero no cumple automatizacion ni deja
  evidencia en PRs.
* **Dagster Cloud u orquestador gestionado** - potente para operacion, pero excede el
  alcance local y agrega costo/cuenta externa.
* **Jenkins/GitLab CI** - validos, pero no estan integrados con este repositorio.

## Resultado de la decision

Opcion propuesta: **GitHub Actions como CI/CD de pipelines ML**.

El repositorio ya valida API, dbt, Dagster, DataHub y Metabase con GitHub Actions. Extender
esa misma plataforma para ML mantiene una unica superficie de CI, evita nuevos servicios
y permite usar Postgres como service container para smoke tests. El despliegue live queda
fuera de alcance por consigna, pero CI debe demostrar que los pipelines se pueden construir
y ejecutar de forma reproducible.

## Consecuencias

**Pros**

* Cada PR deja evidencia automatica de integracion.
* No se introducen proveedores nuevos.
* Los fallos de training/registry/API se detectan antes del merge.
* Los comandos locales pueden copiarse del workflow.

**Cons**

* Los smoke tests deben ser chicos para no volver lenta la CI.
* La CI no reemplaza una operacion productiva real de modelos.
* Puede requerir fixtures reducidas para evitar depender de datos externos.

## Confirmacion esperada

Confirmar en PR 8 con jobs CI de ML, smoke training, validacion de Dagster definitions,
tests de registry/API y documentacion de comandos locales equivalentes.

## Confirmacion PR 8

Confirmado en PR 8 con cambios en `.github/workflows/ci.yml`:

* el job `dbt-test` construye y testea el modelo `ml_features` junto con silver y gold
  (`dbt build --select silver gold ml_features`), corriendo sus data tests dbt (`not_null`,
  `unique_combination_of_columns`) contra el Postgres del CI;
* nuevo job `ml-pipeline-smoke`: seed bronze -> `dbt build` de silver/gold/ml_features ->
  `python -m ml.training.train --as-of-date 2024-12-31` leyendo del feature store persistido
  con MLflow file-store (sin server) -> tests de orquestacion ML;
* el job `test` mide cobertura del paquete `ml` (`--cov=ml`);
* la validacion de Dagster definitions (`dagster-validate`) instala el grupo `ml` porque el
  modulo de orquestacion ahora importa `ml.*`.

Los comandos locales equivalentes estan documentados en `docs/runbooks/ml-engineer.md`.

