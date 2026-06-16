# ADR-15: Modelo dimensional para la capa gold

```
status: Aceptado
date: 2026-06-12
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La Fase 2 necesita publicar datos de produccion de pozos no convencionales en una
capa gold consumible por BI, gobierno y usuarios no tecnicos. Silver ya limpia,
tipa y deduplica las fuentes de produccion y pozos; gold debe definir un contrato
analitico estable, con grano explicito, claves surrogate y relaciones testeables.

## Impulsores de la decision

* Consultas simples para herramientas BI como Metabase.
* Grano auditable y testeable con dbt.
* Separacion clara entre medidas y atributos descriptivos.
* Lineage comprensible desde bronze/silver hasta modelos publicados.
* Capacidad de evolucionar dimensiones historizadas cuando haya historia suficiente.

## Opciones consideradas

* **Modelo analitico normalizado** - tablas cercanas a las entidades fuente, con mas
  joins y menos duplicacion.
* **Tabla ancha de reporting** - una sola tabla con medidas y atributos descriptivos
  desnormalizados.
* **Modelo estrella** - fact table con medidas y dimensiones conformadas alrededor.

## Resultado de la decision

Opcion elegida: **modelo estrella**.

El modelo normalizado conserva mejor la forma transaccional de las fuentes, pero obliga
a los usuarios de BI a entender demasiadas relaciones y aumenta el riesgo de joins
incorrectos. La tabla ancha seria la opcion mas simple para un dashboard inicial, pero
mezcla atributos y medidas, duplica texto descriptivo en cada fila y dificulta aplicar
calidad y gobierno por entidad. El modelo estrella balancea ambos extremos: expone una
fact table de produccion mensual y dimensiones pequenas, testeables y reutilizables.

La fact `gold.fct_produccion` tiene grano **un pozo por periodo mensual**. Las
dimensiones publicadas son `dim_pozo`, `dim_empresa`, `dim_area`, `dim_cuenca`,
`dim_tipo_recurso` y `dim_fecha`. Todas usan claves surrogate generadas con
`dbt_utils.generate_surrogate_key`.

`dim_pozo` y `dim_empresa` se publican con columnas compatibles con SCD Tipo 2:
`valid_from`, `valid_to` e `is_current`. En este PR representan el estado vigente de
silver; la historizacion completa queda preparada para una evolucion posterior cuando
se preserve suficiente historia de cambios de atributos.

## Consecuencias

* Bueno, porque Metabase puede consultar una fact central con joins previsibles.
* Bueno, porque dbt puede testear unicidad del grano y relaciones de cada FK.
* Bueno, porque DataHub podra mostrar lineage claro por tabla gold.
* Bueno, porque las dimensiones historizables ya tienen el contrato SCD-compatible.
* Malo, porque hay mas modelos que mantener que en una tabla ancha.
* Malo, porque la historizacion SCD completa requiere snapshots o historia de cambios
  adicional en un PR posterior.

## Confirmacion

Confirmado en `data_platform/transform/models/gold/`: dimensiones, fact y tests de
relaciones. Confirmado en `docs/data-model.md`: grano, dimensiones, medidas y diagrama
estrella documentados.
