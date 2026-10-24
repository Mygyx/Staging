> Historico Oracle. No representa una ejecucion PostgreSQL.

# Adaptación al contrato Chinook: 24 de octubre de 2026

Se conservó el historial inicial y se creó la carpeta/repositorio local
`chinook_staging_etl`. El esquema definitivo de esta entrega es
`CHINOOK_STAGING`, dentro de `XEPDB1`; el esquema inicial `INVACOM_STG` quedó
como antecedente. Los CSV originales permanecen intactos.

## Cambios acordados

- Once tablas fuente con los nombres exactos del equipo, incluidos
  `STG_INVOICE_LINE`, `STG_MEDIA_TYPE` y `STG_PLAYLIST_TRACK`.
- Auditoría en `ETL_SOURCE_FILE`, fuera del prefijo de tablas fuente `STG_`.
- Prefect muestra tareas distintas para **Extraer CSV**, **Cargar Staging** y
  **Validar Staging**. También prepara las tablas y guarda la evidencia.
- Las tareas de carga y validación comparten una conexión Oracle local, se
  ejecutan secuencialmente y confirman una sola transacción tras validar.
- Usuario `CHINOOK_STG_READ` con `CREATE SESSION` y `READ` sobre las 11 fuentes.
- Contrato JSON con conteos y consultas que conservan los encabezados CSV.
- Acceso LAN mediante la IP de la PC; sin cambios en el repositorio del DW.

## Evidencia actual

| Evidencia | Resultado |
| --- | --- |
| [Ejecución Prefect](../../../evidence/oracle/prefect-contract-completed.json) | Flujo y cinco tareas en `Completed` |
| [Comparación de datos](../../../evidence/oracle/run-94c3f2b3-fcb5-43b7-ab8d-aa724a58c835.json) | 15607 registros comparados campo por campo y confirmados |
| [Reversión entre tareas](../../../evidence/oracle/prefect-transaction-rollback.json) | Un fallo provocado en Validar Staging revierte la carga; las 12 tablas quedan vacías |
| [Pruebas](../../../evidence/oracle/tests-contract.txt) | 9 aprobadas, 1 omitida porque ya hay datos; rollback probado antes de cargar |
| [Validación SQL](../../../evidence/oracle/sql-contract-validated.txt) | Hashes por fila correctos en las 11 tablas |
| [Lector DW](../../../evidence/oracle/dw-reader-contract.json) | Once tablas, 15607 registros, ventas 2328.60, escritura rechazada con ORA-01031 |
| [Acceso LAN](../../../evidence/oracle/lan-access-status.json) | Firewall habilitado solo para la IP, interfaz, subred y puerto acordados |

El flujo fallido que aparece en el historial de Prefect corresponde a una prueba
deliberada de rollback, seguida de la carga real exitosa. No se alteró el CSV
para provocar el fallo.

La validación del lector usa la IP LAN desde el servidor. Todavía no se ha
ejecutado desde otra PC. La comparación de los totales usa `Decimal`: las 2240
líneas de factura y las 412 facturas suman **2328.60** en ambos casos. Esto
verifica controles de staging; el equipo del DW verificará su modelo y Excel.

El usuario creó la regla de Windows desde PowerShell como administrador después
de que el proceso del agente recibió acceso denegado. Se verificó posteriormente
que la regla está activa y que sus filtros corresponden a TCP/1521, interfaz
Wi-Fi, IP local `192.168.0.250` y subred origen `192.168.0.0/24`.

## Repositorio y siguientes pasos

El commit `33651bf` adapta nombres, esquema de instalación y tareas Prefect.
La entrega de acceso LAN, lector y evidencia se registra en un commit posterior.
El paquete `chinook_staging_etl.bundle` contiene el historial completo.

El usuario proporcionará después la URL del repositorio remoto. No se publicó
en otra cuenta ni se alteraron autores o fechas de los commits. El compañero
debe probar la conexión desde su PC y luego integrar las consultas del contrato
en `chinook_datawarehouse`.
