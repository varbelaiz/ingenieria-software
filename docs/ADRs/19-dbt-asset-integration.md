# ADR-19: Integración de dbt en Dagster

```
status: Aceptado
date: 2026-06-15
decision-makers: Equipo de Desarrollo
```

## Contexto y declaración del problema

[ADR-11](11-orchestration-tool.md) eligió Dagster como orquestador. Queda una decisión
separada: **cómo integrar dbt dentro de Dagster**. La primera implementación corría todo
el proyecto dbt como un único op que invocaba `dbt build` por subprocess; en el grafo de
Dagster eso es un solo nodo opaco que no expone qué modelos produce ni el estado de cada
test. La plataforma necesita lineage por modelo (para DataHub), idempotencia y backfill por
fecha, y observabilidad de la calidad por modelo, no solo un pass/fail global del job.

## Impulsores de la decisión

* Lineage a nivel modelo (`bronze → silver → gold`) navegable en la UI y exportable a
  DataHub.
* Idempotencia y backfill por fecha de primera clase (re-materializar una partición).
* Resultado de calidad por modelo: cada test dbt visible de forma individual.
* Freshness fail-fast: una fuente vieja debe cortar antes de transformar.
* Mantenimiento mínimo: el grafo no debe duplicar a mano la estructura del proyecto dbt.

## Opciones consideradas

* **Op único `dbt build` (subprocess)** — un solo op corre todo el proyecto. Simple, pero
  opaco: un nodo en el grafo, sin lineage por modelo ni tests individuales.
* **`@dbt_assets` (dagster-dbt)** — la integración oficial lee el `manifest.json` de dbt y
  genera un asset por modelo y un asset check por test, manteniendo el grafo en sync con el
  proyecto dbt de forma automática.
* **Assets de Dagster escritos a mano, uno por modelo** — control total, pero hay que
  mantener a mano un asset por cada modelo dbt; se descarta por costo de mantenimiento y
  riesgo de drift respecto del proyecto dbt.

## Resultado de la decisión

Opción elegida: **`@dbt_assets` (dagster-dbt)**.

El op único era el camino más corto pero contradice la razón por la que se eligió Dagster
en ADR-11: su modelo asset-céntrico. Con `@dbt_assets`, cada modelo dbt es un asset de
Dagster y cada test es un asset check, derivados del `manifest.json`, así que el grafo
queda en sync con el proyecto dbt sin código a medida. Un `DagsterDbtTranslator` mapea las
fuentes dbt de bronze a las keys de los assets de bronze (`bronze_<tabla>`), conectando la
extracción con la transformación en un solo grafo `bronze → silver → gold`. El asset corre
`dbt source freshness` (fail-fast) antes de `dbt build`, y la partición mensual se inyecta
como `--vars reprocess_period=<partición>`. Los assets escritos a mano dan el mismo
resultado pero exigen mantener el grafo en paralelo al proyecto dbt, con riesgo de drift.

## Consecuencias

**Pros**

* El lineage por modelo se expone nativo en la UI y se ingiere directo en
  DataHub (refuerza [ADR-17](17-data-governance.md)).
* Cada test dbt es un asset check individual: la calidad se observa por
  modelo, no solo como pass/fail del job ([ADR-16](16-data-quality.md)).
* El grafo se deriva del `manifest.json`: no hay que mantener a mano un asset
  por modelo.

**Cons**

* Acopla la orquestación a `dagster-dbt` y obliga a generar el `manifest.json`
  (paso de build adicional, también en CI).
* Debuggear un fallo de dbt exige leer tanto el log del asset en Dagster como
  las filas persistidas por `store_failures`.

## Confirmación

Confirmado en `data_platform/orchestration/assets/transform.py`: `@dbt_assets` con
`BronzeSourceTranslator` y particiones mensuales; el manifest se genera en
`dbt_project.py`; los assets quedan registrados en `__init__.py` y se ejecutan vía
`end_to_end_data_job` (`AssetSelection.all()`). Cobertura en `tests/test_dbt_assets.py`.
