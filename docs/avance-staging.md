# Incremento de staging: 24 de octubre de 2026

## Resultado verificado

Se cargaron **15.607 registros de 11 CSV** en `INVACOM_STG`, dentro de `XEPDB1`
de Oracle Database 21c XE. La herramienta de orquestación fue **Prefect 3.9.0**,
con Python 3.13 y python-oracledb 3.4.2. El flujo terminó en estado `Completed`.

Se conservaron los CSV originales y se comprobó que las copias de `data/raw`
coinciden byte por byte. Los datos fuente se almacenan como texto, sin limpieza,
conversiones de fechas ni conversiones de importes. Los campos vacíos se cargan
como `NULL`, según la representación de cadenas vacías de Oracle. Hay 11 tablas
fuente y una tabla técnica de manifiesto. `CSV_ROW_NUMBER` conserva el orden.

## Evidencia de ejecución

- [prefect-completed.json](../evidence/baseline-invacom-stg/prefect-completed.json): exportación de solo
  lectura de la base local de Prefect; el flujo y sus cuatro tareas finalizaron
  en `Completed`. Incluye identificador de ejecución y tiempos reales.
- [run-998c5d1b-06e7-49dd-923f-1b14c13ac88b.json](../evidence/baseline-invacom-stg/run-998c5d1b-06e7-49dd-923f-1b14c13ac88b.json):
  resultado de la carga, comparación de cada campo, conteos y hashes de fuentes.
- [source-copy-verification.json](../evidence/baseline-invacom-stg/source-copy-verification.json):
  comparación de los archivos originales de Downloads contra las copias y el
  manifiesto. No se modificaron las fuentes.
- [sql-oracle-final.txt](../evidence/baseline-invacom-stg/sql-oracle-final.txt): validación independiente
  ejecutada en Oracle con el SQL generado; los hashes de las 15.607 filas coinciden.
- [final-checks.json](../evidence/baseline-invacom-stg/final-checks.json): resumen de comprobaciones,
  todas con código de salida cero.

## Pruebas y límites

Las cinco pruebas de fidelidad comprueban todos los valores del SQL generado,
hashes del archivo, escapes, Unicode, vacíos y límites de campos. Las pruebas de
integración reales comprueban cuatro escenarios:

1. Otra conexión mantiene un bloqueo: la carga concurrente se rechaza con ORA-00054.
2. Se provoca un fallo de validación después de insertar todas las fuentes: el
   `ROLLBACK` deja las 12 tablas vacías. Esta prueba se ejecutó antes de la carga
   final; resultado en [preload-validation.json](../evidence/baseline-invacom-stg/preload-validation.json).
3. Una segunda carga sobre los datos confirmados se rechaza sin modificarlos.
4. Se elimina temporalmente una tilde de un campo: la comparación detecta el
   cambio; la transacción de prueba se revierte y la fuente vuelve a coincidir.

La ejecución final de unittest tuvo **8 pruebas aprobadas y 1 omitida** porque la
prueba que exige tablas vacías ya se había ejecutado antes de cargar los datos.
Véase [unittest-final.txt](../evidence/baseline-invacom-stg/unittest-final.txt).

El manifiesto y el SQL generado se comprobaron nuevamente sin regenerarlos. La
revisión de dependencias no encontró requisitos incompatibles. No se hicieron
transformaciones al DW, configuración de Excel ni creación del tablero Kanban.

## Incrementos Git

| Commit | Entregable |
| --- | --- |
| `6fcdfa8` | CSV originales y estructura inicial |
| `118b190` | Inventario, hashes y revisión de calidad |
| `af6136b` | DDL, carga y verificación SQL por fila |
| `7a97f19` | Flujo Prefect, carga con binds, instalación y entrega |
| Commit de esta evidencia | Pruebas de fidelidad e integración y resultados reales |

Los commits corresponden a trabajo realizado en esta fecha. El equipo debe
mantener los avances semanales reales, crear el repositorio remoto y el tablero,
y registrar los aportes de cada integrante durante los siguientes incrementos.
