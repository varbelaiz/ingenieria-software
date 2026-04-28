---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Escaneo Estático de Vulnerabilidades en Contenedores (CI)

## Contexto y Declaración del Problema

Empaquetar la aplicación en imágenes Docker hace conveniente revisar vulnerabilidades conocidas en la imagen base y dependencias. Para esta etapa alcanza con tener visibilidad en CI antes de endurecer políticas de bloqueo.

## Impulsores de la Decisión

* Visibilidad temprana sobre CVEs en la imagen.
* Mantener el pipeline simple durante la fase inicial.
* Poder endurecer el pipeline más adelante si hace falta.

## Opciones Consideradas

* No realizar escaneo en CI.
* Docker Scout local.
* Trivy integrado en GitHub Actions en modo informativo.
* Trivy integrado en GitHub Actions fallando ante severidad alta o crítica.

## Resultado de la Decisión

Opción elegida: "Trivy integrado en GitHub Actions en modo informativo", porque automatiza la auditoría de seguridad sin bloquear el avance del proyecto por vulnerabilidades que pueden depender de la imagen base. El workflow actual usa severidades `CRITICAL,HIGH`, pero `exit-code: "0"`, por lo que reporta y no falla.

### Consecuencias

* Bueno, porque deja evidencia de vulnerabilidades conocidas en los logs de Actions.
* Bueno, porque permite convertir el escaneo en bloqueante cambiando solo la configuración del workflow.
* Malo, porque en su estado actual no impide que una imagen vulnerable avance.
* Malo, porque incrementa ligeramente el tiempo de ejecución del workflow de GitHub Actions.

### Confirmación

Confirmado en `.github/workflows/ci.yml`: el job `scan` construye la imagen Docker y ejecuta `aquasecurity/trivy-action`.
