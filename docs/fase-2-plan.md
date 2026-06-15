# Plan de PRs - Fase 2: Plataforma de Datos

Fecha de entrega: 2026-06-15

## Contexto y alcance

La Fase 2 construye una **plataforma de datos** completa sobre datos reales de
producción de pozos no convencionales de Argentina (datos.gob.ar), reutilizando la base
de la Fase 1 (Docker Compose, estructura `docs/ADRs/`, CI con GitHub Actions, convención
de commits y Git Flow). El eje deja de ser "servir una API mock" y pasa a ser
"extraer → transformar (medallion) → modelar (estrella) → validar (calidad) → gobernar
→ exponer (BI)".

La pieza que resuelve la mayor cantidad de requisitos de una sola vez es **dbt**: cubre
medallion, modelo estrella, calidad persistida, documentación del modelo, lineage y el
bonus de semantic layer. Es la columna vertebral del stack.

## Stack elegido

| Capa | Herramienta | Alternativas (ver ADR) | Requisito que cubre |
|------|-------------|------------------------|---------------------|
| Orquestación | **Dagster** | Airflow, Prefect | DAGs-as-code, idempotencia, retries, observabilidad |
| Warehouse | **PostgreSQL** | DuckDB, BigQuery | Modelo estrella, multiusuario, BI + gobierno |
| Transformación / medallion / estrella | **dbt (dbt-postgres)** | SQL plano, Spark | Medallion, estrella, doc del modelo, lineage |
| Calidad | **dbt tests + dbt-expectations + `store_failures`** | Great Expectations, Soda | Checks persistidos con consecuencia operativa |
| Gobierno | **DataHub** | OpenMetadata, Amundsen | Workflows, DW, freshness, lineage tabla |
| BI | **Metabase** | Superset, Looker Studio | Acceso de usuarios no técnicos |
| Semantic layer (bonus) | **vistas lógicas / dbt metrics** | Cube.dev | Métricas definidas una vez |

## Nota de despliegue

El stack de datos (Dagster + Postgres + DataHub + Metabase) es **demasiado pesado para
la `t3.micro` de Fase 1** — DataHub solo ya requiere Kafka + Elasticsearch + un store de
metadata. Decisión: el stack de datos de Fase 2 corre **localmente vía Docker Compose**
(documentado en el README), mientras que la API y el monitoreo de Fase 1 permanecen en
AWS. Esto se justifica brevemente en el README; no es un ADR obligatorio de la consigna,
pero conviene dejarlo explícito.

## Estrategia de branching

Se mantiene el **Git Flow** ya establecido en Fase 1: las feature branches salen de
`develop`, se mergean a `develop` (→ staging) mediante PR con CI requerido, y al final
`develop` → `main` (→ prod).

**Todos los PR de la Fase 2 apuntan a `develop`** (ninguno apunta a otra feature
branch). Esto es deliberado: la regla de protección que exige review obligatorio se aplica
sobre la branch **destino** del PR, así que para que *todo* PR pase por review, todos
deben aterrizar en una branch protegida (`develop`). Apuntar un PR a otra feature branch
lo dejaría fuera de la regla **y** impediría pushear a esa branch mientras se desarrolla
(la regla `pull_request` prohíbe el push directo a su destino) — los dos motivos por los
que NO se usa branching apilado (stacked) acá.

Las branches cuyo trabajo depende de otra anterior se **anidan localmente** (se crean a
partir de la branch previa para tener su código), pero el PR sigue apuntando a `develop`.
Se mergean **en orden, bottom-up**, con **merge commit** (no squash): así `develop` queda
con los commits reales del padre y el diff del hijo se limpia solo al re-basearse. Con
squash habría que `rebase --onto` + force-push en cada paso.

```
develop ──●  (todas las feature salen de aca; todos los PR apuntan aca)
           │
           ├─ feature/data-platform-scaffolding   PR 1 → develop   (incluye bronze)
           ├─ feature/silver-transformations      PR 2 → develop   depende de PR1
           ├─ feature/gold-star-schema            PR 3 → develop   depende de PR2
           ├─ feature/data-quality                PR 4 → develop   depende de PR3
           ├─ feature/orchestration-hardening     PR 5 → develop   depende de PR4
           ├─ feature/governance-datahub          PR 6 → develop   depende de gold (PR3)
           ├─ feature/bi-metabase                 PR 7 → develop   depende de gold (PR3)
           └─ feature/docs-runbooks               PR 8 → develop   al final

Orden de merge: bottom-up segun dependencia (PR1 → PR2 → PR3 → ...), con merge commit.
"depende de" = se anida local sobre esa branch, pero el PR apunta a develop igual.
```

> **Nota:** en la versión original de este plan bronze era un PR aparte apilado sobre
> scaffolding. Quedó integrado en `feature/data-platform-scaffolding` (vía su propio PR de
> review), así que viaja junto a scaffolding en el PR 1. Por eso la numeración de PR de
> abajo se mantiene, pero el branching real es plano contra `develop`.

### Protección de branches (ruleset)

Un único ruleset de GitHub protege **`main` y `develop`** (no `~ALL`) con: PR obligatorio
con **≥1 review aprobado**, **status checks requeridos** (`lint` + `test`), bloqueo de
**deletion** y **non-fast-forward**. Las `feature/*` quedan **libres** para pushear y
borrar (son solo origen de PR, nunca destino), lo que evita bloquear a los colaboradores
en sus propias branches.

Convención de nombres de branch: `feature/<nombre>`. Convención de commits: Conventional
Commits (`feat:`, `chore:`, `docs:`, `test:`, `ci:`), igual que Fase 1.

Estructura de carpetas nueva (sugerida):

```
data_platform/
├── extraction/        # clientes de descarga de datos.gob.ar
├── orchestration/     # definiciones de Dagster (assets, jobs, schedules, partitions)
├── transform/         # proyecto dbt (models/bronze, models/silver, models/gold)
└── governance/        # recipes de ingesta de DataHub
docs/
├── ADRs/              # ADR-11 .. ADR-16 (+ 17, 18)
├── runbooks/          # data-engineer.md, bi-user.md
└── data-model.md      # documentación del modelo dimensional
```

---

## PR 1: `feature/data-platform-scaffolding`

**Branch:** `feature/data-platform-scaffolding` ← `develop`
**PR target:** `develop`
**Descripción:** Cimientos del stack de datos: Postgres como warehouse, Dagster como
orquestador, proyecto dbt inicializado y estructura de carpetas.

**Commits:**

1. `feat: add postgres warehouse and dagster to docker-compose`
   - `docker-compose.data.yml` — servicios `warehouse` (Postgres 16), `dagster-webserver`,
     `dagster-daemon`, con volúmenes persistentes
   - `.env.data.example` — credenciales de Postgres, puertos

2. `chore: initialize dbt project (dbt-postgres)`
   - `data_platform/transform/dbt_project.yml`
   - `data_platform/transform/profiles.yml` — perfil apuntando a Postgres, con esquemas
     `bronze`, `silver`, `gold`
   - `data_platform/transform/models/sources.yml` — declaración de fuentes (placeholders)
   - dependencias dbt en `pyproject.toml`: `dbt-core`, `dbt-postgres`, `dbt-expectations`

3. `chore: scaffold orchestration and extraction packages`
   - `data_platform/orchestration/__init__.py` — `Definitions` vacío de Dagster
   - `data_platform/extraction/__init__.py`
   - estructura de carpetas `models/bronze`, `models/silver`, `models/gold`

4. `docs: add ADR-11 (orchestration) and ADR-17 (warehouse engine)`
   - `docs/ADRs/11-orchestration-tool.md`
   - `docs/ADRs/17-warehouse-engine.md`
   - `docs/ADRs/diagram-data-architecture.html` (diagrama de la arquitectura de datos,
     estilo de los `.html` de Fase 1)

**Tests:** smoke test de que Dagster levanta el `Definitions` y dbt parsea
(`dbt parse`).

**CI:** extender `ci.yml` con un job `dbt-parse` y `dagster-validate` (no rompe el job
existente de la API).

---

## PR 2: `feature/data-extraction-bronze`

**Branch:** `feature/data-extraction-bronze` → integrada en `feature/data-platform-scaffolding`
**PR target:** se revisó en su propio PR y quedó dentro de scaffolding; llega a `develop` junto con PR 1
**Descripción:** Extracción de las dos fuentes de datos.gob.ar hacia la capa **bronze**,
idempotente y particionada.

**Commits:**

1. `feat: add extraction clients for both datasets`
   - `data_platform/extraction/produccion.py` — descarga del dataset de producción de
     pozos no convencionales (CSV)
   - `data_platform/extraction/pozos.py` — descarga del listado de pozos por operadora
   - manejo de errores HTTP, timeouts y reintentos a nivel cliente

2. `feat: add dagster assets that land raw data into bronze`
   - `data_platform/orchestration/assets/bronze.py` — assets particionados por período de
     carga, que escriben tal cual al esquema `bronze` de Postgres (sin transformar)
   - escritura idempotente: `DELETE WHERE partition` + `INSERT`, o `MERGE` por clave de
     partición (re-correr una partición no duplica)

3. `feat: declare bronze sources in dbt`
   - `data_platform/transform/models/sources.yml` — fuentes `bronze.produccion_raw` y
     `bronze.pozos_raw` con `loaded_at_field` para freshness

4. `test: add idempotency and schema tests for extraction`
   - `tests/test_extraction_idempotency.py` — correr dos veces la misma partición deja la
     misma cantidad de filas
   - `tests/test_bronze_schema.py` — columnas esperadas presentes

5. `docs: add ADR-12 (medallion layering)`
   - `docs/ADRs/12-medallion-layering.md`

**Tests:** ver commit 4. **CI:** corre dentro del job existente.

---

## PR 3: `feature/silver-transformations`

**Branch:** `feature/silver-transformations` (anidada local sobre bronze/scaffolding)
**PR target:** `develop`
**Descripción:** Capa **silver**: limpieza, tipado, deduplicación y conformado de las
dos fuentes. Se define el tipo de carga.

**Commits:**

1. `feat: add silver staging models`
   - `models/silver/stg_produccion.sql` — tipado de fechas y volúmenes, normalización de
     nombres de pozo/empresa, filtrado de nulos inválidos
   - `models/silver/stg_pozos.sql` — limpieza del listado de pozos
   - `models/silver/_silver__models.yml` — descripción de columnas

2. `feat: configure incremental/merge materialization on production`
   - `stg_produccion.sql` como `materialized='incremental'` con `unique_key` y estrategia
     `merge` (upsert), particionable por período
   - macro o config para reprocesar una fecha (`--vars 'reprocess_period: ...'`)

3. `test: add silver dbt tests`
   - `not_null` y `unique` sobre claves; `relationships` entre producción y pozos

4. `docs: add ADR-13 (load type: full vs incremental vs merge)`
   - `docs/ADRs/13-load-type.md`

**Tests:** `dbt test` sobre silver. **CI:** job `dbt-test`.

---

## PR 4: `feature/gold-star-schema`

**Branch:** `feature/gold-star-schema` (anidada local sobre silver)
**PR target:** `develop`
**Descripción:** Capa **gold** con el modelo estrella: dimensiones, fact y documentación
del modelo de datos.

**Commits:**

1. `feat: add dimension models with surrogate keys`
   - `models/gold/dim_pozo.sql`, `dim_empresa.sql`, `dim_area.sql`, `dim_cuenca.sql`,
     `dim_tipo_recurso.sql`, `dim_fecha.sql`
   - surrogate keys con `dbt_utils.generate_surrogate_key`
   - `dim_pozo` y `dim_empresa` como **SCD Tipo 2** (columnas `valid_from`, `valid_to`,
     `is_current`); el resto Tipo 1

2. `feat: add fact table for monthly well production`
   - `models/gold/fct_produccion.sql` — grano: **un pozo × un mes**; medidas `prod_gas`,
     `prod_petroleo`, `prod_agua`, `dias_produccion`; FKs surrogate a todas las dims
   - materialización incremental con `merge` (hereda decisión del ADR-13)

3. `test: add grain and relationship tests on the star schema`
   - test de unicidad del grano (`unique` sobre `id_pozo + periodo`)
   - `relationships` de cada FK de la fact a su dim

4. `docs: add ADR-14 (dimensional model) and data model documentation`
   - `docs/ADRs/14-dimensional-model.md`
   - `docs/data-model.md` — grano de la fact, listado de dimensiones, surrogate keys y
     decisión de SCD por dimensión (con diagrama estrella)

**Tests:** ver commit 3. **CI:** job `dbt-test`.

---

## PR 5: `feature/data-quality`

**Branch:** `feature/data-quality` (anidada local sobre gold)
**PR target:** `develop`
**Descripción:** Checks de calidad persistidos con ≥3 dimensiones y consecuencia
operativa al fallar.

**Commits:**

1. `feat: add data quality tests across 3+ dimensions`
   - tests cubriendo como mínimo: **completitud** (`not_null`), **unicidad** (`unique`),
     **validez** (`accepted_values`, rangos con `dbt_expectations`), **schema**
     (`dbt_expectations.expect_column_to_exist` / contracts), y **freshness**
     (`dbt source freshness`)
   - `_gold__models.yml` con los tests por columna

2. `feat: persist quality results and expose a quality mark`
   - `dbt_project.yml`: `tests: store_failures: true` → cada test fallido persiste sus
     filas en un esquema `dbt_test_failures`
   - `models/gold/quality_marks.sql` — vista que resume el último estado de cada check
     (marca de calidad **visible** para BI y gobierno)

3. `feat: make a failed check block downstream promotion + alert`
   - en el job de Dagster, el step de `dbt build` (no `run`) hace que un test fallido
     corte la corrida → **bloquea la promoción a gold**
   - hook/sensor de Dagster que dispara una **alerta** (log de error + opcional webhook)
     cuando un check de severidad `error` falla

4. `test: verify failed checks are persisted and block the run`
   - test que inyecta un dato inválido y verifica que el run falla y que queda registro
     en `dbt_test_failures`

5. `docs: add ADR-15 (data quality approach)`
   - `docs/ADRs/15-data-quality.md`

**Tests:** ver commit 4. **CI:** job `dbt-test`.

---

## PR 6: `feature/orchestration-hardening`

**Branch:** `feature/orchestration-hardening` (anidada local sobre data-quality)
**PR target:** `develop`
**Descripción:** Endurece los DAGs: idempotencia, retries con backoff, observabilidad y
backfill verificable. Conecta extracción → dbt de punta a punta.

**Commits:**

1. `feat: wire end-to-end job (extraction -> dbt build)`
   - `data_platform/orchestration/jobs.py` — job que corre extracción a bronze y luego
     `dbt build` (silver + gold + tests)
   - `schedules.py` — schedule mensual

2. `feat: add retry policy with exponential backoff`
   - `RetryPolicy(max_retries=3, delay=..., backoff=Backoff.EXPONENTIAL)` en los assets
     de extracción y transformación

3. `feat: add time partitions to enable per-date backfill`
   - particiones mensuales en los assets; reprocesar una fecha = re-materializar su
     partición (idempotente por la escritura `merge`)

4. `docs: document the backfill / historical reprocessing procedure`
   - sección en `docs/runbooks/` (se completa el runbook del data engineer en PR 9, pero
     se deja acá el comando verificable de backfill)

**Tests:** test de que re-materializar una partición no duplica filas (idempotencia
end-to-end). **CI:** job existente.

---

## PR 7: `feature/governance-datahub`

**Branch:** `feature/governance-datahub` ← `develop`
**PR target:** `develop`
**Descripción:** Plataforma de gobierno con DataHub: workflows, tablas del DW, freshness
y lineage a nivel tabla.

**Commits:**

1. `feat: add datahub to docker-compose (quickstart)`
   - `docker-compose.datahub.yml` (compose separado por el peso de DataHub)
   - `.env.datahub.example`

2. `feat: add ingestion recipes`
   - `data_platform/governance/recipes/dbt.yml` — ingiere `manifest.json` + `catalog.json`
     de dbt (lineage de modelos + descripciones)
   - `data_platform/governance/recipes/postgres.yml` — ingiere tablas del warehouse
   - `data_platform/governance/recipes/dagster.yml` — ingiere los workflows/assets
   - resultado: lineage navegable a nivel tabla, freshness (última actualización) y los
     workflows de extracción visibles

3. `docs: add ADR-16 (data governance) and access instructions`
   - `docs/ADRs/16-data-governance.md`
   - sección de README con cómo levantar y acceder a DataHub

**Tests:** validación de que los recipes parsean (`datahub ingest -c ... --dry-run`).
**CI:** opcional (DataHub es pesado para CI; alcanza con dry-run del recipe).

---

## PR 8: `feature/bi-metabase`

**Branch:** `feature/bi-metabase` ← `develop`
**PR target:** `develop`
**Descripción:** Plataforma de BI con Metabase para usuarios no técnicos, conectada a la
capa gold.

**Commits:**

1. `feat: add metabase to docker-compose`
   - servicio `metabase` en `docker-compose.data.yml`, conectado al esquema `gold`

2. `feat: provision dashboards for non-technical users`
   - dashboards: producción de gas/petróleo por cuenca y por operadora a lo largo del
     tiempo, top pozos, evolución mensual, marca de calidad de los datos
   - export de la config para que sea reproducible

3. `docs: add ADR-18 (BI tool) and access instructions`
   - `docs/ADRs/18-bi-tool.md`
   - sección de README con cómo acceder al BI

**Tests:** smoke test de conexión de Metabase al warehouse. **CI:** opcional.

---

## PR 9: `feature/docs-runbooks`

**Branch:** `feature/docs-runbooks` ← `develop`
**PR target:** `develop`
**Descripción:** Documentación final: README completo, runbooks de los dos roles y bonus
de semantic layer.

**Commits:**

1. `docs: finalize README with data platform instructions`
   - cómo **actualizar los workflows**, cómo **acceder a BI y a gobierno**, y la
     **descripción de la arquitectura de datos** (requisitos no funcionales del README)

2. `docs: add data engineer runbook (backfill)`
   - `docs/runbooks/data-engineer.md`

3. `docs: add BI user runbook (freshness & quality before publishing)`
   - `docs/runbooks/bi-user.md`

4. `feat: add semantic layer (bonus)`
   - vistas lógicas o `dbt metrics` que definen métricas de negocio una sola vez
     (producción total, declino, etc.)

**Tests:** no aplica. **CI:** job existente.

---

# ADRs — Detalle completo

> Formato igual al de Fase 1. **Regla crítica de la consigna:** un ADR que no compare
> alternativas, o que solo describa el camino tomado, se considera **inválido**. Todos
> los ADRs de abajo comparan al menos dos opciones reales con sus trade-offs.

---

## ADR-11: Herramienta de orquestación

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto y declaración del problema

La Fase 2 requiere un orquestador con DAGs definidos como código, con idempotencia,
retries con backoff y observabilidad mínima (logs y status accesibles). Debe poder
reprocesar datos por fecha (backfill) e integrarse con dbt y con la plataforma de
gobierno (DataHub).

### Impulsores de la decisión

* DAGs/flows como código versionado.
* Idempotencia y backfill por fecha de primera clase.
* Retries con backoff exponencial.
* Observabilidad (UI con logs y status por corrida).
* Integración con dbt y con DataHub para lineage.

### Opciones consideradas

* **Apache Airflow** — el orquestador más maduro y difundido; modelo task-céntrico.
* **Dagster** — orquestador asset-céntrico (software-defined assets); lineage y
  particiones nativas.
* **Prefect** — orientado a flows en Python puro, muy liviano.

### Resultado de la decisión

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

### Consecuencias

* Bueno, porque particiones + assets dan idempotencia y backfill por fecha nativos.
* Bueno, porque el lineage de assets se ingiere directo en DataHub.
* Bueno, porque la UI provee logs y status por corrida (observabilidad mínima cubierta).
* Malo, porque la comunidad y el material de soporte son menores que los de Airflow.
* Malo, porque agrega un daemon adicional al stack (webserver + daemon).

### Confirmación

Confirmado en `data_platform/orchestration/`: assets particionados con `RetryPolicy`
(backoff exponencial) y un job end-to-end visible en la UI de Dagster.

---

## ADR-12: Capas de la arquitectura medallion

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto y declaración del problema

La consigna exige arquitectura medallion (bronze/silver/gold). Hay que decidir **cómo se
materializan físicamente** las tres capas dentro del warehouse y qué responsabilidad tiene
cada una.

### Impulsores de la decisión

* Separación clara de responsabilidades por capa.
* Trazabilidad: poder volver al dato crudo (bronze) ante cualquier discrepancia.
* Reprocesabilidad sin perder el origen.
* Simplicidad operativa para un equipo chico.

### Opciones consideradas

* **Tres esquemas Postgres** (`bronze`, `silver`, `gold`) en una misma base.
* **Tres bases de datos separadas**.
* **Convención de naming en un único esquema** (`raw_`, `stg_`, `mart_`).

### Resultado de la decisión

Opción elegida: **tres esquemas Postgres en una misma base**.

Tres bases separadas aíslan mejor pero complican las queries cross-capa (lineage, joins de
validación) y multiplican la administración de conexiones — innecesario para el volumen del
proyecto. La convención de naming en un solo esquema es la más simple pero mezcla crudo y
modelado en el mismo namespace, lo que dificulta permisos diferenciados y ensucia la
navegación en BI/gobierno. Tres esquemas dan separación lógica real (permisos por esquema,
navegación limpia) manteniendo todo en una sola base, que es lo que dbt mapea naturalmente
con su config de `schema` por carpeta de modelos.

Responsabilidades: **bronze** = landing crudo, sin transformar, particionado por carga
(append/merge por partición); **silver** = limpieza, tipado, deduplicación y conformado;
**gold** = modelo estrella listo para consumo.

### Consecuencias

* Bueno, porque da separación de responsabilidades y permisos por esquema.
* Bueno, porque dbt mapea carpetas → esquemas sin configuración extra.
* Bueno, porque bronze preserva el crudo para auditoría y reproceso.
* Malo, porque no hay aislamiento físico entre capas (comparten la misma base).

### Confirmación

Confirmado en `profiles.yml` y la config de `dbt_project.yml`: modelos en
`models/bronze|silver|gold` materializan en los esquemas homónimos.

---

## ADR-13: Tipo de carga (full vs incremental vs merge/upsert)

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto y declaración del problema

La consigna pide definir y justificar explícitamente el tipo de carga, y que sea posible
reprocesar los datos de una fecha si hay cambios. El dataset de producción de datos.gob.ar
se **revisa y corrige retroactivamente** (los volúmenes de meses pasados pueden cambiar en
publicaciones posteriores).

### Impulsores de la decisión

* El dato histórico puede cambiar entre publicaciones.
* Debe poder reprocesarse una fecha puntual sin recargar todo.
* El procesamiento debe ser idempotente.
* Costo/tiempo de procesamiento acotado.

### Opciones consideradas

* **Full load** — borrar y recargar todo en cada corrida.
* **Incremental append** — agregar solo filas nuevas.
* **Incremental merge / upsert** — insertar nuevas y actualizar las que cambiaron, por clave.

### Resultado de la decisión

Opción elegida: **incremental merge / upsert** sobre la fact y los staging de producción.

Full load es el más simple y trivialmente idempotente, pero recargar todo el histórico en
cada corrida no escala en tiempo a medida que crece la serie y desperdicia cómputo. Append
es barato pero **incorrecto** para este dataset: si un mes pasado se corrige, append
duplicaría el período en vez de actualizarlo. Merge/upsert con `unique_key` por
(pozo, período) actualiza el período corregido y agrega los nuevos, que es exactamente el
comportamiento que pide un dataset con correcciones retroactivas. Además es idempotente:
re-correr una partición converge al mismo estado.

### Consecuencias

* Bueno, porque refleja correctamente las correcciones retroactivas de la fuente.
* Bueno, porque permite reprocesar una fecha puntual (re-merge de esa partición).
* Bueno, porque es idempotente por construcción.
* Malo, porque el merge es más complejo que append y requiere una `unique_key` confiable.
* Malo, porque un cambio de esquema en la fuente exige revisar la lógica de merge.

### Confirmación

Confirmado en `stg_produccion.sql` y `fct_produccion.sql`:
`materialized='incremental'`, `incremental_strategy='merge'`, `unique_key` por
(pozo, período).

---

## ADR-14: Modelo dimensional (estrella)

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto y declaración del problema

La consigna exige que el warehouse use modelo estrella y que la documentación incluya
grano de la fact, dimensiones, surrogate keys y decisión de SCD. Hay que elegir el patrón
de modelado de la capa gold.

### Impulsores de la decisión

* Consultas analíticas simples para usuarios de BI no técnicos.
* Performance de agregaciones por dimensión (cuenca, operadora, tiempo).
* Manejo del cambio histórico en pozos y operadoras.
* Documentabilidad del modelo.

### Opciones consideradas

* **Estrella** — fact central + dimensiones desnormalizadas.
* **Copo de nieve (snowflake)** — dimensiones normalizadas en sub-dimensiones.
* **One Big Table (OBT)** — una tabla ancha desnormalizada.

### Resultado de la decisión

Opción elegida: **estrella** (la pide la consigna, pero se compara igual).

OBT es la más simple de consultar pero infla el almacenamiento, duplica atributos y vuelve
inmanejable el cambio histórico (un cambio de operadora reescribiría millones de filas).
Snowflake normaliza y ahorra algo de espacio, pero agrega joins que complican las queries
de BI para usuarios no técnicos — justo lo contrario de lo que se busca. La estrella es el
punto medio estándar: pocas joins, dimensiones legibles, y permite **SCD Tipo 2** limpio en
las dimensiones que cambian.

Modelo: **`fct_produccion`** con grano **un pozo × un mes** (medidas: gas, petróleo, agua,
días de producción); dimensiones `dim_pozo`, `dim_empresa`, `dim_area`, `dim_cuenca`,
`dim_tipo_recurso`, `dim_fecha`. Surrogate keys hash en todas las dims. **SCD Tipo 2** en
`dim_pozo` y `dim_empresa` (cambian de estado/operadora en el tiempo y el histórico
importa); **Tipo 1** en el resto.

### Consecuencias

* Bueno, porque minimiza joins para los usuarios de BI.
* Bueno, porque habilita SCD Tipo 2 ordenado donde el histórico importa.
* Bueno, porque el grano explícito previene doble conteo.
* Malo, porque desnormalizar duplica algunos atributos respecto a snowflake.
* Malo, porque SCD Tipo 2 agrega complejidad de carga (vigencias, claves surrogate).

### Confirmación

Confirmado en `models/gold/` y en `docs/data-model.md`: grano, dimensiones, surrogate keys
y decisión de SCD documentados.

---

## ADR-15: Enfoque de calidad de datos

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto y declaración del problema

La consigna exige checks de calidad con ≥3 dimensiones (ej. schema, linaje), **persistidos**
(no solo asserts en runtime), y que fallar un check tenga **consecuencia operativa**:
alerta, bloqueo de promoción aguas abajo o marca de calidad visible.

### Impulsores de la decisión

* Cobertura de varias dimensiones de calidad (completitud, unicidad, validez, schema, frescura).
* Persistencia de resultados, no solo pass/fail efímero.
* Consecuencia operativa al fallar.
* Integración con el resto del stack (dbt, orquestador).

### Opciones consideradas

* **dbt tests + dbt-expectations** con `store_failures`.
* **Great Expectations (GX)** — framework dedicado de validación con Data Docs.
* **Soda Core** — checks declarativos en YAML (SodaCL).

### Resultado de la decisión

Opción elegida: **dbt tests + dbt-expectations con `store_failures: true`**.

Great Expectations es el más potente en variedad de expectativas y genera Data Docs ricos,
pero es una herramienta separada con su propia curva y su propio orquestado — duplica
infraestructura sobre dbt, que ya está en el stack. Soda es liviano y declarativo pero
agrega otro servicio/CLI y otro lenguaje (SodaCL). dbt tests ya viven **dentro** de los
modelos: con `dbt-expectations` se cubren las dimensiones pedidas (schema, validez,
distribución) además de las nativas (not_null, unique, relationships, freshness), y con
`store_failures: true` los resultados se **persisten** en un esquema de fallas. La
consecuencia operativa sale natural: usar `dbt build` (no `run`) hace que un test fallido
**corte la corrida y bloquee la promoción a gold**, y una vista `quality_marks` expone la
**marca de calidad visible** en BI y gobierno; un sensor de Dagster agrega la **alerta**.

Tres dimensiones (mínimo exigido) quedan cubiertas y excedidas: completitud, unicidad,
validez, schema y frescura.

### Consecuencias

* Bueno, porque no agrega un framework/servicio extra al stack.
* Bueno, porque `store_failures` persiste las filas que fallan (auditable).
* Bueno, porque `dbt build` bloquea aguas abajo y `quality_marks` da marca visible.
* Malo, porque dbt-expectations es menos expresivo que GX para validaciones estadísticas complejas.
* Malo, porque la "alerta" requiere un sensor/hook propio (no viene out-of-the-box).

### Confirmación

Confirmado en `dbt_project.yml` (`store_failures: true`), `_gold__models.yml` (tests por
dimensión), `models/gold/quality_marks.sql` y el sensor de alerta en Dagster.

---

## ADR-16: Plataforma de gobierno de datos

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto y declaración del problema

La consigna exige una plataforma de gobierno que muestre los workflows de extracción, los
datos en el warehouse y la última actualización, y que permita **navegar el lineage a
nivel tabla**. Nombra DataHub como la herramienta vista en clase, admitiendo alternativas
si se justifican.

### Impulsores de la decisión

* Lineage navegable a nivel tabla.
* Visibilidad de workflows, tablas del DW y freshness.
* Ingesta de metadata desde dbt, el orquestador y Postgres.
* Herramienta vista en clase/tutoría (driver explícito de la consigna).

### Opciones consideradas

* **DataHub** — catálogo + lineage, vista en clase.
* **OpenMetadata** — catálogo open source con buena UX.
* **Amundsen** — catálogo de Lyft, foco en discovery.

### Resultado de la decisión

Opción elegida: **DataHub**.

OpenMetadata tiene muy buena experiencia de usuario y conectores propios, y Amundsen es
liviano y bueno para discovery, pero ninguno fue el material trabajado en la cursada —
elegirlos agregaría riesgo de soporte y contradice el driver explícito de "herramienta
vista en clase". DataHub cumple los tres requisitos concretos: ingiere el `manifest`/
`catalog` de dbt (lineage de modelos + descripciones), ingiere Postgres (tablas del DW) y
los assets de Dagster (workflows), y expone freshness y **lineage a nivel tabla** navegable.
La justificación de no explorar alternativa es deliberada: el costo de aprendizaje no se
compensa para el alcance del proyecto.

### Consecuencias

* Bueno, porque cumple lineage a nivel tabla + workflows + freshness en una sola UI.
* Bueno, porque tiene recipes de ingesta nativos para dbt, Postgres y Dagster.
* Bueno, porque es la herramienta vista en clase (menor riesgo de soporte).
* Malo, porque es **pesado**: requiere Kafka + Elasticsearch + store de metadata, por lo
  que corre en un compose separado y local (no en la `t3.micro`).
* Malo, porque la ingesta hay que programarla/correrla (no es push automático en tiempo real).

### Confirmación

Confirmado en `data_platform/governance/recipes/` (dbt, postgres, dagster) y en la UI de
DataHub mostrando el lineage bronze → silver → gold.

---

## ADR-17 (recomendado): Motor del warehouse

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto

Hay que elegir el motor donde viven las capas medallion y el modelo estrella, que además
sirve a Metabase (BI) y a DataHub (gobierno).

### Opciones consideradas

* **PostgreSQL** — relacional, multiusuario, conectores nativos en Metabase y DataHub.
* **DuckDB** — analítico embebido, rapidísimo en dev, archivo único.
* **BigQuery / Snowflake** — warehouses cloud gestionados.

### Resultado de la decisión

Opción elegida: **PostgreSQL**.

DuckDB es ideal para el loop de desarrollo de dbt, pero es **single-writer embebido**: no
encaja bien como warehouse servido a la vez a Metabase, DataHub y el orquestador. BigQuery/
Snowflake son excelentes pero implican cuenta cloud y costo, innecesarios para el alcance.
Postgres da concurrencia multiusuario, conectores nativos en todo el stack y corre en el
mismo Compose, soportando el modelo estrella sin problema al volumen del dataset.

### Consecuencias

* Bueno, porque es multiusuario y tiene conectores nativos en Metabase y DataHub.
* Bueno, porque corre local en Compose sin costo cloud.
* Malo, porque no es columnar: en volúmenes mucho mayores rendiría peor que un warehouse
  analítico dedicado (no es el caso a este volumen).

---

## ADR-18 (recomendado): Herramienta de BI

```
status: Aceptado
date: 2026-06-XX
decision-makers: Equipo de Desarrollo
```

### Contexto

Se necesita una plataforma de BI para que **usuarios no técnicos** exploren los datos de la
capa gold.

### Opciones consideradas

* **Metabase** — BI self-service orientado a no técnicos.
* **Apache Superset** — BI potente, más orientado a perfiles técnicos.
* **Looker Studio** — BI gestionado de Google.

### Resultado de la decisión

Opción elegida: **Metabase**.

Superset es más potente pero su curva (construcción de charts, SQL Lab) apunta a perfiles
técnicos — choca con el requisito de "usuarios no técnicos". Looker Studio es gestionado
pero implica sacar los datos del entorno local/controlado y atarse a Google. Metabase
permite explorar y armar dashboards con el "question builder" sin escribir SQL, conecta
nativo a Postgres y levanta en un contenedor.

### Consecuencias

* Bueno, porque los no técnicos arman consultas sin SQL.
* Bueno, porque conecta nativo a Postgres y corre en Compose.
* Malo, porque es menos flexible que Superset para visualizaciones avanzadas.

---

# Runbooks — Detalle

Se eligen **dos roles** (uno de implementación + uno de negocio), un archivo por rol en
`docs/runbooks/`. Cada runbook incluye: propósito y disparador, rol/dueño y prerrequisitos,
pasos numerados ejecutables, validación, qué hacer si falla (rollback/plan B/escalamiento),
consideraciones no funcionales, y **dos decisiones justificadas** (una funcional, una no
funcional) desde los incentivos del rol.

## `docs/runbooks/data-engineer.md` — Reprocesamiento histórico / backfill

* **Propósito y disparador:** reprocesar la producción de una fecha cuando datos.gob.ar
  publica correcciones de meses pasados (disparador: aviso de actualización de la fuente o
  detección de discrepancia en un check de calidad).
* **Dueño y prerrequisitos:** data engineer; accesos a Dagster, al repo y a Postgres;
  conocer el período a reprocesar.
* **Pasos:** identificar la partición → lanzar el backfill de esa partición en Dagster →
  `dbt build` corre silver+gold+tests sobre el período → verificar.
* **Validación:** la partición re-materializada deja la misma cantidad de filas que antes
  + las correcciones (idempotencia), todos los checks de calidad en verde, freshness
  actualizada en DataHub.
* **Si falla:** un check rojo bloquea la promoción a gold; rollback = la corrida fallida no
  promociona (gold queda en el último estado válido); escalar al data owner si la
  discrepancia es del dato fuente, no del pipeline.
* **No funcional:** idempotencia, frecuencia del reproceso, costo de cómputo.
* **Decisión funcional justificada:** por qué el reproceso usa `merge` por (pozo, período)
  — desde el incentivo del data engineer de no duplicar ni perder datos al corregir.
* **Decisión no funcional justificada:** umbral de frescura/SLA del pipeline — desde el
  incentivo de que aguas abajo (BI, gobierno) confíen en el dato.

## `docs/runbooks/bi-user.md` — Validar frescura y calidad antes de publicar

* **Propósito y disparador:** antes de presentar un reporte de producción, confirmar que
  los datos están frescos y pasaron calidad (disparador: pedido de reporte / reunión).
* **Dueño y prerrequisitos:** usuario de BI / data owner; acceso a Metabase y a DataHub.
* **Pasos:** abrir el dashboard → revisar la **marca de calidad** (`quality_marks`) → en
  DataHub verificar la **última actualización** del dataset → publicar/presentar.
* **Validación:** marca de calidad en verde y freshness dentro del umbral acordado.
* **Si falla:** si la marca está roja o el dato es viejo, no publicar; escalar al data
  engineer (pedir backfill) o al data owner.
* **No funcional:** frescura aceptable, calidad mínima, privacidad (no hay PII en el
  dataset público, dejarlo explícito).
* **Decisión funcional justificada:** qué métrica de negocio expone el dashboard (ej.
  producción total por cuenca) — desde el incentivo del usuario de negocio.
* **Decisión no funcional justificada:** qué umbral de frescura considera aceptable para
  decidir — desde el incentivo de no presentar datos desactualizados.

---

# Distribución de trabajo sugerida

| PR | Workstream | Autor sugerido | Reviewers |
|----|------------|----------------|-----------|
| 1 - scaffolding | Plataforma | Miembro A | B, C |
| 2 - extraction/bronze | Pipeline | Miembro B | A, C |
| 3 - silver | Pipeline | Miembro B | A, C |
| 4 - gold/estrella | Modelado | Miembro C | A, B |
| 5 - data quality | Calidad | Miembro A | B, C |
| 6 - orchestration hardening | Pipeline | Miembro B | A, C |
| 7 - governance (DataHub) | Gobierno | Miembro C | A, B |
| 8 - BI (Metabase) | BI | Miembro A | B, C |
| 9 - docs + runbooks | Docs | todos (1 runbook c/u) | cruzado |

Los ADRs se redactan en el PR donde se toma la decisión (no todos juntos al final), para
que la justificación quede atada a la implementación que la confirma.

---

# Checklist pre-entrega

- [ ] CI en verde en todos los PRs (job de la API + jobs `dbt-parse`/`dbt-test`)
- [ ] Extracción de las **2 fuentes** de datos.gob.ar funcionando → bronze
- [ ] Arquitectura **medallion** (esquemas bronze/silver/gold) operativa
- [ ] Orquestador (**Dagster**) con DAGs/assets como código
- [ ] DAGs con **idempotencia + retries con backoff + observabilidad** (logs/status)
- [ ] Procedimiento de **backfill** documentado y verificable
- [ ] **Tipo de carga** (merge/upsert) definido y justificado en ADR-13
- [ ] Warehouse con **modelo estrella** (dims + fact)
- [ ] **Documentación del modelo de datos**: grano, dimensiones, surrogate keys, SCD
- [ ] Checks de calidad con **≥3 dimensiones**, **persistidos** (`store_failures`) y con
      **consecuencia operativa** (bloqueo + marca visible + alerta)
- [ ] Procesamiento **idempotente** y **reprocesable por fecha** (verificado con test)
- [ ] Plataforma de **gobierno (DataHub)**: workflows, tablas del DW, freshness y
      **lineage a nivel tabla** navegable
- [ ] Plataforma de **BI (Metabase)** accesible para usuarios no técnicos
- [ ] **README** con: actualizar workflows, acceder a BI y gobierno, arquitectura de datos
- [ ] **6 ADRs obligatorios** (11–16) con comparación de alternativas
- [ ] **2 runbooks** (data engineer + BI user) en `docs/runbooks/`
- [ ] (Bonus) **semantic layer** implementado
- [ ] Video de demo

---

# Plan de Ejecución — Fase 2

> Esta sección es la guía operativa de implementación. La sección anterior es la adenda
> técnica (contratos de PR, ADRs, runbooks). Aquí vive el estado de avance, los comandos
> exactos y los criterios de done por PR.
>
> **Convención:** marcar `[x]` en cada ítem al completarlo. No avanzar al siguiente PR
> sin tener el anterior en verde (CI + criterios de done).

## Registro de decisiones de implementación

> Log de decisiones técnicas tomadas durante la implementación. Fuente de verdad para
> generar los ADRs semi-automáticamente. Formato: `[PR#] Decisión — Razón — Alternativa descartada`.

### PR 1 — data-platform-scaffolding (2026-06-04)

| # | Decisión | Razón | Alternativa descartada |
|---|----------|-------|------------------------|
| D1 | Puerto **5433** para Postgres warehouse | Evitar colisión con instancia Postgres local (5432 por defecto) | Puerto 5432 |
| D2 | Puerto **3001** para Dagster webserver | Puerto 3000 ya ocupado por Grafana | Puerto 3000 |
| D3 | **`Dockerfile.dagster` separado** del Dockerfile de la API | Dependencias data (dagster, dbt, psycopg2) pesadas e innecesarias en la imagen de la API | Multi-stage en Dockerfile principal |
| D4 | Grupo de dependencias uv **`[dependency-groups] data`** (separado de `dev`) | Mantiene la imagen Docker de la API lean; CI instala solo `--group data` para los jobs de dbt/dagster | Agregar al grupo `dev` o a `dependencies` principal |
| D5 | **`workspace.yaml` con `python_module`** (no file path) | Más robusto en Docker — no depende de paths absolutos del host | `workspace.yaml` con `python_file:` |
| D6 | **SQLite** como store de metadata de Dagster (default) | Sin infraestructura extra; Postgres del warehouse es para datos, no para metadata del orquestador | Postgres como Dagster metadata store |
| D7 | **`dbt parse`** como validación en CI (no `dbt compile`) | `dbt parse` no requiere conexión a DB — funciona en CI sin warehouse activo | `dbt compile` (requiere DB) |
| D8 | **`dagster definitions validate -m ...`** en CI | Valida que el módulo Python carga sin errores; no requiere DB ni UI | Levantar dagster-webserver completo en CI |
| D9 | **`profiles.yml` commiteado** con `env_var()` para credenciales | Sin secretos hardcodeados; funciona local y en Docker solo con variables de entorno | Profiles en `~/.dbt/` (no versionable) |
| D10 | `store_failures: false` en `dbt_project.yml` de PR1 | Se activa en PR5 (data-quality) cuando el schema de fallas está definido | Activar desde el inicio |
| D11 | **`packages.yml`** con `dbt_utils` + `dbt_expectations` desde PR1 | Los packages se necesitan en PR4 (surrogate keys) y PR5 (quality tests); instalarlos desde el scaffold evita olvidos | Agregar en PR4/PR5 |
| D12 | **`metaplane/dbt_expectations`** (no `calogica/dbt_expectations`) | `calogica` está deprecated; `metaplane` es el fork activo y mantenido | `calogica/dbt_expectations` (deprecated) |
| D13 | **`data_tests:`** en lugar de `tests:` en dbt_project.yml | Cambio de key en dbt 1.8+; `tests:` deprecated | `tests:` (deprecated en dbt>=1.8) |
| D14 | **`dbt deps` antes de `dbt parse`** en CI | `dbt parse` falla si packages declarados en packages.yml no están instalados | Omitir packages.yml en CI (no válido) |

---

## Estado de partida (develop, 2026-06-04)

| Componente | Estado |
|------------|--------|
| FastAPI + pytest + pre-commit | ✅ operativo |
| Docker Compose (api + prometheus + grafana) | ✅ puertos 8000/9090/3000 |
| CI (ci.yml) + CD (cd.yml → AWS ECR/EC2) | ✅ operativo |
| ADRs 01–10 en `docs/ADRs/` | ✅ presentes |
| `data_platform/` | ❌ no existe |
| Postgres warehouse | ❌ no existe |
| dbt project | ❌ no existe |
| Dagster | ❌ no existe |

## Mapa de dependencias

> Todos los PR apuntan a `develop`. La columna "anida sobre" indica de qué branch se crea
> localmente para tener su código; el merge es bottom-up (con merge commit) en ese orden.

```
develop  ◄── todos los PR apuntan aca
  │
  PR1: data-platform-scaffolding (+bronze)   anida sobre: develop      merge 1º
  PR3: silver-transformations                anida sobre: PR1          merge 2º
  PR4: gold-star-schema                      anida sobre: PR3          merge 3º
  PR5: data-quality                          anida sobre: PR4          merge 4º
  PR6: orchestration-hardening               anida sobre: PR5          merge 5º
  PR7: governance-datahub                    anida sobre: develop      tras gold (PR4)
  PR8: bi-metabase                           anida sobre: develop      tras gold (PR4)
  PR9: docs-runbooks                         anida sobre: develop      al final
```

**Regla de paralelismo:** PR7, PR8 y PR9 pueden desarrollarse en paralelo a la cadena
principal una vez que el modelo estrella (PR4) esté mergeado a develop. Antes de PR4,
no hay tablas gold que consumir. (PR2/bronze quedó integrado en PR1.)

---

## PR 1 — `feature/data-platform-scaffolding`

**Duración estimada:** 3–4 h  
**Dependencia:** develop limpio

### Comandos de inicio

```bash
git checkout develop && git pull
git checkout -b feature/data-platform-scaffolding
```

### Archivos a crear

```
docker-compose.data.yml
.env.data.example
data_platform/__init__.py
data_platform/extraction/__init__.py
data_platform/orchestration/__init__.py           # Definitions() vacío
data_platform/transform/dbt_project.yml
data_platform/transform/profiles.yml              # schemas: bronze, silver, gold
data_platform/transform/models/.gitkeep
data_platform/transform/models/bronze/.gitkeep
data_platform/transform/models/silver/.gitkeep
data_platform/transform/models/gold/.gitkeep
data_platform/transform/models/sources.yml        # placeholders
docs/ADRs/11-orchestration-tool.md
docs/ADRs/17-warehouse-engine.md
docs/ADRs/diagram-data-architecture.html
.github/workflows/ci.yml                          # extender: jobs dbt-parse + dagster-validate
```

### Dependencias a agregar en pyproject.toml

```toml
# En [project] dependencies:
"dbt-core>=1.8,<2.0"
"dbt-postgres>=1.8,<2.0"
"dbt-expectations>=0.10,<1.0"
"dagster>=1.8,<2.0"
"dagster-webserver>=1.8,<2.0"
"dagster-dbt>=0.24,<1.0"
```

### Criterios de done

- [ ] `docker compose -f docker-compose.data.yml up -d` levanta `warehouse` (Postgres) +
      `dagster-webserver` + `dagster-daemon` sin errores
- [ ] `uv run dbt parse --project-dir data_platform/transform` sale con código 0
- [ ] `uv run dagster definitions validate -m data_platform.orchestration` sale con código 0
- [ ] CI verde: job `dbt-parse` + `dagster-validate` pasan
- [ ] ADR-11 y ADR-17 presentes con comparación de alternativas
- [ ] PR abierto contra `develop`, revisado y mergeado

---

## PR 2 — `feature/data-extraction-bronze`

**Duración estimada:** 4–5 h  
**Dependencia:** PR1 mergeado

### Comandos de inicio

```bash
git checkout feature/data-platform-scaffolding && git pull
git checkout -b feature/data-extraction-bronze
```

### URLs de las fuentes (datos.gob.ar)

```
Producción pozos no conv.:
https://datos.gob.ar/dataset/energia-produccion-petroleo-gas-por-pozo-operadora-y-conc/archivo/energia_a9a3ec4a-4e2e-4236-903a-8ff5749f784c

Listado pozos por operadora:
https://datos.gob.ar/dataset/energia-produccion-petroleo-gas-por-pozo-operadora-y-conc/archivo/energia_7a2f16cb-abf3-482c-b044-7e91e1d6c2a5
```

### Archivos a crear

```
data_platform/extraction/produccion.py     # cliente HTTP + retry + timeout
data_platform/extraction/pozos.py          # ídem para listado
data_platform/orchestration/assets/
data_platform/orchestration/assets/__init__.py
data_platform/orchestration/assets/bronze.py  # assets particionados → bronze schema
data_platform/transform/models/sources.yml    # bronze.produccion_raw + bronze.pozos_raw
tests/test_extraction_idempotency.py
tests/test_bronze_schema.py
docs/ADRs/12-medallion-layering.md
```

### Patrón de escritura idempotente (bronze assets)

```python
# Estrategia: DELETE WHERE partition_key = X → INSERT
# O: INSERT ... ON CONFLICT (partition_key, pozo_id) DO UPDATE
```

### Criterios de done

- [ ] `uv run python -c "from data_platform.extraction.produccion import download; download()"` descarga CSV sin error
- [ ] Correr el asset de bronze dos veces sobre la misma partición → mismo row count
- [ ] `uv run pytest tests/test_extraction_idempotency.py tests/test_bronze_schema.py -v` verde
- [ ] `bronze.produccion_raw` y `bronze.pozos_raw` visibles en Postgres
- [ ] `uv run dbt source freshness --project-dir data_platform/transform` no falla (aunque no haya umbral aún)
- [ ] CI verde
- [ ] ADR-12 presente con comparación de alternativas

---

## PR 3 — `feature/silver-transformations`

**Duración estimada:** 3–4 h  
**Dependencia:** PR2 mergeado

### Comandos de inicio

```bash
git checkout feature/data-extraction-bronze && git pull
git checkout -b feature/silver-transformations
```

### Archivos a crear

```
data_platform/transform/models/silver/stg_produccion.sql
data_platform/transform/models/silver/stg_pozos.sql
data_platform/transform/models/silver/_silver__models.yml
docs/ADRs/13-load-type.md
```

### Config clave en stg_produccion.sql

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['id_pozo', 'periodo'],
    schema='silver'
) }}
```

### Criterios de done

- [ ] `uv run dbt run --select silver --project-dir data_platform/transform` sin errores
- [ ] `uv run dbt test --select silver --project-dir data_platform/transform` todos green
  (not_null, unique sobre claves; relationships entre produccion y pozos)
- [ ] Re-correr `dbt run --select silver` sobre misma partición → row count estable
- [ ] CI verde (job `dbt-test` corre silver)
- [ ] ADR-13 presente con comparación full/incremental/merge

---

## PR 4 — `feature/gold-star-schema`

**Duración estimada:** 5–6 h  
**Dependencia:** PR3 mergeado  
**Desbloquea:** PR7, PR8 (pueden iniciarse en paralelo tras merge de este PR)

### Comandos de inicio

```bash
git checkout feature/silver-transformations && git pull
git checkout -b feature/gold-star-schema
```

### Archivos a crear

```
data_platform/transform/models/gold/dim_pozo.sql
data_platform/transform/models/gold/dim_empresa.sql
data_platform/transform/models/gold/dim_area.sql
data_platform/transform/models/gold/dim_cuenca.sql
data_platform/transform/models/gold/dim_tipo_recurso.sql
data_platform/transform/models/gold/dim_fecha.sql
data_platform/transform/models/gold/fct_produccion.sql
data_platform/transform/models/gold/_gold__models.yml
docs/ADRs/14-dimensional-model.md
docs/data-model.md
```

### Surrogate keys

```sql
-- En cada dim:
{{ dbt_utils.generate_surrogate_key(['campo_natural_key']) }} as sk_pozo
```

### SCD Tipo 2 (dim_pozo, dim_empresa)

```sql
-- Columnas adicionales:
valid_from    DATE,
valid_to      DATE,   -- NULL = registro activo
is_current    BOOLEAN
```

### Criterios de done

- [ ] `uv run dbt run --select gold --project-dir data_platform/transform` sin errores
- [ ] `uv run dbt test --select gold --project-dir data_platform/transform` verde
  (unique sobre grain `id_pozo + periodo`; relationships de cada FK a su dim)
- [ ] `docs/data-model.md` tiene: grano, listado de dims, surrogate keys, decisión SCD
- [ ] CI verde
- [ ] ADR-14 presente con comparación estrella/snowflake/OBT

---

## PR 5 — `feature/data-quality`

**Duración estimada:** 4–5 h  
**Dependencia:** PR4 mergeado

### Comandos de inicio

```bash
git checkout feature/gold-star-schema && git pull
git checkout -b feature/data-quality
```

### Archivos a crear / modificar

```
data_platform/transform/models/gold/_gold__models.yml    # tests por columna y dimensión
data_platform/transform/models/gold/quality_marks.sql    # vista resumen de checks
data_platform/transform/dbt_project.yml                  # store_failures: true
data_platform/orchestration/sensors.py                   # sensor alerta en Dagster
tests/test_quality_persistence.py
docs/ADRs/15-data-quality.md
```

### Dimensiones de calidad mínimas a cubrir

| Dimensión | Implementación |
|-----------|---------------|
| Completitud | `not_null` en claves y medidas |
| Unicidad | `unique` sobre grain de la fact |
| Validez | `accepted_values` + `dbt_expectations.expect_column_values_to_be_between` |
| Schema | `dbt_expectations.expect_column_to_exist` o dbt contracts |
| Frescura | `dbt source freshness` con umbral definido |

### Config store_failures en dbt_project.yml

```yaml
tests:
  +store_failures: true
  +schema: dbt_test_failures
```

### Criterios de done

- [ ] `uv run dbt build --project-dir data_platform/transform` (no `run`) corre tests integrados
- [ ] Inyectar dato inválido → `dbt build` falla → fila persiste en `dbt_test_failures`
- [ ] `quality_marks` vista accesible en Postgres con estado de cada check
- [ ] Sensor de Dagster loggea error cuando check de severidad `error` falla
- [ ] `uv run pytest tests/test_quality_persistence.py -v` verde
- [ ] CI verde
- [ ] ADR-15 presente con comparación dbt-tests/GX/Soda

---

## PR 6 — `feature/orchestration-hardening`

**Duración estimada:** 3–4 h  
**Dependencia:** PR5 mergeado

### Comandos de inicio

```bash
git checkout feature/data-quality && git pull
git checkout -b feature/orchestration-hardening
```

### Archivos a crear

```
data_platform/orchestration/jobs.py        # job end-to-end: extraction → dbt build
data_platform/orchestration/schedules.py   # schedule mensual
```

### Modificar

```
data_platform/orchestration/assets/bronze.py   # agregar RetryPolicy + particiones mensuales
data_platform/orchestration/__init__.py         # exportar jobs, schedules, assets
docs/runbooks/data-engineer.md                  # sección backfill (comando verificable)
```

### Patrón RetryPolicy

```python
from dagster import RetryPolicy, Backoff

retry_policy = RetryPolicy(
    max_retries=3,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
)
```

### Criterios de done

- [ ] Job end-to-end visible y ejecutable en la UI de Dagster (`localhost:3001`)
- [ ] Schedule mensual registrado en Dagster
- [ ] Re-materializar partición ya cargada → row count idéntico (idempotencia end-to-end)
- [ ] `uv run pytest tests/test_extraction_idempotency.py -v` verde (test end-to-end)
- [ ] CI verde
- [ ] Sección de backfill en runbook con comando ejecutable documentado

---

## PR 7 — `feature/governance-datahub`

**Duración estimada:** 3–4 h  
**Dependencia:** PR4 mergeado (esquema gold disponible)  
**Puede correr en paralelo con:** PR8, PR9

### Comandos de inicio

```bash
git checkout develop && git pull
git checkout -b feature/governance-datahub
```

### Archivos a crear

```
docker-compose.datahub.yml
.env.datahub.example
data_platform/governance/__init__.py
data_platform/governance/recipes/dbt.yml       # ingiere manifest.json + catalog.json
data_platform/governance/recipes/postgres.yml  # ingiere tablas del warehouse
data_platform/governance/recipes/dagster.yml   # ingiere assets/workflows
docs/ADRs/16-data-governance.md
```

### Validación de recipes (sin levantar DataHub)

```bash
datahub ingest -c data_platform/governance/recipes/dbt.yml --dry-run
datahub ingest -c data_platform/governance/recipes/postgres.yml --dry-run
```

### Criterios de done

- [ ] `docker compose -f docker-compose.datahub.yml up -d` levanta DataHub (puede tardar ~3 min)
- [ ] UI de DataHub accesible en `localhost:9002`
- [ ] Dry-run de los tres recipes sin error
- [ ] Tras ingestión real: lineage bronze → silver → gold navegable en DataHub
- [ ] Freshness (última actualización) visible por tabla
- [ ] Workflows de Dagster visibles
- [ ] README actualizado con instrucciones de acceso a DataHub
- [ ] ADR-16 presente con comparación DataHub/OpenMetadata/Amundsen

---

## PR 8 — `feature/bi-metabase`

**Duración estimada:** 2–3 h  
**Dependencia:** PR4 mergeado (esquema gold disponible)  
**Puede correr en paralelo con:** PR7, PR9

### Comandos de inicio

```bash
git checkout develop && git pull
git checkout -b feature/bi-metabase
```

### Archivos a crear / modificar

```
docker-compose.data.yml    # agregar servicio metabase conectado a gold
docs/ADRs/18-bi-tool.md
```

### Dashboards a provisionar (exportar config para reproducibilidad)

```
grafana/metabase/                           # o carpeta equivalente de export
  produccion-por-cuenca.json
  produccion-por-operadora.json
  top-pozos.json
  evolucion-mensual.json
  quality-marks.json
```

### Criterios de done

- [ ] `docker compose -f docker-compose.data.yml up -d metabase` levanta Metabase
- [ ] UI accesible en `localhost:3030` (o el puerto elegido, distinto de 3000 Grafana)
- [ ] Conexión a esquema `gold` del warehouse verificada desde la UI
- [ ] Al menos 3 dashboards/questions operativos mostrando datos reales
- [ ] Dashboard de `quality_marks` visible
- [ ] Config de dashboards exportada y commiteada (reproducible)
- [ ] README actualizado con instrucciones de acceso a Metabase
- [ ] ADR-18 presente con comparación Metabase/Superset/Looker Studio

---

## PR 9 — `feature/docs-runbooks`

**Duración estimada:** 2–3 h  
**Dependencia:** PR6 + PR7 + PR8 mergeados (o avanzados — puede escribirse en paralelo)  
**Puede correr en paralelo con:** PR7, PR8

### Comandos de inicio

```bash
git checkout develop && git pull
git checkout -b feature/docs-runbooks
```

### Archivos a crear / completar

```
docs/runbooks/data-engineer.md    # procedimiento backfill completo
docs/runbooks/bi-user.md          # validar frescura + calidad antes de publicar
README.md                         # sección: actualizar workflows, acceder BI y gobierno,
                                  #          descripción arquitectura de datos
data_platform/transform/models/gold/semantic/   # (bonus) vistas/métricas dbt
```

### Estructura mínima de cada runbook

```markdown
## Propósito y disparador
## Rol / Dueño / Prerrequisitos
## Pasos (numerados, ejecutables)
## Validación
## Si falla (rollback / escalamiento)
## Consideraciones no funcionales
## Decisión funcional justificada
## Decisión no funcional justificada
```

### Criterios de done

- [ ] `docs/runbooks/data-engineer.md` completo con las 8 secciones
- [ ] `docs/runbooks/bi-user.md` completo con las 8 secciones
- [ ] README tiene las tres secciones requeridas (actualizar workflows, acceder BI/gobierno,
      arquitectura de datos)
- [ ] (Bonus) semantic layer: al menos 2 métricas de negocio definidas en dbt
- [ ] PR abierto y mergeado

---

## Tabla de seguimiento de PRs

> **Target de todos:** `develop`. La columna "anida sobre" es la branch local de la que se
> crea; el orden de merge es bottom-up. PR# es el número real en GitHub.

| Plan | PR# | Branch | Anida sobre | Estado |
|------|-----|--------|-------------|--------|
| 1 | #32 | `feature/data-platform-scaffolding` (+bronze) | develop | 🟡 en revisión |
| 3 | #28 | `feature/silver-transformations` | PR1 | 🟡 en revisión (✅ approved) |
| 4 | #30 | `feature/gold-star-schema` | PR3 | 🟡 en revisión |
| 5 | #31 | `feature/data-quality` | PR4 | 🟡 en revisión |
| 6 | — | `feature/orchestration-hardening` | PR5 | ⬜ pendiente |
| 7 | — | `feature/governance-datahub` | develop (post-PR4) | ⬜ pendiente |
| 8 | — | `feature/bi-metabase` | develop (post-PR4) | ⬜ pendiente |
| 9 | — | `feature/docs-runbooks` | develop (post-PR6/7/8) | ⬜ pendiente |

(PR2/bronze: integrado en PR1, ya revisado vía su PR #27.)

**Estados:** ⬜ pendiente · 🔵 en progreso · 🟡 en revisión · ✅ mergeado

---

## Convenciones de trabajo

### Antes de empezar cada PR

1. Pull de la branch base: `git pull`
2. Crear branch: `git checkout -b feature/<nombre>`
3. Verificar que CI está verde en la base

### Durante el PR

- Un commit por área de cambio (ver commits del plan técnico arriba)
- `uv run pre-commit run --all-files` antes de cada push
- Actualizar tabla de seguimiento marcando estado 🔵

### Antes de abrir el PR

1. `uv run pytest --cov=app --cov-report=term-missing` — cobertura de la API sin regresiones
2. `uv run dbt build --project-dir data_platform/transform` — pipeline dbt limpio
3. Todos los criterios de done del PR marcados `[x]`
4. Actualizar estado a 🟡 en la tabla

### Al mergear

- Actualizar estado a ✅ en la tabla
- Si desbloquea PR7/PR8: crear inmediatamente esas branches

---

## Puertos del stack completo

| Servicio | Puerto | Compose file |
|----------|--------|--------------|
| FastAPI | 8000 | docker-compose.yml |
| Prometheus | 9090 | docker-compose.yml |
| Grafana | 3000 | docker-compose.yml |
| Postgres warehouse | 5433 | docker-compose.data.yml |
| Dagster webserver | 3001 | docker-compose.data.yml |
| Metabase | 3030 | docker-compose.data.yml |
| DataHub GMS | 8080 | docker-compose.datahub.yml |
| DataHub frontend | 9002 | docker-compose.datahub.yml |

> Puerto 5433 (no 5432) para no colisionar con Postgres local si existe.
