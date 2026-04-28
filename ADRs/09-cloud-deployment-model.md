---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Despliegue en AWS con Terraform, EC2, ECR y SSM

## Contexto y Declaración del Problema

El proyecto necesita un despliegue reproducible en AWS para ejecutar la API y el stack de monitoreo. Se debe decidir si usar una plataforma administrada, una instancia simple o mantener solo ejecución local.

## Impulsores de la Decisión

* Mantener infraestructura versionada junto con el código.
* Evitar pasos manuales repetidos para crear recursos cloud.
* Mantener bajo el costo y la complejidad operativa.
* Poder desplegar desde GitHub Actions sin acceso SSH directo.
* Alineación con AWS y Terraform como herramientas vistas o incentivadas por la cátedra.

## Opciones Consideradas

* Ejecución local únicamente con Docker Compose.
* EC2 con Docker Compose, Terraform, ECR, SSM y Secrets Manager.
* Servicios administrados de contenedores (ECS/Fargate).
* Kubernetes administrado (EKS).

## Resultado de la Decisión

Opción elegida: "EC2 con Docker Compose, Terraform, ECR, SSM y Secrets Manager". Para el alcance actual permite desplegar el mismo stack que se usa localmente, mantener la infraestructura como código y automatizar el deploy desde GitHub Actions sin introducir una plataforma de orquestación más compleja. Además, AWS y Terraform estaban alineados con el enfoque recomendado en la materia.

### Consecuencias

* Bueno, porque Terraform documenta y crea los recursos principales de AWS.
* Bueno, porque ECR centraliza la imagen Docker de la API.
* Bueno, porque SSM permite ejecutar el deploy sin abrir SSH.
* Bueno, porque Secrets Manager evita commitear secretos reales.
* Malo, porque una sola EC2 no ofrece alta disponibilidad real.
* Malo, porque Docker Compose en una instancia requiere más operación manual que un servicio administrado.

### Confirmación

Confirmado en el repositorio: `infra/` define recursos Terraform para EC2, ECR, IAM y Secrets Manager; `.github/workflows/cd.yml` construye y sube la imagen a ECR y ejecuta el despliegue vía SSM; `docker-compose.prod.yml` levanta la API, Prometheus y Grafana en la instancia.
