# Decisiones de staging

1. Una tabla `STG_*` por CSV, con las columnas fuente en el mismo orden y una
   columna técnica `CSV_ROW_NUMBER`. Esta última numera registros lógicos desde 1,
   después del encabezado; no es una línea física cuando hay saltos dentro de comillas.
2. Todos los campos fuente son `VARCHAR2(n BYTE)`, dimensionados a partir del
   máximo real de bytes UTF-8 observado. No se usa `NUMBER`, `DATE`, `TRIM`,
   deduplicación, relleno de vacíos ni normalización de texto. Ante archivos nuevos
   se deben revisar manifiesto y DDL; este incremento carga la fotografía entregada.
3. Solo la posición técnica tiene PK. No hay PK ni FK sobre datos fuente:
   podrían impedir conservar duplicados o inconsistencias que pertenecen al CSV.
4. Un campo vacío del CSV se representa como `NULL`. No se reemplaza por cero,
   espacio, texto `NULL` ni un valor inventado. Oracle no distingue `''` de `NULL`
   en VARCHAR2. El archivo original, incluido su formato, sigue en `data/raw`.
   Las comillas delimitadoras, BOM y terminadores pertenecen al archivo CSV, no al
   contenido del campo. La copia byte por byte y su SHA-256 permiten auditarlos.
5. Los scripts son ASCII; los caracteres Unicode se expresan con `UNISTR`.
   Se exige `AL32UTF8` en la base para evitar pérdidas al convertir a VARCHAR2.
   `SET DEFINE OFF` conserva los ampersands sin pedir valores al usuario.
6. `STG_SOURCE_FILE` registra el hash del CSV, su tamaño, cantidad de campos y
   registros. Los hashes del contenido se recalculan leyendo las columnas reales
   de Oracle: no se da por válido un hash almacenado junto con una fila.
7. La serialización para SHA-256 concatena cada campo como
   `longitud_en_bytes_UTF8:valor`. El vacío se serializa como `0:`. Se compara
   cada fila por `CSV_ROW_NUMBER`, además de revisar los conteos. Se detectan
   cambios de espacios, acentos, ceros, orden, contenido y registros faltantes.
8. La carga confirma una sola transacción después de validar. Ante un error SQL
   se revierte el DML completo. Oracle confirma DDL de manera implícita: podrían
   quedar tablas vacías si la instalación falla después de crearlas. No se borran
   objetos ni se reemplazan tablas preexistentes automáticamente. Para corregir
   una carga fallida después del DDL, ejecutar `02_load_data.sql` y
   `03_validate_data.sql` en la misma sesión dedicada y luego `COMMIT`, una vez
   corregida la causa. Se requiere que todas las tablas estén vacías.
9. Prefect es la herramienta elegida por el equipo. El flujo Python define tareas
   para verificar fuentes, preparar tablas, cargar y validar dentro de una sola
   transacción Oracle y guardar evidencia. Las tareas no usan caché ni reintentos
   automáticos. La carga usa python-oracledb con binds y bloqueos exclusivos
   `NOWAIT` en orden fijo para impedir que dos cargas avancen simultáneamente.
   Una nueva carga sobre tablas pobladas falla; `--validate-only` permite auditar.
10. Los scripts SQL son artefactos reproducibles de revisión y una ruta manual
   alternativa en otro esquema. La ejecución principal del proyecto es Prefect.
   La comparación Python consulta y compara cada valor, además del hash por fila;
   permite una revisión independiente de los escapes utilizados en los SQL.
11. El staging es la entrega para que el compañero implemente las transformaciones
   y el DW. La limpieza posterior se documenta y se aplica fuera de estas tablas.

Fuentes técnicas oficiales:

- Oracle. [Nulls](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/Nulls.html).
- Oracle. [UNISTR](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/UNISTR.html).
- Oracle. [STANDARD_HASH](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/STANDARD_HASH.html).
- Oracle. [Using substitution variables](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqpug/using-substitution-variables-sqlplus.html).
