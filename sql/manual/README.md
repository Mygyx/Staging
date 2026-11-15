# Preparación manual de Chinook Staging

Esta es la alternativa a `scripts/provision_postgres.py --create-new`.
Permite revisar y ejecutar la preparación por etapas. **01–06 preparan PostgreSQL;
07 carga los CSV con Python/Prefect y 08 comprueba el resultado.**

Antes de comenzar, leé los requisitos, las cuentas y la configuración del
[README principal](../../README.md). Si la preparación automática ya terminó,
no repitas el paso 04 sobre las tablas creadas: continuá con Prefect y la carga.

## Qué hace falta

Para 01–06: servidor PostgreSQL 17 encendido, cliente **psql 17**, dirección y
puerto reales y una cuenta superusuaria autorizada, normalmente `postgres`.
Los roles del proyecto no deben ser superusuarios; esta cuenta se usa solo para
prepararlos y ejecutar `SET ROLE` al crear objetos de su propiedad.

Para 07–08 también hacen falta Python 3.13, `.venv` con las dependencias,
`.env` y `.env.reader` completos, CSV/manifiesto originales y una API Prefect
funcionando. Crear las tablas con SQL no instala esas herramientas.

Los archivos usan instrucciones de **psql** como `\i`, `\ir`, `\if` y
`\password`. No se deben pegar completos en el Query Tool de pgAdmin, que
ejecuta SQL pero no esos comandos del cliente. Podés usar SQL Shell (psql) o
el ejecutable `psql.exe` incluido con la instalación de PostgreSQL.

## 1. Abrir psql e inspeccionar el destino

Desde PowerShell, entrá a la raíz del clon y abrí una conexión administrativa.
Este ejemplo supone el proyecto en D:, PostgreSQL instalado en
`D:\PostgreSQL\17` y puerto 5433; ajustá las rutas y el puerto a tu instalación:

```powershell
Set-Location D:\Staging
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d postgres -W
```

Si `psql` está disponible en PATH, también podés usar:

```powershell
psql -X -h 127.0.0.1 -p 5433 -U postgres -d postgres -W
```

Ejecutá **una** de esas variantes. `-h` y `-p` seleccionan la instancia;
`-U` es la cuenta administrativa; `-d postgres` usa la base de mantenimiento.
`-W` pide la contraseña de esa cuenta y `-X` evita cargar personalizaciones
de psql que podrían alterar esta secuencia. No uses `-1` ni abras una
transacción que abarque toda la guía: la creación de la base debe hacerse fuera
de una transacción.

A partir de ahora verás el indicador `postgres=#`. Estos comandos van **dentro
de psql**, no en PowerShell:

```text
\pset pager off
\i sql/manual/01_inspeccionar_instancia.sql
```

El primer comando evita que las salidas largas queden detenidas en un visor.
El archivo 01 solo consulta y comprueba: muestra conexión, versión, puerto,
bases y roles. Revisá que corresponda al destino que querés preparar.

Se exige PostgreSQL 17 y se rechazan los nombres DW conocidos en esta misma
instancia. Una base o rol homónimo solo se acepta si ya pertenece al proyecto
con propietario, marca y privilegios esperados. El proceso no adopta recursos
ajenos ni cambia otras bases.

Las rutas anteriores parten de la raíz de `Staging`. Si abriste SQL Shell desde
otra carpeta, usá una ruta absoluta, por ejemplo:
`\i 'D:/Staging/sql/manual/01_inspeccionar_instancia.sql'`.
Los `\ir` internos resuelven sus archivos respecto del script que los incluye.

## 2. Crear las cuentas PostgreSQL

En la misma sesión, todavía conectado a `postgres` como administrador:

```text
\i sql/manual/02_crear_roles.sql
```

Se crean `chinook_stg_loader` y `chinook_stg_reader` sin privilegios de
administración del servidor. psql pide y confirma una contraseña para cada rol
nuevo sin mostrarla ni guardarla en el archivo SQL.

- Para el cargador elegí la misma clave que guardaste como `STG_PASSWORD` en
  `.env`.
- Para el lector elegí la misma clave que guardaste en `.env.reader`.
- Estas son claves de las cuentas nuevas; no se pide reutilizar la del administrador.

Los roles nuevos se crean inicialmente sin inicio de sesión; se habilitan y
confirman en la transacción cuando tienen contraseña. Se marcan como recursos
de este proyecto. Si ya existen con la marca y privilegios correctos, se conserva
su contraseña y no se vuelve a solicitar.

Si olvidaste una contraseña existente, revisá primero la identidad del rol con
el administrador. Un cambio intencional mediante `\password nombre_del_rol`
también requiere actualizar el archivo de conexión y cualquier cliente que use
esa cuenta; no es algo que estos scripts hagan automáticamente.

## 3. Crear la base

Todavía conectado como administrador a `postgres`:

```text
\i sql/manual/03_crear_base.sql
```

Crea `chinook_staging` con codificación UTF-8 y el cargador como propietario,
usando `template0` y ordenación `C` para coincidir con el aprovisionador Python.
Agrega el comentario `chinook_staging_etl:postgres:v1` que el ETL exige para
reconocer la base.

Si ya existe y tiene el propietario y la marca esperados, se conserva.
No se incluyen instrucciones `DROP DATABASE` ni limpieza de datos.
Si hubiera una interrupción entre crear la base y agregar su comentario,
inspeccioná el resultado antes de continuar; no marques una base desconocida
solo para saltarte la comprobación.

Ahora cambiá de base conservando la conexión administrativa:

```text
\connect chinook_staging
```

El indicador pasa a `chinook_staging=#`. Los siguientes pasos deben ejecutarse
en esta base, en el mismo host/puerto.

## 4. Crear las tablas oficiales

Conectado a `chinook_staging` como administrador:

```text
\i sql/manual/04_crear_tablas.sql
```

Comprueba que el esquema `public` esté vacío de tablas/vistas y cambia
temporalmente al rol cargador para ejecutar
[create_staging.sql](../create_staging.sql). Así las 11 tablas `stg_*` y
`etl_source_file` quedan a nombre del cargador.

Este paso es de **inicialización**, no de recarga. Se detiene si ya hay objetos
en `public`, sin borrarlos. Si ya completaste la preparación, no hace falta
volver a crear tablas para cargar de nuevo los CSV.

## 5. Asignar permisos al lector

En la misma base y con la cuenta administrativa:

```text
\i sql/manual/05_configurar_permisos.sql
```

Ejecuta el mismo [provision_access.sql](../provision_access.sql) que usa la
ruta automática. El lector recibe conexión a la base, uso del esquema y
`SELECT` sobre las 11 tablas fuente. No recibe escritura ni lectura del
catálogo técnico. El cargador conserva la propiedad de la base/tablas.

También se quitan permisos generales de conexión y del esquema `public` para
que el acceso se asigne de forma explícita a los roles del proyecto.

## 6. Revisar la preparación

```text
\i sql/manual/06_verificar_preparacion.sql
```

Comprueba las 12 tablas esperadas, propietarios, claves primarias, tipos básicos
de las fuentes y permisos del lector. Muestra las columnas y la cantidad de
filas por tabla. Esta revisión SQL no sustituye la comparación completa del
contenido y estructura que realiza el ETL.

**Si acabás de crear las tablas, cero filas es el resultado esperado.**
Hasta este momento ningún paso ha leído ni insertado los CSV.
Si todas las comprobaciones terminaron sin error, cerrá psql:

```text
\q
```

## 7. Cargar los CSV mediante Prefect

Regresá a PowerShell en la raíz del proyecto. Iniciá la API y configurá la
terminal del cliente como explica el
[paso 5 del README principal](../../README.md#5-preparar-prefect-para-ver-las-ejecuciones).
El ayudante exige `PREFECT_API_URL` para que la ejecución use ese servidor
conocido.

Después:

```powershell
& .\sql\manual\07_cargar_csv.ps1
```

Este archivo llama a `scripts/staging_flow.py`, usando el Python de `.venv`
y las credenciales del cargador en `.env`. No vuelve a crear la base ni inicia
un servidor Prefect. El flujo comprueba fuentes, carga de forma transaccional
y audita los datos. Si falla, el ayudante devuelve un error y no continúa con
la validación siguiente.

Se reutiliza el ETL porque allí están el manifiesto, las comprobaciones de
fidelidad y el registro de tareas en Prefect. No hay una segunda carga con
`COPY` que omita esas validaciones. El resultado esperado con las fuentes del
repo es `Completed`, 15.607 filas fuente y 11 registros en el catálogo técnico.

Si PowerShell no permite ejecutar scripts, el equivalente es:

```powershell
.\.venv\Scripts\python.exe scripts/staging_flow.py
```

## 8. Validar el contenido y la cuenta del DW

En la misma terminal PowerShell, después de completar la carga:

```powershell
& .\sql\manual\08_validar_carga.ps1
```

Ejecuta la auditoría `--validate-only` con el cargador y después comprueba
el contrato con `.env.reader`. No recarga ni modifica las tablas; genera
evidencia de auditoría y metadatos de Prefect. Una tabla vacía no supera esta
validación aunque su definición SQL sea correcta.

Los comandos equivalentes, si no usás el ayudante, son:

```powershell
.\.venv\Scripts\python.exe scripts/staging_flow.py --validate-only
.\.venv\Scripts\python.exe scripts/staging_contract.py --check --env-file .env.reader
```

Si el primero falla, resolvelo antes de ejecutar el siguiente. Después se
entregan al equipo DW las credenciales del **lector**, por un canal privado,
junto con host/puerto accesibles y el [contrato de lectura](../../docs/entrega-dw.md).

## Si falla un paso o necesitás retomarlo

Los SQL activan `ON_ERROR_STOP`: se detiene el archivo ante un error. En una
sesión interactiva podés volver al indicador de psql; eso no significa que el
paso haya terminado correctamente. No continúes copiando los comandos siguientes
sin resolver la causa.

Si el indicador muestra una transacción abortada (`=!#`) o quedó una transacción
abierta por un paso fallido, ejecutá dentro de psql:

```sql
ROLLBACK;
```

Revisá la base y cuenta de conexión antes de retomar. Los pasos 01–03 requieren
la base `postgres`; 04–06, `chinook_staging`, siempre con el administrador.
Después de un error, `ROLLBACK` también revierte el `SET ROLE` que estaba dentro
de esa transacción.

Los pasos 02 y 03 pueden reconocer recursos ya preparados sin cambiar claves.
El 04 rechaza un esquema no vacío: si ya terminó antes, revisá su estructura,
completá 05 si faltan permisos y usá 06 para comprobarla. Omití 04 solamente
cuando confirmés que las tablas oficiales están completas. Ante una estructura
parcial o ajena, no uses `DROP` ni recreaciones a ciegas.

Esta ruta conserva las comprobaciones del proyecto. No evita los requisitos
de conexión, credenciales válidas o instancia separada. Para repetir una carga
sobre una base preparada, usá 07; para auditarla sin recargar, usá 08.

Referencia de los comandos del cliente:
[documentación oficial de psql 17](https://www.postgresql.org/docs/17/app-psql.html).
