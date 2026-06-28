# ADR-20: Tracking de experimentos de machine learning

```
status: Aceptado
date: 2026-06-26
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La Fase 3 requiere que los ML Engineers puedan acceder a una plataforma de tracking de
experimentos. El entrenamiento debe ser reproducible y comparable entre runs, dejando
evidencia de parametros, metricas, artefactos, ventana de datos y version de features.
La entrega no exige un servicio live en produccion, pero si una demostracion local clara
de multiples entrenamientos y sus metricas.

## Impulsores de la decision

* Registrar metricas comparables entre runs, como MAE, RMSE y cantidad de filas.
* Registrar parametros y tags de reproducibilidad: `as_of_date`, ventana temporal,
  feature view y commit.
* Guardar artefactos de modelo para que puedan registrarse/promoverse despues.
* Correr localmente sin depender de servicios SaaS externos.
* Integrarse con un model registry sin construir una plataforma propia.

## Opciones consideradas

* **MLflow Tracking** - plataforma open source para registrar experimentos, metricas,
  parametros, tags y artefactos. Puede correr localmente en Docker Compose y se integra
  con MLflow Model Registry.
* **Weights & Biases** - tracking y visualizacion muy completos, con excelente UI para
  colaboracion, pero normalmente depende de un servicio externo y de una cuenta SaaS.
* **Neptune** - alternativa gestionada fuerte para equipos ML, tambien con dependencia
  externa y mayor superficie operativa para esta entrega.
* **CSV/JSON propio** - simple de implementar, pero no cumple bien la necesidad de
  comparar runs, navegar metricas ni conectar tracking con registry.

## Resultado de la decision

Opcion propuesta: **MLflow Tracking**.

MLflow cubre el requisito de plataforma de tracking sin sumar una dependencia SaaS. Su
modelo de runs permite registrar parametros, metricas, tags y artefactos de manera
reproducible, y su UI local es suficiente para la demostracion del video. Ademas, deja el
camino abierto para usar MLflow Model Registry en ADR-22 sin inventar metadatos propios.

Weights & Biases y Neptune ofrecen mejor experiencia gestionada y colaborativa, pero
agregan cuentas externas, configuracion de tokens y dependencia de red que no aporta
valor suficiente para una entrega local. CSV/JSON propio seria barato al inicio, pero
terminaria recreando mal una parte de MLflow y haria mas debil la evidencia del video.

## Consecuencias

**Pros**

* Los ML Engineers pueden comparar runs desde una UI local.
* Los artefactos quedan relacionados con metricas y parametros.
* Se reduce el trabajo necesario para conectar training con model registry.
* La demo puede mostrar multiples runs reales sin produccion live.

**Cons**

* Agrega un servicio local adicional y volumen de artefactos.
* Requiere acordar convenciones de experimentos, tags y nombres de modelo.
* En un entorno productivo real habria que endurecer almacenamiento, permisos y backups.

## Confirmacion esperada

Confirmar en PR 3 con servicio MLflow local, helpers en `ml/training/tracking.py`, al
menos un smoke test de registro de runs y un entrenamiento real registrando metricas.

## Confirmacion PR 3

PR 3 confirma la decision con:

* grupo de dependencias `ml` con `mlflow`;
* `docker-compose.ml.yml` con servicio local `mlflow` y volumen persistente para backend
  SQLite y artefactos;
* `.env.ml.example` con las variables compartidas `MLFLOW_TRACKING_URI`,
  `MLFLOW_EXPERIMENT_NAME` y `MLFLOW_MODEL_NAME`;
* helper `ml/training/tracking.py` para configurar tracking URI, experimento y tags
  estandar de reproducibilidad;
* smoke command `python -m ml.training.smoke_tracking` para registrar un run dummy con
  parametros y metricas;
* tests que validan el contrato sin requerir servidor MLflow vivo, incluyendo un store
  local temporal basado en archivos.

El entrenamiento real queda para PR 5; este PR solo deja la plataforma y el harness de
tracking listos para ser consumidos por training y registry.

