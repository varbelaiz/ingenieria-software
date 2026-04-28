---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Adopción de uv como Gestor de Paquetes y Entornos

## Contexto y Declaración del Problema

Para asegurar la reproducibilidad de los entornos locales y de CI/CD, necesitamos una herramienta que mantenga un lockfile de dependencias Python y simplifique la creación del entorno virtual.

## Impulsores de la Decisión

* Tiempos de instalación en contenedores y pipelines de CI.
* Determinismo en las dependencias (evitar el "funciona en mi máquina").

## Opciones Consideradas

* uv
* Poetry
* pip + pip-tools

## Resultado de la Decisión

Opción elegida: "uv", porque resuelve e instala dependencias rápido, genera `uv.lock` y permite usar el mismo flujo en local, Docker y GitHub Actions.

### Consecuencias

* Bueno, porque reduce el tiempo de instalación de dependencias frente al flujo tradicional con `pip`.
* Bueno, porque estandariza el manejo de entornos virtuales sin herramientas extra.
* Malo, porque es una tecnología relativamente nueva y parte del equipo podría no estar familiarizado.

### Confirmación

Confirmado en el repositorio: existen `pyproject.toml` y `uv.lock`; Dockerfile, README y workflows de CI usan `uv sync` / `uv run`.
