# ADR-18: Herramienta de BI para usuarios no tecnicos

```
status: Aceptado
date: 2026-06-14
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La capa gold ya expone un modelo estrella consultable y una marca de calidad
(`gold.quality_marks`), pero falta una plataforma de BI que permita a usuarios no
tecnicos explorar esos datos y armar dashboards sin escribir SQL. La herramienta debe
conectar al warehouse Postgres, correr en el stack local de Docker Compose y dejar la
configuracion de los dashboards versionada y reproducible.

## Impulsores de la decision

* Acceso self-service para perfiles no tecnicos (requisito funcional de la fase).
* Conexion nativa al warehouse Postgres y al esquema gold.
* Despliegue en un contenedor dentro del Compose de datos existente.
* Dashboards reproducibles a partir de configuracion versionada.
* Mantener los datos en el entorno local/controlado, sin exfiltrarlos.

## Opciones consideradas

* **Metabase** - BI self-service orientado a no tecnicos, con question builder sin SQL.
* **Apache Superset** - BI potente y flexible, mas orientado a perfiles tecnicos.
* **Looker Studio** - BI gestionado de Google, sin infraestructura propia.

## Resultado de la decision

Opcion elegida: **Metabase**.

Superset es mas potente para visualizaciones avanzadas, pero su curva de uso
(construccion de charts, SQL Lab) apunta a perfiles tecnicos y choca con el requisito de
"usuarios no tecnicos". Looker Studio es gestionado y comodo, pero implica sacar los
datos del entorno local hacia un servicio de Google y atar la solucion a ese proveedor.
Metabase permite explorar y armar dashboards con el question builder sin escribir SQL,
conecta nativo a Postgres y levanta en un unico contenedor junto al resto del stack.

La configuracion no se deja como estado mutable dentro de Metabase: se define de forma
declarativa en `data_platform/bi/metabase_config.py` (conexion, preguntas y dashboard) y
se aplica de forma idempotente con `data_platform/bi/provision.py` contra la REST API.
Asi la configuracion queda versionada y reproducible sin depender de la serializacion de
la edicion Enterprise. El metadata interno de Metabase corre en un Postgres propio
(`metabase-db`), separado del warehouse.

## Consecuencias

**Pros**

* Los no tecnicos arman consultas y dashboards sin SQL.
* Conecta nativo a Postgres y corre en el Compose de datos.
* Los dashboards quedan versionados y se reaplican de forma idempotente.
* El estado interno de Metabase no se mezcla con los datos analiticos.

**Cons**

* Es menos flexible que Superset para visualizaciones avanzadas.
* La provision por API depende de la estabilidad de los endpoints REST.

## Confirmacion

Confirmado en `docker-compose.data.yml` (servicios `metabase` y `metabase-db`),
`data_platform/bi/` (config declarativa y script de provision) y en los tests
`tests/test_metabase_config.py` (estructura de las cards) y
`tests/test_metabase_cards_sql.py` (cada query valida contra el gold real).
