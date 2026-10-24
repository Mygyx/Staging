# Limpieza del repositorio PostgreSQL

El proyecto activo implementa exclusivamente CSV -> Python/Prefect -> PostgreSQL
Staging. El 24 de octubre de 2026 se revisaron dependencias, rutas, documentación,
estado Git, fuentes y base antes de retirar archivos antiguos.

## Recuperación e historial

El punto previo es `b54ab4ec494e92ea9d64d25450dd8dacc2434885`, con once commits.
La referencia `pre-cleanup-b54ab4e` conserva ese estado completo versionado.
Se verificó la existencia de cada archivo retirado en ese commit y la integridad
de Git. Los autores y fechas anteriores permanecen intactos.

Para consultar un archivo histórico sin modificar el proyecto actual:

```powershell
git show pre-cleanup-b54ab4e:archive/oracle/sql/01_create_tables.sql
```

La migración conservó el parser estricto csv.reader, SHA-256, ordinales y
comparaciones campo por campo. PostgreSQL reemplazó conexiones, tipos, DDL y
permisos Oracle; ahora conserva cadenas vacías como `''` en columnas TEXT.
El Full Refresh PostgreSQL usa una sola transacción y valida antes del COMMIT.

## Archivos retirados

- `archive/oracle/`: 12 archivos de instalación, SQL, generador y pruebas antiguas.
- `evidence/oracle/`: 20 reportes que corresponden al motor anterior.
- `docs/historico/oracle/`: dos informes sustituidos por la documentación vigente.
- Archivos de trabajo de `local/clone-entrega/`: copia Oracle en el commit 361bb17,
  cuyo contenido ya está conservado en el historial principal.
- `local/run_prefect_contract.py` y `local/finalize_contract_checks.py`:
  auxiliares de comprobaciones Oracle, sin importaciones ni referencias activas.

La eliminación de los nueve archivos locales de caché `.pyc` fue rechazada por
la revisión automática de aprobación con el motivo «blocked by policy», tanto
por carpeta como por archivos concretos. Se conservaron excluidos de Git. No
se utiliza ese caché como implementación activa y las pruebas se ejecutan con
PYTHONDONTWRITEBYTECODE=1. También pueden quedar directorios vacíos locales;
Git no los publica como parte del repositorio.

Por la instrucción de conservar `.git`, la metadata de la copia anterior sigue
en `local/clone-entrega/.git`. Sus archivos de trabajo se retiraron; esa ubicación
no es el proyecto para ejecutar ni una segunda implementación activa.

## Archivos preservados

Los once CSV y sus hashes, manifiesto, contrato DW, cinco scripts Python actuales,
dos scripts SQL PostgreSQL, pruebas y evidencias PostgreSQL permanecen disponibles.
También se conserva requirements-lock.txt para reproducir las dependencias.

No se borraron `.git`, `.venv`, `.env`, `.env.admin`, `.env.reader` ni los XML
locales de credenciales. No se quitaron paquetes de .venv. El historial local
de Prefect en `local/prefect` continúa disponible. Estos recursos locales están
excluidos de Git. No se modificaron archivos externos, bases ajenas ni servicios.

La prueba `test_environment_is_supported_without_oracle_fallback` se mantiene:
comprueba que una variable antigua no se utilice como credencial alternativa.
Esa referencia es una protección de regresión; no importa ni necesita Oracle.

## Verificación y tamaños

Las comprobaciones posteriores se registran en `evidence/postgresql/cleanup-*`.
Incluyen fuentes, esquema y datos de public de solo lectura, lector, contrato,
pruebas unitarias, integración aislada y ejecución Prefect. Las pruebas utilizan
temporales dentro de local y verifican que public conserve su firma anterior.

La medición suma tamaños lógicos de archivos en bytes, separando archivos
versionados, `.git`, `.venv` y otros archivos locales. No mide las bases del
servidor PostgreSQL ni el espacio asignado por bloques del sistema de archivos.
Los metadatos Git y de Prefect pueden crecer al registrar la limpieza y pruebas.

El código y las dependencias activas solo requieren PostgreSQL. El historial
mantiene los antecedentes Oracle para recuperación y evidencia del avance real.

## Resultados posteriores comprobados

Las 34 pruebas volvieron a pasar: 19 locales y 15 de integración PostgreSQL,
sin omisiones. El flujo completo con sus tres tareas terminó en Completed
dentro de un esquema de pruebas. Tras la suite, la firma de las doce tablas de
public coincidió exactamente con la inicial y no quedaron esquemas de pruebas.
El contrato lector, los once hashes y la comparación de los 66439 campos de
15607 filas también pasaron. Los totales monetarios siguen siendo 2328.60.

El primer intento de capturar la salida de unittest mediante redirección
PowerShell se interrumpió por NativeCommandError. Se corrigió la captura usando
subprocess de Python, sin modificar las pruebas ni el proceso de carga, y se
ejecutó la suite completa. Los resultados individuales están en
[cleanup-tests.txt](../evidence/postgresql/cleanup-tests.txt).

El comando `run.ps1 -ValidateOnly` también terminó en Completed sobre public,
sin recargar tablas. Su reporte es
`run-2919cd6f-f499-4e16-adf3-c0b8ffe2de84.json` y su salida está en
[cleanup-prefect.txt](../evidence/postgresql/cleanup-prefect.txt).
