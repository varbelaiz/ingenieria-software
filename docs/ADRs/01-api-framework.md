---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Uso de Python y FastAPI para el Mock del Servidor API

## Contexto y Declaración del Problema

La Fase 1 requiere la implementación de una API REST mock que exponga los endpoints `/api/v1/forecast` y `/api/v1/wells`. También se necesita documentación OpenAPI para facilitar pruebas e integración.

## Impulsores de la Decisión (Decision Drivers)

* Necesidad de autogenerar documentación OpenAPI.
* Validación simple de parámetros y respuestas.
* Velocidad de desarrollo para la construcción del mock inicial.
* Alineación con herramientas vistas o incentivadas por la cátedra.

## Opciones Consideradas

* FastAPI (Python)
* Flask o Django (Python)
* Express.js (Node.js)

## Resultado de la Decisión

Opción elegida: "FastAPI", porque ofrece validación de esquemas con Pydantic y genera automáticamente la documentación OpenAPI interactiva (`/docs`). Además, era una herramienta alineada con lo trabajado en la materia. Para el alcance actual del proyecto permite construir el mock con poco código adicional.

### Consecuencias

* Bueno, porque reduce el trabajo manual de documentación de endpoints.
* Bueno, porque la validación de parámetros queda integrada al framework.
* Malo, porque suma dependencia al ecosistema FastAPI/Pydantic.

### Confirmación

Confirmado en la implementación actual: `/docs` y `/openapi.json` están expuestos, y la suite de tests valida los casos principales de `/api/v1/wells` y `/api/v1/forecast`.
