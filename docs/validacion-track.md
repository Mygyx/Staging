# Validación de calidad de datos de Track

## Objetivo

Incorporar controles adicionales de calidad sobre los registros de `Track.csv` antes de realizar la carga hacia PostgreSQL Staging.

## Validaciones implementadas

Se comprueban las siguientes reglas:

- `TrackId`: debe ser un identificador entero positivo y no repetido.
- `Milliseconds`: debe contener una duración entera positiva.
- `UnitPrice`: debe representar un valor numérico finito y no negativo.
- `Bytes`: cuando contiene información, debe representar un entero no negativo. Los valores vacíos se permiten.

Estas comprobaciones complementan las validaciones existentes de integridad, encabezados, hashes y relaciones.

## Automatización

El script `scripts/validate_tracks.py` puede ejecutarse de forma independiente y forma parte del workflow de GitHub Actions.

La función `validar_tracks_snapshot()` permite reutilizar la misma validación dentro de la tarea `Extraer CSV` de Prefect, utilizando los datos ya extraídos.

Cuando se detecta un error, la validación genera una excepción y el flujo no continúa hacia la tarea `Cargar Staging`.

## Pruebas

Los archivos `tests/test_validate_tracks.py` y `tests/test_prefect_track_validation.py` comprueban los casos válidos, los datos incorrectos y el bloqueo de la carga mediante simulaciones.

Comandos para reproducir las verificaciones:

```powershell
python scripts/validate_tracks.py
python -m unittest discover -s tests -v
```

## Alcance

Estas validaciones no modifican los archivos CSV originales ni realizan transformaciones sobre los valores almacenados. Tampoco necesitan credenciales de PostgreSQL para las pruebas locales.

La verificación de una ejecución completa del ETL contra PostgreSQL requiere acceso y autorización sobre el servidor Staging.
