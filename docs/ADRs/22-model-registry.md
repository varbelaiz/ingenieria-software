# ADR-22: Registro y promocion de modelos

```
status: Aceptado
date: 2026-06-25
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La API de predicciones necesita resolver que modelo esta vigente y exponer metadata de la
version servida. El equipo tambien necesita trazar cada modelo hasta el run de
entrenamiento, las metricas de validacion, los parametros y el artefacto generado. Sin un
registry, la promocion de modelos quedaria como un proceso manual y dificil de auditar.

## Impulsores de la decision

* Versionar modelos entrenados.
* Relacionar modelo, run, metricas y artefacto.
* Distinguir modelos promovidos, candidatos y rechazados.
* Permitir que la API consulte el modelo vigente sin hardcodear paths.
* Evitar construir un registry propio con semantica incompleta.

## Opciones consideradas

* **MLflow Model Registry** - registro integrado con MLflow Tracking, versiones de modelo,
  metadata y resolucion de modelos por nombre/version.
* **Artefactos versionados + JSON** - guardar modelos en carpetas y metadata en archivos,
  con baja complejidad inicial pero poca seguridad operativa.
* **Tabla propia en Postgres** - metadata controlada por el equipo, pero implica disenar
  reglas de versionado, promocion y resolucion de artefactos.

## Resultado de la decision

Opcion propuesta: **MLflow Model Registry**.

Como ADR-20 propone MLflow Tracking, usar MLflow Model Registry evita duplicar metadata y
mantiene la trazabilidad run-modelo en una misma plataforma. La API podra resolver el
modelo vigente por nombre y version/stage, mientras que el pipeline de entrenamiento
podra registrar y promover candidatos segun metricas. Artefactos + JSON es demasiado
fragil para auditar promocion, y una tabla propia en Postgres recrearia funcionalidades
que MLflow ya provee.

## Consecuencias

**Pros**

* Trazabilidad directa entre run, metricas y modelo servido.
* Menos codigo propio para versionado y promocion.
* La demo puede mostrar el modelo registrado/promovido junto a los runs.
* Facilita el endpoint `GET /models/current`.

**Cons**

* Acopla training e inferencia a convenciones de MLflow.
* La API necesita manejar claramente el caso "no hay modelo promovido".
* En produccion real habria que definir permisos y almacenamiento robusto para artefactos.

## Confirmacion esperada

Confirmado en PR 6 con:

* `ml/registry/client.py` para registrar artefactos trazables desde un run, resolver
  aliases y descargar el modelo vigente.
* aliases `candidate` y `champion`, en lugar de stages de MLflow.
* politica de promocion por MAE: el candidato debe tener la metrica, respetar el umbral
  y mejorar al champion actual.
* CLI `python -m ml.registry.promote --run-id <RUN_ID> --max-mae <VALOR>`.
* inferencia por API usando features point-in-time y el modelo `champion`, con respuesta
  `503` explicita cuando no existe uno promovido.
