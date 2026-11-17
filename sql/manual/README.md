# Preparación manual de Chinook Staging

Esta es la alternativa a `scripts/provision_postgres.py --create-new`.
Permite revisar y ejecutar la preparación por etapas. **01–06 preparan PostgreSQL;
07 carga los CSV con Python/Prefect y 08 comprueba el resultado.**

Antes de comenzar, leé los requisitos, las cuentas y la configuración del
[README principal](../../README.md). Si la preparación automática ya terminó,
no repitas el paso 04 sobre las tablas creadas: continuá con Prefect y la carga.

## Qué hace falta

Para 01–06: servidor PostgreSQL 17 encendido, dirección y puerto reales y una
cuenta superusuaria autorizada, normalmente `postgres`. Elegí un cliente:

- **PowerShell con psql 17:** copiás el comando de la opción A de cada archivo.
- **Query Tool de pgAdmin:** copiás el SQL de la opción B de cada archivo.

Los roles del proyecto no deben ser superusuarios; esta cuenta se usa solo para
prepararlos y ejecutar `SET ROLE` al crear objetos de su propiedad.

Para 07–08 también hacen falta Python 3.13, `.venv` con las dependencias,
`.env` y `.env.reader` completos, CSV/manifiesto originales y una API Prefect
funcionando. Crear las tablas con SQL no instala esas herramientas.

Los archivos conservan su ruta interna para **psql**, con órdenes como `\ir`,
`\if` y `\password`. Ahora cada uno incluye también el SQL equivalente para
**pgAdmin**, sin esas órdenes. Elegí una opción por paso; no ejecutes ambas.

## Qué copiar y dónde ejecutarlo

| Lo que estás viendo | Dónde ejecutarlo | Qué copiar |
| --- | --- | --- |
| De `# INICIO_POWERSHELL` a `# FIN_POWERSHELL` | Terminal PowerShell | Todo ese bloque del `.sql`, incluidos sus dos comentarios |
| De `-- INICIO_SQL_PGADMIN` a `-- FIN_SQL_PGADMIN` | Query Tool de pgAdmin | Todo ese bloque del `.sql`, incluidos sus dos comentarios; en el 03 hay tres bloques con sufijos |
| Bloque marcado `powershell` en este README | Terminal PowerShell | Las líneas dentro del bloque; sin los signos de Markdown ni el indicador `PS D:\Staging>` |
| Una orden como `\i sql/manual/01_inspeccionar_instancia.sql` | SQL Shell/psql, después de conectarse | La orden completa, incluida la barra invertida `\` |
| Archivo `.sql` completo | Solo psql, mediante el comando de la opción A o `\i` | psql ignora los ejemplos comentados de la cabecera y ejecuta su ruta interna |
| Archivos `.ps1` 07 y 08 | PowerShell | El comando para lanzar el archivo; son ayudantes de Python/Prefect, no SQL |

Las barras invertidas **sí importan**: `\set`, `\encoding`, `\i`, `\ir`,
`\if` y `\password` son órdenes del cliente psql. Los comentarios que comienzan
con `--` explican el archivo. Las sentencias SQL y los bloques `DO $$ ... $$;`
son las instrucciones que psql envía a PostgreSQL.

### Las dos opciones están dentro de cada SQL

La cabecera de cada archivo contiene la opción A para **PowerShell** y la
opción B para **Query Tool de pgAdmin**. Copiá únicamente desde la marca de
inicio hasta la de fin de la opción elegida. No copies los delimitadores
`/*` y `*/` que rodean los ejemplos: son comentarios para que psql y Python
no ejecuten las alternativas al procesar el archivo.

**No pegues el archivo completo en Query Tool.** La parte interna puede tener
órdenes de psql. Los ejemplos SQL marcados para pgAdmin sí se pueden pegar
completos y contienen las comprobaciones necesarias.

| Archivo | Base de conexión, como administrador | Bloque SQL para pgAdmin | Resultado esperado |
| --- | --- | --- | --- |
| [01](01_inspeccionar_instancia.sql) | `postgres` | `INICIO_SQL_PGADMIN` → `FIN_SQL_PGADMIN` | Muestra el destino y termina sin excepciones. |
| [02](02_crear_roles.sql) | `postgres` | `INICIO_SQL_PGADMIN` → `FIN_SQL_PGADMIN` | Dos roles del proyecto con inicio de sesión y contraseña. |
| [03](03_crear_base.sql) | `postgres` | Tres bloques: `_1_COMPROBAR`, `_2_CREAR_BASE`, `_3_MARCAR_BASE` | Base UTF-8, propiedad del cargador y marcada para el proyecto. |
| [04](04_crear_tablas.sql) | `chinook_staging` | `INICIO_SQL_PGADMIN` → `FIN_SQL_PGADMIN` | 11 tablas `stg_*` y `etl_source_file`, todavía sin filas. |
| [05](05_configurar_permisos.sql) | `chinook_staging` | `INICIO_SQL_PGADMIN` → `FIN_SQL_PGADMIN` | El lector puede consultar las 11 fuentes, sin modificarlas. |
| [06](06_verificar_preparacion.sql) | `chinook_staging` | `INICIO_SQL_PGADMIN` → `FIN_SQL_PGADMIN` | Comprobaciones sin errores y conteos en Messages. |

En PowerShell, todos usan las marcas `# INICIO_POWERSHELL` y
`# FIN_POWERSHELL`. El comando invoca `psql.exe`, solicita la contraseña del
administrador con `-W` y selecciona la base adecuada con `-d`. Los ejemplos
suponen `D:\PostgreSQL\17`, `D:\Staging` y `127.0.0.1:5433`; ajustalos en tu equipo.
`-v ON_ERROR_STOP=1` detiene psql ante el primer error; no agregues `-1`, porque
la creación de la base debe ejecutarse fuera de una transacción.

El archivo 02 explica cómo indicar las **claves de los roles nuevos**: son
distintas de la clave administrativa que solicita `-W`. En pgAdmin se escriben
en las variables del bloque copiado al editor; en psql se solicitan con
`\password`. Las claves deben coincidir con `.env` y `.env.reader`.

También tienen ambas opciones estos componentes, que **no son pasos extra**:

- [`_comprobar_base.sql`](_comprobar_base.sql): ayudante de 04–06; solo revisa el destino.
- [`../create_staging.sql`](../create_staging.sql): definición oficial usada por 04 y Python. Sus opciones manuales hacen lo mismo que 04.
- [`../provision_access.sql`](../provision_access.sql): permisos oficiales usados por 05 y Python. Sus opciones manuales hacen lo mismo que 05.

No ejecutes 04 y después `create_staging.sql` como si faltara otra etapa:
estarías intentando crear las mismas tablas dos veces.

### Por qué hay archivos PowerShell junto a los SQL

Los pasos 01–06 preparan PostgreSQL. Los pasos 07–08 completan el recorrido con
la carga y su comprobación, que pertenecen al programa Python/Prefect:

- `07_cargar_csv.ps1` inicia `scripts/staging_flow.py --run-once` para cargar inmediatamente.
- `08_validar_carga.ps1` ejecuta el flujo con `--validate-only` y después comprueba
  el contrato con la cuenta lectora. Las tablas deben haber sido cargadas antes.
- `_python_comun.ps1` es un ayudante que ambos reutilizan para localizar Python,
  comprobar configuración y manejar el resultado del comando.

Estos tres archivos no son necesarios para ejecutar el ETL desde `run.ps1` o
desde un deployment de Prefect. Sí forman parte de la ruta numerada documentada:
07 y 08 dependen del ayudante. Su función es ofrecer los mismos pasos sin
duplicar la lógica de carga ni de validación.

`run.ps1` **no llama** a 07, 08 ni `_python_comun.ps1`. Son accesos alternativos
al código Python: `run.ps1` sin opciones sirve el deployment para Quick Run;
`run.ps1 -RunOnce` y 07 inician una carga inmediata. Por eso se utiliza una ruta
de carga u otra, no ambas para una sola demostración.

## 1. Inspeccionar el destino

La forma más directa es abrir el archivo **01** y elegir su opción A o B.
En pgAdmin, abrí Query Tool sobre **`postgres`**, conectado como administrador,
y ejecutá el bloque SQL indicado. Solo consulta y comprueba: no crea recursos.

Si preferís una sesión interactiva de psql para los seis pasos, esta es la
alternativa; los comandos `\i` de los pasos siguientes pertenecen a esa sesión.
No hace falta abrirla si vas a usar los bloques de PowerShell o de pgAdmin.

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
\set ON_ERROR_STOP on
\encoding UTF8
\pset pager off
\i sql/manual/01_inspeccionar_instancia.sql
```

`\pset pager off` evita que las salidas largas queden detenidas en un visor.
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

**En pgAdmin:** abrir **02**, copiar su bloque SQL y reemplazar únicamente los
valores asignados a `clave_cargador` y `clave_lector` en la copia del editor.
No cambies el texto `REEMPLAZAR...` de los `IF`: detecta los valores pendientes.
Si una clave contiene `'`, escribí `''` dentro del literal SQL. No guardes las
claves reales en el archivo del repositorio. Ejecutá el bloque completo sobre
**`postgres`**. Si ya existen roles válidos del proyecto, conserva sus claves.

**En PowerShell:** el bloque A de **02** pide las claves nuevas mediante psql.
Si elegiste la sesión interactiva anterior, el equivalente es:

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

**En pgAdmin:** abrir **03** y ejecutar sus tres bloques **por separado**:

1. `_1_COMPROBAR`: revisa el destino y devuelve `crear_base`. Si hay un error, detenete. Si devuelve `false`, omití 2 y 3: la base ya está preparada.
2. `_2_CREAR_BASE`: solo si devuelve `true`. Activá **Auto-commit**, cerrá cualquier transacción previa y ejecutá únicamente este bloque, que contiene `CREATE DATABASE`. No lo envíes junto con los otros bloques.
3. `_3_MARCAR_BASE`: solo después de que el bloque 2 termine correctamente. Identifica la base que acabás de crear; no sirve para adoptar una base existente desconocida.

Después, refrescá **Databases**, seleccioná **`chinook_staging`** y abrí una
**nueva Query Tool** para 04–06. La pestaña conectada a `postgres` no cambia de
base por haber creado otra. No pegues `\connect` en Query Tool.

**En PowerShell:** el bloque A de **03** resuelve automáticamente la decisión
de crear o conservar una base válida. En la sesión interactiva de psql:

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

Solo en la sesión interactiva de **psql**, cambiá de base conservando la
conexión administrativa:

```text
\connect chinook_staging
```

El indicador pasa a `chinook_staging=#`. Los siguientes pasos deben ejecutarse
en esta base, en el mismo host/puerto.

## 4. Crear las tablas oficiales

**En pgAdmin:** sobre **`chinook_staging`**, ejecutá el bloque B completo de
**04**. Ya incluye la comprobación de destino, la transacción y las mismas 12
definiciones de tablas del SQL oficial; no hay que pegar `\ir` ni ejecutar
otro archivo después. Se confirma todo con `COMMIT` si termina correctamente.

**En PowerShell:** ejecutá el bloque A de **04**. En la sesión interactiva:

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

**En pgAdmin:** sobre **`chinook_staging`**, ejecutá el bloque B completo de
**05**. Incluye las comprobaciones y el SQL oficial de permisos.

**En PowerShell:** ejecutá el bloque A de **05**. En la sesión interactiva:

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

**En pgAdmin:** sobre **`chinook_staging`**, ejecutá el bloque B completo de
**06**. Revisá **Data Output** para las columnas y el resultado final y
**Messages** para los conteos emitidos con `NOTICE`.

**En PowerShell:** ejecutá el bloque A de **06**. En la sesión interactiva:

```text
\i sql/manual/06_verificar_preparacion.sql
```

Comprueba las 12 tablas esperadas, propietarios, claves primarias, tipos básicos
de las fuentes y permisos del lector. Muestra las columnas y la cantidad de
filas por tabla. Esta revisión SQL no sustituye la comparación completa del
contenido y estructura que realiza el ETL.

**Si acabás de crear las tablas, cero filas es el resultado esperado.**
Hasta este momento ningún paso ha leído ni insertado los CSV.
Si todas las comprobaciones terminaron sin error y usaste la sesión
interactiva de **psql**, cerrala con este comando (no va en Query Tool):

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

Este archivo llama a `scripts/staging_flow.py --run-once`, usando el Python de `.venv`
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
.\.venv\Scripts\python.exe scripts/staging_flow.py --run-once
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

En la opción PowerShell/psql se activa `ON_ERROR_STOP`: se detiene el archivo
ante un error. En pgAdmin no se usa esa orden; ejecutá el bloque marcado completo
y revisá los errores de Messages antes de seguir con otro paso. En una
sesión interactiva podés volver al indicador de psql; eso no significa que el
paso haya terminado correctamente. No continúes copiando los comandos siguientes
sin resolver la causa.

Si el indicador muestra una transacción abortada (`=!#`) o quedó una transacción
abierta por un paso fallido, ejecutá en psql o en la misma Query Tool:

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
La separación del paso 03 se debe a la restricción de
[CREATE DATABASE](https://www.postgresql.org/docs/17/sql-createdatabase.html).
