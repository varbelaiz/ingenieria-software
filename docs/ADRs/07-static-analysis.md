---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Implementación de Pipeline de Análisis Estático (Pre-commit)

## Contexto y Declaración del Problema

El proyecto necesita reglas consistentes de formato, linting y chequeo de tipos para evitar diferencias entre entornos locales y CI.

## Impulsores de la Decisión

* Mantener un estilo homogéneo.
* Detectar errores simples antes del merge.
* Ejecutar las mismas validaciones localmente y en CI.

## Opciones Consideradas

* Confiar en revisiones manuales de código (Pull Requests).
* Configurar herramientas locales sin obligatoriedad.
* Usar `pre-commit` hooks (Black, Flake8, Pylint, Mypy) y ejecutarlos en CI.

## Resultado de la Decisión

Opción elegida: "Usar pre-commit hooks integrados con CI", porque centraliza las reglas de calidad y permite correrlas igual en local y en GitHub Actions.

### Consecuencias

* Bueno, porque Black asegura un estilo unificado sin debates.
* Bueno, porque Mypy y Pylint detectan errores simples antes de revisar manualmente.
* Malo, porque puede generar fricción inicial si las reglas fallan por detalles menores.

### Confirmación

Confirmado en el repositorio: `.pre-commit-config.yaml` configura Black, Flake8, Pylint y Mypy; el workflow de CI ejecuta `uv run pre-commit run --all-files`.
