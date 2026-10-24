# Evidencias PostgreSQL

Solo esta carpeta representa la migración nueva. Los reportes Oracle permanecen
en `../oracle/` y no demuestran que PostgreSQL funcione.

Cada `run-<UUID>.json` generado por Prefect incluye la validación crítica que
precedió al COMMIT y una segunda comparación en una transacción de solo lectura.
No contiene contraseñas ni valores personales completos: registra hashes,
conteos, controles, identificador y resultados.

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
- Dos `run-<UUID>.json`: comparación antes del COMMIT y validación independiente.
- `reader-verification.json`: lector limitado, todos los campos y controles.
- `runtime-safety.json`: cargador no superusuario, pruebas limpiadas y sin
  verificación de red desde otra PC.
- `instance-before.json` y `provisioned-instance.json`: inspección autenticada
  antes de crear y comprobación posterior; las bases previas no fueron objetivo
  de ninguna escritura de la migración.
- `unit-tests.*`: ejecución local anterior a habilitar las pruebas PostgreSQL;
  sus omisiones se explican y no reemplazan el resultado integral posterior.

Siguen pendientes únicamente la prueba desde las computadoras del equipo DW y
la publicación en el remoto que el usuario proporcione. No se presentan como
realizadas ni se abrió el acceso de red automáticamente.
