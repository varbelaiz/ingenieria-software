# ADR-11: Herramienta de orquestación

```
status: Aceptado
date: 2026-06-04
decision-makers: Equipo de Desarrollo
```

## Contexto y declaración del problema

La Fase 2 requiere un orquestador con DAGs definidos como código, con idempotencia,
retries con backoff y observabilidad mínima (logs y status accesibles). Debe poder
reprocesar datos por fecha (backfill) e integrarse con dbt y con la plataforma de
gobierno (DataHub).

## Impulsores de la decisión

* DAGs/flows como código versionado.
* Idempotencia y backfill por fecha de primera clase.
* Retries con backoff exponencial.
* Observabilidad (UI con logs y status por corrida).
* Integración con dbt y con DataHub para lineage.

## Opciones consideradas

* **Apache Airflow** — el orquestador más maduro y difundido; modelo task-céntrico.
* **Dagster** — orquestador asset-céntrico (software-defined assets); lineage y
  particiones nativas.
* **Prefect** — orientado a flows en Python puro, muy liviano.

## Resultado de la decisión

Opción elegida: **Dagster**.

Airflow es el estándar de facto y el que más material de soporte tiene, pero su modelo
es task-céntrico: la idempotencia y el lineage hay que construirlos a mano (cada task no
"sabe" qué dato produce). Dagster modela el pipeline como **assets** con **particiones**:
reprocesar una fecha es re-materializar su partición, lo que da idempotencia y backfill
casi gratis, y expone lineage de datos que DataHub puede ingerir directamente. Prefect es
el más liviano pero su modelo de assets/lineage es menos maduro que el de Dagster y su
integración con dbt y DataHub es más artesanal.

Para un pipeline cuyo requisito central es "reprocesable por fecha + idempotente + con
lineage", el modelo de assets de Dagster reduce la cantidad de código propio necesario
para cumplirlos. Si el equipo tuviera más familiaridad previa con Airflow, ese sería un
driver fuerte a favor de Airflow; en ausencia de eso, Dagster minimiza el trabajo a medida.

## Consecuencias

**Pros**

* Particiones + assets dan idempotencia y backfill por fecha nativos.
* El lineage de assets se ingiere directo en DataHub.
* La UI provee logs y status por corrida (observabilidad mínima cubierta).

**Cons**

* La comunidad y el material de soporte son menores que los de Airflow.
* Agrega un daemon adicional al stack (webserver + daemon).

## Confirmación

Confirmado en `data_platform/orchestration/`: los modelos dbt se exponen como assets de
Dagster vía `@dbt_assets` (`assets/transform.py`), conectados a los assets de bronze a
través de un `DagsterDbtTranslator`. El grafo muestra `bronze -> silver -> gold` con cada
modelo como nodo y los tests dbt como asset checks; particiones mensuales con backfill por
fecha (`reprocess_period`), `RetryPolicy` con backoff en la extracción, y un asset job
(`end_to_end_data_job`) con hook de alerta ante fallas de calidad.
