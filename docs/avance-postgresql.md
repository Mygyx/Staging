# Entrega PostgreSQL: 24 de octubre de 2026

Registro histórico de la migración. Los conteos de commits, las referencias Git
y los pendientes descritos corresponden a esa etapa; sus referencias de
recuperación se conservan localmente. Para el remoto y el historial agrupado
actuales, consultar [colaboración](colaboracion.md).

## Resultado y entorno real

Staging cargado en **PostgreSQL 17.4, puerto 5433**, base `chinook_staging`,
esquema `public`. Driver psycopg 3.3.6, Prefect 3.9.0 y Python 3.13.1.

La inspección autenticada encontró `DBBaseDatos`, `DBBaseDatosPrueba` y `postgres`.
No existía `chinook_staging` ni los dos roles del proyecto. Solo se agregaron
nuestra base y los roles `chinook_stg_loader` y `chinook_stg_reader`. Se
comprobaron nuevamente los nombres y propietarios de las bases previas.
No se modificaron otras bases, instalaciones Oracle, servicios, firewall,
credenciales antiguas, copias externas, bundles ni el repositorio del DW.

El usuario proporcionó la configuración administrativa, autorizó claves
aleatorias seguras para los roles nuevos y autorizó los esquemas de pruebas.
Las claves son independientes y están en .env y .env.reader, excluidos de Git.
El ETL se ejecuta como cargador no superusuario, sin CREATEDB ni CREATEROLE.

## Cambios realizados

Se reutilizaron el parser csv.reader, la fotografía en memoria, las firmas de
archivos y filas, las comprobaciones de encabezados y las comparaciones exactas.
Se reemplazaron driver, DDL, metadatos, parámetros, conexiones y privilegios.
Las columnas fuente son TEXT y conservan CamelCase; los vacíos son `''`.

Hay una sola ruta de carga: DELETE + INSERT en una transacción, advisory lock,
validación de todos los valores y catálogo, y COMMIT posterior. La tarea final
abre otra transacción de solo lectura y conserva evidencia. Los datos ya
confirmados no se revierten si falla esta fase de observabilidad.

La primera ejecución puede crear tablas; las recargas conservan sus objetos y
permisos. La base y el esquema no se borran ni se reinicializan para recargar.
El lector y el ejemplo SQLAlchemy usan REPEATABLE READ READ ONLY para obtener
una fotografía consistente de las once tablas.

## Conteos y fidelidad

| Tabla | Registros |
| --- | ---: |
| stg_album | 347 |
| stg_artist | 275 |
| stg_customer | 59 |
| stg_employee | 8 |
| stg_genre | 25 |
| stg_invoice | 412 |
| stg_invoice_line | 2240 |
| stg_media_type | 5 |
| stg_playlist | 18 |
| stg_playlist_track | 8715 |
| stg_track | 3503 |

15607 registros y 66439 campos fuente coinciden exactamente con los CSV.
Se conservaron 1339 cadenas vacías, 24 códigos postales con ceros iniciales y
8 campos con espacio final. Los once hashes coinciden con los originales de
la referencia Oracle. No se normalizó Unicode ni se convirtió ningún dato.
Controles con Decimal: 2240 líneas, total de líneas 2328.60 y facturas 2328.60.

## Pruebas ejecutadas

**34 aprobadas, 0 omitidas, 0 errores y 0 fallos.**

Se incluyen lectura estricta, hashes originales, caracteres especiales, DDL,
contrato, secretos/configuración, controles de aprovisionamiento y 15 casos
reales sobre PostgreSQL: primera carga, segunda carga, restauración de una
fotografía anterior tras fallo, fallo durante la inserción, corrupción detectada
antes del commit, vacíos distintos de NULL, tildes, espacios finales, ceros,
estructura incompatible, concurrencia, lectura repetible durante un refresco,
flujo Prefect real en esquema aislado, lector y rechazo real de escrituras.

Cada prueba destructiva creó y eliminó exclusivamente un esquema aleatorio
stg_test_* con una marca única. Se comparó la firma de public antes y después:
sin cambios. No quedaron esquemas de pruebas.

Dos cargas reales adicionales en public terminaron en Completed:

- `7f0158c3-5415-464e-9235-299ea0fe74ee`.
- `561a402d-2d10-4ae1-8a4f-66d2dd9323df`.

Ambas muestran Extraer CSV, Cargar Staging y Validar Staging en Completed y
conservan las mismas cantidades. Sus reportes se encuentran en
`evidence/postgresql`, junto con la aceptación y los resultados individuales
de unittest. Las evidencias Oracle anteriores se consultan desde el historial Git.

## Git y entrega

Los siete commits iniciales permanecen en `oracle-baseline-361bb17` y son
antecesores de la implementación. Se agregaron commits reales para backend,
pruebas/aprovisionamiento, documentación/archivo y evidencia de ejecución.

La carpeta activa es `chinook_staging_etl`. Tras la entrega, los archivos
específicos de Oracle se retiraron del árbol de trabajo, conservando su
recuperación en `pre-cleanup-b54ab4e`. La [limpieza posterior](limpieza-repositorio.md)
documenta esta decisión. Las credenciales antiguas de local se preservaron.

Brian y Miguel reciben `contracts/staging_sources.json` y `docs/entrega-dw.md`,
los datos de conexión PostgreSQL y la clave del lector por un canal privado.
Deben convertir TEXT y tratar `''` en sus transformaciones; no basta con un
cambio literal de read_csv a read_sql. No se modificó su proyecto.

La conexión desde sus PCs y la publicación remota quedan pendientes. No hay
bloqueos locales de autenticación, privilegios o pruebas al cerrar esta entrega.
