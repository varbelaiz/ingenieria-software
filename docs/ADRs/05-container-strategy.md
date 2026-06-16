---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Desacoplamiento de Servicios en Múltiples Contenedores (Docker Compose)

## Contexto y Declaración del Problema

Al contenerizar la aplicación, surge la duda de si empaquetar la API y las herramientas de monitoreo (Grafana/Prometheus) en una sola imagen o utilizar contenedores separados.

## Impulsores de la Decisión

* Separación de responsabilidades.
* Aislamiento básico entre API y monitoreo.
* Principio de responsabilidad única por contenedor.
* Alineación con Docker como herramienta incentivada por la cátedra para empaquetar servicios.

## Opciones Consideradas

* Imagen Docker única ejecutando múltiples procesos (ej. via Supervisord).
* Múltiples contenedores orquestados con Docker Compose.

## Resultado de la Decisión

Opción elegida: "Múltiples contenedores orquestados con Docker Compose". La API, Prometheus y Grafana corren como servicios separados y se comunican por la red interna de Docker Compose. Esta decisión también mantiene el proyecto dentro del enfoque de contenedores trabajado en la materia.

### Consecuencias

**Pros**

* Cada servicio se puede configurar y reiniciar por separado.
* El fallo de Grafana no interrumpe la disponibilidad de la API para los clientes.

**Cons**

* Orquestar múltiples contenedores hace el despliegue local marginalmente más complejo que correr un solo script.

### Confirmación

Se confirma levantando `docker compose up --build` y observando los servicios en los puertos esperados: API `8000`, Prometheus `9090` y Grafana `3000`.
