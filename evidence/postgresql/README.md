# Evidencias PostgreSQL

Esta carpeta contiene las evidencias de PostgreSQL. Los reportes de la etapa
Oracle se consultan desde Git, en la referencia local `pre-cleanup-b54ab4e`,
disponible en la PC que conserva el respaldo del historial detallado.

Un reporte `run-<UUID>.json` con `mode=full-refresh` y `load_committed=true`
incluye la validación crítica anterior al COMMIT en `transactional_validation`,
y la verificación posterior en una conexión de solo lectura. Si la validación
crítica falla, hay ROLLBACK y no se genera un reporte exitoso de esa carga.

Un reporte con `mode=validate-only` tiene `load_committed=false` y
`transactional_validation=null`: comprueba una fotografía ya almacenada, sin
DELETE ni INSERT. No demuestra que se haya ejecutado una carga nueva. Este modo
es de solo lectura para PostgreSQL, pero genera evidencia y metadatos Prefect.

La verificación posterior al COMMIT no puede revertir datos ya confirmados.
Los reportes registran hashes, conteos, identificadores y resultados, sin claves.

Los resultados de unidades, integración, aprovisionamiento y verificaciones
finales deben especificar si se ejecutaron realmente. Un caso omitido o bloqueado
no se cuenta como aprobado. Las pruebas de corrupción deliberada solo se
ejecutan en los esquemas de pruebas expresamente autorizados, nunca en public.

## Resultado comprobado el 24 de octubre de 2026

- `acceptance.json`: criterios locales de aceptación, todos comprobados.
- `integration-tests.json` y `.txt`: 34 pruebas aprobadas, 0 omitidas; incluyen
  19 pruebas locales y 15 casos reales de integración PostgreSQL.
- `prefect-completed.json`: dos cargas reales en public, cada una con las tres
  tareas en Completed. No incluye el flujo de la prueba en esquema aislado.
- Dos reportes `full-refresh`: comparación antes del COMMIT y validación independiente.
- El reporte `run-2919cd6f-...json` corresponde a `validate-only` tras la limpieza.
- `reader-verification.json`: lector limitado, todos los campos y controles.
- `runtime-safety.json`: cargador no superusuario, pruebas limpiadas y sin
  verificación de red desde otra PC.
- `instance-before.json` y `provisioned-instance.json`: inspección autenticada
  antes de crear y comprobación posterior; las bases previas no fueron objetivo
  de ninguna escritura de la migración.
- `unit-tests.*`: ejecución local anterior a habilitar las pruebas PostgreSQL;
  sus omisiones se explican y no reemplazan el resultado integral posterior.

La conectividad desde las PCs del equipo DW y la evidencia semanal de los dos
responsables de Staging siguen pendientes. El remoto autorizado es
[Mygyx/Staging](https://github.com/Mygyx/Staging). La auditoría identificó una
regla administrativa trust que requiere revisión autorizada fuera del código.
Esta corrección no modifica credenciales, redes ni configuraciones del servidor.

## Comprobaciones posteriores a la limpieza

- `cleanup-audit.json`: inventario retirado, punto de recuperación, tamaños
  iniciales y archivos locales preservados.
- `cleanup-tests.json` y `.txt`: resultado de las pruebas posteriores, con
  temporales dentro del repositorio e integración en esquemas aislados.
- `cleanup-validation.json`: comparación de todos los datos, contrato lector,
  firma de public y preservación de credenciales.
- `cleanup-prefect.txt`: ejecución del lanzador en modo de solo validación.

La eliminación local de cachés fue rechazada por la revisión automática de
aprobación. Se conservan excluidos de Git y se documentan en la auditoría.
El primer intento de capturar unittest con redirección PowerShell se interrumpió
por NativeCommandError; se repitió con captura directa desde Python. Los
reportes cleanup-tests describen esta segunda ejecución completa.

## Correcciones finales posteriores a la auditoría

Los reportes anteriores conservan su fecha, formato y alcance; no se sobrescriben.

El reporte `run-52e4f3ea-07d8-4c9f-a9a4-6d889deb37f4.json` corresponde a otra
ejecución local real: `mode=full-refresh`, `load_committed=true`, con validación
transaccional y verificación posterior. No es una prueba de acceso desde la PC
del equipo DW ni de monitoreo compartido entre los dos repositorios.
La suite actual agrega casos y su ejecución se registra separadamente:

- `final-fixes-unit-tests.*`: casos locales; las integraciones omitidas se cuentan
  como omitidas y no como aprobadas.
- `final-fixes-integration-tests.*`: suite completa con PostgreSQL en esquemas
  aislados de la primera ampliación (44 casos) y temporal Prefect autorizado.
  Los estados Failed y SQLSTATE 23505 esperados pertenecen a una prueba negativa;
  el resumen final de unittest determina si la suite pasó.
- `final-fixes-complete-tests.*`: suite final de 45 casos, que agrega la prueba
  de UPDATE por columna dentro de un esquema aislado. Es el resultado final;
  las ejecuciones previas se conservan con sus conteos originales.
- `final-fixes-validation.json`: comprobación final de solo lectura de public,
  contrato, fuentes y preservación de los archivos protegidos.

El nuevo verificador reporta `source_tables_read_only`, el alcance de los
privilegios de tablas/columnas examinados y TEMP efectivo. Los reportes históricos conservan el
campo anterior, que no representa una auditoría de todo el servidor.

El [catálogo de pruebas](../../docs/pruebas-y-validaciones.md) distingue cada
tipo de fallo, las comprobaciones monetarias y las limitaciones de cobertura.
