# Plataforma Predictiva de Producción de Hidrocarburos

Sistema para pronosticar la producción futura de hidrocarburos, reduciendo la incertidumbre en la planificación operativa mediante modelos predictivos y una API REST para consulta e integración.

## Requisitos

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) como package manager

## Setup local

1. Clonar el repositorio:

```bash
git clone <repo-url>
cd ingenieria-software
```

2. Instalar dependencias:

```bash
uv sync
```

3. Configurar variables de entorno:

```bash
cp .env.example .env
```

Editar `.env` con los valores correspondientes:

```
API_KEY=api_key
```

4. Ejecutar el servidor:

```bash
uv run uvicorn app.main:app --reload
```

## Estructura del proyecto

```
app/
├── __init__.py          # Paquete principal
├── main.py              # Punto de entrada de FastAPI y registro de routers
├── middleware.py         # Middleware global (validación de API key)
├── forecast/
│   ├── __init__.py      # Exporta el router de pronóstico
│   └── routes.py        # Endpoints de pronóstico de producción
└── wells/
    ├── __init__.py      # Exporta el router de pozos
    └── routes.py        # Endpoints de consulta de pozos
```

## Autenticación

Todos los endpoints requieren el header `X-API-Key` con una clave válida. La clave se configura mediante la variable de entorno `API_KEY`. Si la clave es inválida o no se proporciona, se retorna un error `403 Forbidden`.

## Endpoints

### `GET /api/v1/wells`

Retorna la lista de pozos disponibles para una fecha determinada.

**Parámetros de query:**

| Parámetro    | Tipo   | Requerido | Descripción                  |
|--------------|--------|-----------|------------------------------|
| `date_query` | `date` | Sí        | Fecha en formato `YYYY-MM-DD` |

**Ejemplo de respuesta:**

```json
{
  "date_query": "2026-03-23",
  "wells": ["POZO-001", "POZO-002", "POZO-003"]
}
```

### `GET /api/v1/forecast`

Retorna un pronóstico de producción (tendencia lineal decreciente) para un pozo en un rango de fechas.

**Parámetros de query:**

| Parámetro    | Tipo   | Requerido | Descripción                        |
|--------------|--------|-----------|------------------------------------|
| `id_well`    | `str`  | Sí        | Identificador del pozo             |
| `date_start` | `date` | Sí        | Fecha inicial en formato `YYYY-MM-DD` |
| `date_end`   | `date` | Sí        | Fecha final en formato `YYYY-MM-DD`   |

**Ejemplo de respuesta:**

```json
{
  "id_well": "POZO-001",
  "date_start": "2026-03-01",
  "date_end": "2026-03-03",
  "trend": "linear_decreasing",
  "data": [
    {"date": "2026-03-01", "oil_bopd": 1200.0},
    {"date": "2026-03-02", "oil_bopd": 1192.5},
    {"date": "2026-03-03", "oil_bopd": 1185.0}
  ]
}
```

**Errores posibles:**

| Código | Descripción                                    |
|--------|------------------------------------------------|
| `404`  | Pozo no encontrado                             |
| `400`  | `date_end` debe ser mayor o igual a `date_start` |
