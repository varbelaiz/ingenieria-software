---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Implementación de Seguridad vía Middleware

## Contexto y Declaración del Problema

El sistema necesita una autenticación simple mediante una API key (`X-API-Key`) configurada por variable de entorno. Si el token es inválido o no existe, la API debe retornar `403 Forbidden`. Se debe decidir dónde ubicar esta lógica.

## Impulsores de la Decisión

* Desacoplamiento de la lógica de negocio y la seguridad.
* Seguridad transversal a los endpoints de negocio.
* Mantener públicas las rutas técnicas necesarias para documentación, health check y scraping de métricas.

## Opciones Consideradas

* Implementación en Middleware global de FastAPI.
* Implementación como Dependencia (`Depends`) inyectada en cada endpoint.
* Delegación a un API Gateway externo.

## Resultado de la Decisión

Opción elegida: "Implementación en Middleware global de FastAPI", porque centraliza la validación en un solo punto y evita repetir lógica de autenticación en cada endpoint de negocio. El middleware mantiene excepciones explícitas para `/docs`, `/openapi.json`, `/metrics` y `/healthz`.

### Consecuencias

**Pros**

* Reduce el riesgo de olvidar autenticación al añadir nuevos endpoints de negocio.
* Rechaza el tráfico no autenticado más temprano en el ciclo de vida del request.

**Cons**

* Cualquier endpoint público futuro requiere agregar una excepción explícita al middleware.

### Confirmación

Confirmado por tests de middleware: requests sin `X-API-Key` o con un valor inválido devuelven `403 Forbidden`, mientras que `/healthz` y `/openapi.json` quedan disponibles sin API key.
