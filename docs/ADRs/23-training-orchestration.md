# ADR-23: Orquestacion de entrenamiento y retraining

```
status: Propuesto
date: 2026-06-25
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La Fase 3 exige repetir el proceso de entrenamiento para un dia dado y ejecutar
entrenamiento/despliegue de modelos de manera recurrente y automatica. La plataforma ya
usa Dagster para orquestar la capa de datos, con assets, particiones, schedules y
validacion en CI.

## Impulsores de la decision

* Ejecutar retraining parametrizado por `as_of_date`.
* Disparar retraining manual para la demo.
* Programar retraining recurrente.
* Observar estado, logs y fallas desde una UI local.
* Reutilizar la orquestacion existente sin sumar otro stack.

## Opciones consideradas

* **Dagster** - jobs/assets/schedules definidos como codigo, UI local y reutilizacion del
  stack de Fase 2.
* **GitHub Actions scheduled workflow** - simple para cron, pero pobre para observar
  lineage, estado de assets y triggers parametrizados desde UI.
* **Apache Airflow** - maduro para DAGs, pero agregaria un segundo orquestador al repo.

## Resultado de la decision

Opcion propuesta: **Dagster para retraining ML**.

Dagster ya esta incorporado, validado en CI y documentado para reprocesos por fecha. Usar
un `train_model_job` parametrizable por `as_of_date` permite demostrar retraining manual
desde la UI y schedule recurrente sin sumar Airflow ni depender de GitHub Actions para la
operacion diaria. GitHub Actions queda mejor ubicado como CI/CD de validacion de
pipelines, no como orquestador principal de ML.

## Consecuencias

**Pros**

* Unifica pipelines de datos y ML en el mismo orquestador.
* Permite mostrar trigger manual y schedule en la demo.
* Reutiliza patrones de assets, jobs y validations ya presentes.
* Evita operar Airflow solo para esta fase.

**Cons**

* Aumenta la responsabilidad del stack Dagster local.
* Hay que cuidar que el job de training no quede acoplado a estado local no reproducible.
* GitHub Actions seguira siendo necesario para validar cambios antes de mergear.

## Confirmacion esperada

Confirmar en PR 7 con `train_model_job`, schedule recurrente, config por `as_of_date`,
validacion de definitions y runbook de trigger manual.

## Confirmacion PR 7

Confirmado en PR 7 con:

* `data_platform/orchestration/assets/ml.py`: assets particionados por mes
  `ml_trained_model` y `ml_promoted_model`, downstream del modelo dbt `ml_features`. El
  training lee point-in-time del feature store persistido, registra el run en MLflow y la
  promocion reutiliza la politica de MAE de ADR-22.
* `train_model_job` (`data_platform/orchestration/jobs.py`) y `ml_retraining_schedule`
  (`data_platform/orchestration/schedules.py`, mensual, dia 2 a las 04:00 ART). Retrain
  para un `as_of_date` dado = materializar esa particion (manual desde la UI de Dagster).
* El job de datos excluye el grupo `ml` para no reentrenar como efecto colateral.
* `tests/test_ml_orchestration.py`: wiring de assets/job/schedule/deps y smoke de
  materializacion punta a punta.
* Runbook de trigger manual en `docs/runbooks/ml-engineer.md`.

