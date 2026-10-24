# Chinook Staging ETL

Repo 1 de Jeremy y compañero, UTN: **11 CSV -> Python/Prefect 3 -> PostgreSQL**.
La base de staging es `chinook_staging`, esquema `public`, en un entorno distinto
del PostgreSQL DW de Brian y Miguel. Este repositorio no transforma dimensiones.

Hay 11 tablas `stg_*` con **15.607 filas y 66.439 campos originales**. Todos los
campos fuente son `TEXT`, conservan CamelCase y sus valores exactos. Los 1.339
vacíos son `''`, no NULL. Se mantienen ceros iniciales, Unicode y espacios finales.
Las comillas delimitadoras y terminadores se conservan en los CSV originales.
`CSV_ROW_NUMBER` es un ordinal técnico INTEGER; `etl_source_file` es una tabla
de metadatos adicional. Véanse [fuentes](docs/fuentes.md) y
[decisiones](docs/decisiones.md).

## Instalar

Se utiliza Python 3.13, Prefect 3.9.0, psycopg 3.3.6 y python-dotenv 1.2.4.
Pandas no es necesario para cargar el staging.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements-lock.txt` fija el entorno comprobado. Puede instalarse en lugar de
`requirements.txt`. El marcador de pywin32 limita ese paquete a Windows; no se
afirma que el proyecto se haya probado en todos los sistemas operativos.

## Configurar

Crear `.env`, `.env.reader` y, solo para aprovisionar, `.env.admin`, a partir de sus
ejemplos. Completar contraseñas reales localmente; todos esos archivos reales
están excluidos de Git. No sobrescribir una configuración existente.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .env.reader)) { Copy-Item .env.reader.example .env.reader }
if (-not (Test-Path .env.admin)) { Copy-Item .env.admin.example .env.admin }
```

Variables de ejecución: `STG_HOST`, `STG_PORT`, `STG_DATABASE=chinook_staging`,
`STG_SCHEMA=public`, `STG_USER`, `STG_PASSWORD`, `STG_SSLMODE`. El puerto 5433 es
el candidato local comprobado, no una regla universal. Las variables exportadas
prevalecen sobre `.env`. No se interpolan `$VARIABLES` dentro de contraseñas.

La cuenta administrativa usa únicamente `PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, `PGPASSWORD`. Sus credenciales no se reutilizan en el ETL. El programa
rechaza ejecutar cargas o comprobaciones normales como superusuario.

## Aprovisionar la base y las tablas

Primero consultar la instancia mediante autenticación:

```powershell
.\.venv\Scripts\python.exe scripts/provision_postgres.py --inspect
```

Después de comprobar que PostgreSQL 17 es la instancia autorizada e independiente
del DW, se puede aprovisionar nuestra base nueva con las configuraciones completas:

```powershell
.\.venv\Scripts\python.exe scripts/provision_postgres.py --create-new
```

El aprovisionador crea únicamente `chinook_staging`, `chinook_stg_loader` y
`chinook_stg_reader`, si no existen homónimos ajenos. No cambia contraseñas de
roles existentes, no borra bases y no modifica servicios ni firewall. Una base
homónima sin la marca `chinook_staging_etl:postgres:v1` provoca una detención.
También se detiene si encuentra `chinook_dw` o `chinook_datawarehouse` en la misma
instancia. Otras bases permanecen fuera de todas las sentencias de escritura.

El DDL completo está en `sql/create_staging.sql`; los permisos revisables están
en `sql/provision_access.sql`. Este último exige la base marcada y los dos roles
antes de actuar. El usuario cargador es propietario de la base y de las tablas;
el lector recibe conexión, uso de esquema y SELECT sobre las once fuentes.

CREATE DATABASE no participa en una transacción PostgreSQL. Si se interrumpe el
aprovisionamiento, revisar los recursos creados; no se aplica una limpieza ni
adopción automática de objetos desconocidos. No utilizar el aprovisionador para
convertir por la fuerza una base existente de otro proyecto.

## Ejecutar

Un comando desde esta carpeta:

```powershell
.\run.ps1
```

En otros sistemas, con el entorno configurado: `python scripts/staging_flow.py`.
El flujo **Chinook Staging ETL** muestra tres tareas locales y secuenciales:

1. **Extraer CSV:** verifica archivos, manifiesto, estructura y controles antes
   de abrir una conexión de carga.
2. **Cargar Staging:** obtiene un bloqueo transaccional, prepara las tablas solo
   si aún no existen, hace DELETE + INSERT, valida todos los campos, hashes,
   ordinales, catálogo y totales; el COMMIT sucede únicamente después de validar.
3. **Validar Staging:** abre otra transacción REPEATABLE READ READ ONLY, compara
   nuevamente y guarda evidencia en `evidence/postgresql/run-<UUID>.json`.

Las recargas no eliminan ni recrean tablas y conservan los permisos. Si falla la
carga o su validación crítica, el rollback recupera la fotografía anterior.
Si falla la tercera tarea después del COMMIT, los datos ya confirmados no se
revierten. El error lo indica expresamente; revisar y ejecutar una auditoría:

```powershell
.\run.ps1 -ValidateOnly
```

Ese modo solo lee PostgreSQL, pero escribe evidencia y metadatos locales Prefect.
Para comprobar el usuario lector:

```powershell
.\.venv\Scripts\python.exe scripts/staging_contract.py --check --env-file .env.reader
```

Las tareas no comparten conexiones abiertas ni tienen caché o reintentos
automáticos. La segunda recarga usa el mismo mecanismo transaccional que la
primera. Una recarga concurrente se rechaza sin borrar registros.

## Pruebas

Sin acceso a PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/profile_sources.py --check
```

Las pruebas de integración quedan omitidas por defecto. Solo después de contar
con nuestra base, roles y autorización explícita para esquemas aislados:

```powershell
$env:RUN_PG_INTEGRATION = '1'
$env:STG_TEST_SCHEMA_AUTHORIZED = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:RUN_PG_INTEGRATION
Remove-Item Env:STG_TEST_SCHEMA_AUTHORIZED
```

Cada prueba escribe exclusivamente en un esquema aleatorio `stg_test_*` y lo
elimina solo si conserva su marca exclusiva. Nunca corrompe ni vacía `public`.
Se prueban segunda carga, rollback a datos anteriores, fallos durante la carga,
Unicode, vacíos, espacios, ceros, lector, permisos y concurrencia. No ejecutar
estos escenarios en bases o esquemas ajenos al proyecto.

## Interfaz web de Prefect

Sin API configurada, Prefect inicia un servidor temporal. Para una interfaz
local disponible mientras se ejecutan los flujos, abrir otra terminal:

```powershell
$env:PREFECT_HOME = Join-Path (Get-Location) 'local\prefect'
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
.\.venv\Scripts\prefect.exe server start --host 127.0.0.1
```

En la terminal que ejecuta `run.ps1`:

```powershell
$env:PREFECT_API_URL = 'http://127.0.0.1:4200/api'
.\run.ps1
```

Abrir `http://127.0.0.1:4200`. No se requiere Cloud, Docker, deployments ni
workers para esta entrega. La SQLite de `local/prefect` solo guarda metadatos
de orquestación; no reemplaza las dos bases PostgreSQL del proyecto.

## Entrega e historial

[Contrato DW](docs/entrega-dw.md), [colaboración](docs/colaboracion.md),
[evidencia PostgreSQL](evidence/postgresql/README.md).
La [entrega comprobada](docs/avance-postgresql.md) registra 34 pruebas aprobadas
y dos cargas Prefect reales en Completed, con 15607 registros verificados.
El árbol de trabajo contiene la implementación PostgreSQL. La migración desde
Oracle y la limpieza posterior se explican en [limpieza del repositorio](docs/limpieza-repositorio.md).
La referencia Git `pre-cleanup-b54ab4e` permite consultar el estado completo
anterior a la limpieza; `oracle-baseline-361bb17` conserva la versión Oracle.
Los once commits anteriores permanecen en el historial. Las credenciales,
el entorno Python y el historial local de Prefect se mantienen privados en esta PC.
