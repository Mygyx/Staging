# Chinook Staging ETL

Este repositorio carga **11 CSV → Python con Prefect → PostgreSQL Staging**.
Después, el [repositorio del Data Warehouse](https://github.com/Brianrp19/chinook_datawarehouse)
lee Staging y construye su modelo analítico. Aquí se prepara y carga la fuente;
la creación del DW y sus reportes pertenece al otro repositorio.

**Preparar la base y cargar los datos son pasos distintos.** El aprovisionador
crea la base, las cuentas y las tablas. El flujo ETL lee los CSV, los carga y
comprueba el resultado. Clonar el repositorio o instalar Python no crea la base.

## Qué incluye el repositorio

| Recurso | Para qué sirve |
| --- | --- |
| [data/raw](data/raw) | Los 11 CSV originales; no hace falta conseguirlos por separado. |
| [data/manifest.json](data/manifest.json) | Inventario con tamaños, encabezados, cantidades y hashes para detectar cambios en las fuentes. |
| [requirements.txt](requirements.txt) | Dependencias Python: Prefect 3.9.0, psycopg 3.3.6 y python-dotenv 1.2.4. |
| [.env.example](.env.example), [.env.admin.example](.env.admin.example), [.env.reader.example](.env.reader.example) | Plantillas de conexión que cada persona completa localmente. |
| [scripts/provision_postgres.py](scripts/provision_postgres.py) | Inspección y preparación automática de PostgreSQL. |
| [sql/create_staging.sql](sql/create_staging.sql) | Definición de las 11 tablas fuente y la tabla técnica. |
| [sql/provision_access.sql](sql/provision_access.sql) | Permisos que permiten al DW leer las fuentes sin modificarlas. |
| [sql/manual](sql/manual/README.md) | Alternativa numerada para preparar la base con `psql` y luego ejecutar el ETL. |
| [scripts/staging_flow.py](scripts/staging_flow.py), [run.ps1](run.ps1) | Flujo de carga y su acceso directo para PowerShell. |

Las fuentes contienen **15.607 filas y 66.439 campos originales**. Las 11 tablas
`stg_*` conservan los campos fuente como `TEXT`, sus nombres CamelCase y sus
valores exactos: ceros iniciales, Unicode, espacios finales y 1.339 vacíos
representados como `''`. Staging conserva esta fotografía; las conversiones
analíticas se hacen después en el DW.

Cada tabla fuente agrega `"CSV_ROW_NUMBER"`, un entero que identifica la posición
del registro. La tabla adicional `etl_source_file` guarda metadatos de los 11
archivos. Por eso hay **12 tablas**, aunque los CSV sean 11.
Más detalle en [fuentes](docs/fuentes.md) y [decisiones](docs/decisiones.md).

## 1. Requisitos antes de empezar

Necesitás:

- **PostgreSQL 17 instalado y su servidor encendido**, en una dirección y un puerto
  que conozcás. Tener pgAdmin abierto no significa que el servidor esté encendido.
- Una **cuenta administrativa de PostgreSQL que ya exista**, normalmente
  `postgres`, con su contraseña y permisos para crear roles y bases y asignar
  el propietario. Para una instalación local nueva puede usarse el administrador
  creado por el instalador. No se usa esa cuenta para las cargas normales.
- La instancia de Staging separada de la del DW, como está implementado en este
  proyecto. El aprovisionamiento rechaza una instancia que ya contenga
  `chinook_dw` o `chinook_datawarehouse`. Dos bases con nombres diferentes en
  un mismo servidor no equivalen a dos instancias.
- **Python 3.13** y Git para clonar, instalar dependencias y ejecutar los scripts.
  Los ejemplos siguientes usan Windows y PowerShell.
- El repositorio completo: conservar CSV, manifiesto, scripts y carpeta `sql`.
  El aprovisionador automático también revisa las fuentes antes de crear objetos.

**No necesitás crear previamente `chinook_staging`, sus roles ni sus tablas**
si vas a utilizar el aprovisionador automático. Sí necesitás un servidor
PostgreSQL funcionando y acceso administrativo a él. El script no instala
PostgreSQL ni enciende su servicio.

El puerto del servidor se elige al instalar/configurar PostgreSQL. Las plantillas
de este proyecto usan **5433** para Staging. Si tu servidor usa 5432 u otro puerto,
cambiá las tres configuraciones para que coincidan con el puerto real.
No hace falta reinstalar PostgreSQL solo por esa diferencia.

### Comprobar que PostgreSQL esté disponible

En una instalación local de Windows, primero comprobá el servicio. Este ejemplo
usa el nombre `postgresql-x64-17`; si tu instalación tiene otro nombre, usá ese.
Para iniciarlo, abrí PowerShell como administrador:

```powershell
Start-Service -Name postgresql-x64-17
Get-Service -Name postgresql-x64-17
```

`Start-Service` enciende el servidor instalado y `Get-Service` consulta su estado.
Esperamos **`Running`**. Si ya está encendido, basta consultar el estado.

En una terminal normal podés comprobar si acepta conexiones. Ajustá la ruta si
instalaste PostgreSQL en otra carpeta, y el puerto si no usa 5433:

```powershell
& 'D:\PostgreSQL\17\bin\pg_isready.exe' -h 127.0.0.1 -p 5433 -U postgres -d postgres
```

Salida esperada para este ejemplo:

```text
127.0.0.1:5433 - accepting connections
```

Esto confirma disponibilidad del servidor, **no valida la contraseña ni comprueba
que Staging esté preparada**. La autenticación se comprueba después con
`provision_postgres.py --inspect`. A partir de aquí, usá PowerShell normal para
preparar Python y ejecutar el proyecto.

## 2. Descargar y preparar Python

### Descargar el repositorio

Este ejemplo guarda el clon en el disco D:

```powershell
Set-Location D:\
git clone https://github.com/Mygyx/Staging.git
Set-Location .\Staging
```

Si ya tenés el repositorio, omití el clon y entrá directamente con
`Set-Location D:\Staging`. Desde ahora los comandos parten de esa carpeta.

### Qué son Python, uv, venv y pip

| Herramienta o archivo | Función en esta instalación |
| --- | --- |
| Python | Intérprete que ejecuta los scripts del proyecto. Se usa la versión 3.13. |
| uv | Herramienta que administra versiones de Python y paquetes. Aquí se usa opcionalmente para instalar/encontrar Python 3.13 en D:. |
| venv | Módulo incluido en Python que crea un entorno virtual con bibliotecas propias para el proyecto. |
| `.venv` | Carpeta del entorno virtual de este repositorio. |
| pip | Instalador de las bibliotecas que necesita el proyecto, ejecutado con el Python de `.venv`. |
| `requirements.txt` | Lista de bibliotecas y versiones que pip debe instalar. |

Tener Python instalado permite ejecutar código, pero no significa que ya tengas
Prefect, psycopg y python-dotenv, ni las versiones que espera este proyecto.
El entorno virtual permite instalar esas bibliotecas sin mezclarlas con las de
otros proyectos. Por ejemplo, otro proyecto puede necesitar una versión distinta
de Prefect: cada entorno mantiene la suya.

**Se recomienda usar `.venv` para este proyecto.** No es una máquina virtual ni
incluye PostgreSQL. Se crea a partir de un Python base que debe seguir disponible;
no borres ni muevas esa instalación después. Tampoco convierte Python 3.11 en
3.13: hay que crear el entorno usando el intérprete de la versión correcta.

`.venv` y `.env` son cosas distintas: la primera guarda el entorno Python; el
segundo es un archivo de configuración con credenciales de conexión.

### Elegir una forma de obtener Python 3.13

Usá **una** de las rutas siguientes. `uv` no es un requisito del flujo ETL si ya
tenés Python 3.13 disponible por otro medio.

**Ruta A: Python 3.13 ya instalado y comando `py` disponible.**

```powershell
py -3.13 --version
py -3.13 -m venv .venv
```

El primer comando debe mostrar `Python 3.13.x`; la última parte es la versión de
parche y puede variar. El segundo crea `.venv` y normalmente termina sin imprimir
un mensaje. Si `py` no existe o no encuentra esa versión, usá la ruta B o el
ejecutable real de una instalación Python 3.13 que ya tengas.

**Ruta B: instalar Python 3.13 en D: usando uv.**

Esta es la ruta utilizada en la guía para una PC sin el comando `py`. Requiere
`uv` instalado y accesible desde PowerShell. Comprobalo con `uv --version`:
debe mostrar `uv` y un número de versión. Si no se reconoce, instalalo siguiendo
su [guía oficial](https://docs.astral.sh/uv/getting-started/installation/), o usá
la ruta A con Python 3.13. No se necesita uv para las cargas posteriores.

En PowerShell normal, desde `D:\Staging`, ejecutá bloque por bloque y continuá
cuando el anterior termine sin errores:

```powershell
$env:UV_PYTHON_INSTALL_DIR = 'D:\Python'
$env:UV_CACHE_DIR = 'D:\Python\uv-cache'
uv python install 3.13 --no-bin --no-registry
```

Las variables eligen la carpeta del Python administrado y la caché de descargas.
El comando descarga e instala la versión solicitada, o informa que ya está
instalada en ese destino. El texto y la versión de parche pueden variar;
comprobaremos el intérprete en el siguiente bloque. `--no-bin` evita crear
accesos globales al ejecutable y `--no-registry` evita registrarlo en Windows.

```powershell
$pythonStaging = uv python find --system --managed-python 3.13
$pythonStaging
& $pythonStaging --version
& $pythonStaging -m venv .venv
```

`find` busca el Python administrado de la versión solicitada, ignorando entornos
virtuales activos. La variable guarda su ruta y `&` ejecuta esa ruta en PowerShell.
Esperamos una ruta dentro de `D:\Python` y `Python 3.13.x`; si aparece otro disco
o versión, revisá el destino antes de crear el entorno. `-m venv .venv` crea el
entorno en `D:\Staging\.venv`.

Las variables `$env:...` anteriores duran esa sesión de PowerShell. Si abrís otra
terminal para repetir la ruta B, volvé a definirlas. Una vez creado el entorno,
los comandos con `.\.venv\Scripts\python.exe` utilizan directamente ese entorno.

### Instalar las bibliotecas del proyecto

Después de completar la ruta A o B:

```powershell
.\.venv\Scripts\python.exe -m pip install --cache-dir D:\Python\pip-cache -r requirements.txt
```

`-m pip` ejecuta el instalador que pertenece a ese Python; `-r requirements.txt`
le indica que lea la lista de dependencias del repositorio. `--cache-dir` guarda
los paquetes descargados en D:, mientras las bibliotecas instaladas quedan dentro
de `.venv`. Podés ajustar la carpeta de caché a tu equipo.

Las dependencias directas son Prefect 3.9.0 para orquestar las tareas,
psycopg 3.3.6 con su distribución binaria para conectar a PostgreSQL y
python-dotenv 1.2.4 para leer la configuración. pip también instala las
dependencias que requieren esas bibliotecas.

La primera instalación normalmente muestra descargas y `Successfully installed`;
al repetirla puede mostrar `Requirement already satisfied`. Lo importante es que
termine sin errores y que pasen las comprobaciones siguientes.

La ruta `.\.venv\Scripts\python.exe` significa «usar el Python de este proyecto».
No hace falta activar el entorno para estos comandos. Crear `.venv` e instalar
dependencias son pasos de preparación: no se repiten en cada carga, salvo que
recreés el entorno o cambien los requisitos.

[requirements-lock.txt](requirements-lock.txt) fija también las dependencias
indirectas del entorno registrado; puede usarse en lugar de `requirements.txt`.
Pandas no es necesario para esta carga. Los archivos reales de configuración y
`.venv` están excluidos de Git: cada persona los prepara en su equipo.

### Activación opcional del entorno en PowerShell

Una terminal puede mostrar `(.venv)` antes de la ruta. Eso significa que el
entorno ya está activado: al escribir `python` o `prefect`, esa terminal busca
primero los ejecutables de `.venv`. Activarlo utiliza el entorno existente;
no crea uno nuevo ni instala bibliotecas.

Si necesitás activarlo manualmente, desde la raíz del proyecto:

```powershell
& .\.venv\Scripts\Activate.ps1
```

Si la política de ejecución bloquea los scripts locales, y tu equipo permite
cambiarla para la sesión, estos comandos ajustan esa sesión y activan el entorno:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
```

`Process` limita el ajuste a esa sesión y sus procesos hijos; se pierde al cerrar
la sesión. `RemoteSigned` permite scripts locales y exige firma a los marcados
como descargados de Internet, salvo que estén desbloqueados. La configuración
efectiva también puede depender de políticas administrativas del equipo.
Ver [políticas de PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies).

Algunos editores ejecutan ambas instrucciones en una sola línea con `;` y
paréntesis. Esos signos separan y agrupan los comandos; el efecto es el mismo.
No hace falta repetir la activación si ya aparece `(.venv)`. Los ejemplos del
README usan la ruta explícita `.\.venv\Scripts\python.exe`, por lo que también
funcionan sin activar el entorno.

### Comprobar la instalación antes de configurar la base

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "from importlib.metadata import version; print('\n'.join(f'{p}=={version(p)}' for p in ['prefect', 'psycopg', 'python-dotenv']))"
.\.venv\Scripts\python.exe scripts/profile_sources.py --check
```

| Comprobación | Resultado esperado | Qué demuestra |
| --- | --- | --- |
| `--version` | `Python 3.13.x` | El entorno usa la versión de Python indicada. |
| `pip check` | `No broken requirements found.` | Las dependencias instaladas declaran versiones compatibles entre sí. |
| Consulta con `importlib.metadata` | `prefect==3.9.0`, `psycopg==3.3.6` y `python-dotenv==1.2.4`, en líneas separadas. | Las tres dependencias directas están presentes con las versiones del repo. |
| `profile_sources.py --check` | `OK: 11 CSV, 15607 registros; manifiesto intacto` | Las fuentes y su inventario coinciden sin modificarlos. |

`pip check` por sí solo no demuestra que hayas instalado todas las bibliotecas
de este proyecto; por eso también se consultan sus versiones. Estas comprobaciones
no crean bases, no cargan CSV y no inician Prefect. Tampoco prueban aún la conexión
a PostgreSQL ni una ejecución completa del sistema.

Referencias: [entornos virtuales de Python](https://docs.python.org/3.13/tutorial/venv.html),
[versiones de Python con uv](https://docs.astral.sh/uv/concepts/python-versions/) y
[alcance de pip check](https://pip.pypa.io/en/stable/cli/pip_check/).

## 3. Configurar conexiones y entender las cuentas

En PostgreSQL, un **rol con permiso de inicio de sesión** funciona como un usuario.
Estas cuentas pertenecen al servidor PostgreSQL; no son usuarios de Windows,
compañeros del grupo ni clientes que aparecen dentro de los CSV.

| Cuenta | ¿Debe existir antes? | Uso |
| --- | --- | --- |
| `postgres` u otro administrador autorizado | Sí, se configura al instalar/administrar PostgreSQL. | Crear la base, los roles y los permisos iniciales. |
| `chinook_stg_loader` | No, lo crea el aprovisionamiento. | Propietario de Staging y sus tablas; ejecuta la carga y validación. No es superusuario del servidor. |
| `chinook_stg_reader` | No, lo crea el aprovisionamiento. | El DW consulta las 11 tablas fuente. No puede escribirlas ni consultar el catálogo técnico. |

Se separan para que el DW pueda consultar Staging sin recibir las credenciales
del cargador ni del administrador.

Copiá las plantillas **sin sobrescribir una configuración existente**:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .env.reader)) { Copy-Item .env.reader.example .env.reader }
if (-not (Test-Path .env.admin)) { Copy-Item .env.admin.example .env.admin }
```

Abrí esos tres archivos en tu editor y reemplazá `CHANGE_ME`:

| Archivo | Qué completar | Cuándo se utiliza |
| --- | --- | --- |
| `.env.admin` | Host y puerto reales, `PGDATABASE=postgres`, nombre y contraseña del administrador **existente**. | Inspección y aprovisionamiento automático. |
| `.env` | Mismo host/puerto, `STG_DATABASE=chinook_staging`, `STG_SCHEMA=public`, `STG_USER=chinook_stg_loader` y una contraseña elegida para ese rol. | Crear el cargador y ejecutar el ETL. |
| `.env.reader` | Mismo host/puerto/base/esquema, `STG_USER=chinook_stg_reader` y otra contraseña elegida para ese rol. | Crear el lector y comprobar el acceso del DW. |

Para los dos roles nuevos, **elegís las contraseñas antes de ejecutar**
`--create-new`: el script crea las cuentas usando esos valores. La contraseña
administrativa, en cambio, debe ser la que ya funciona en PostgreSQL.
Si los roles del proyecto ya existen, el script conserva sus contraseñas:
los archivos deben coincidir con ellas.

Para leer las conexiones:

- **Host**: equipo donde corre PostgreSQL. `127.0.0.1` apunta a esta misma PC.
- **Puerto**: entrada de esa instancia PostgreSQL; en las plantillas, 5433.
- **Base**: `postgres` es la base de mantenimiento para preparar el proyecto;
  `chinook_staging` es la base de trabajo que se va a crear.
- **Esquema**: `public` agrupa las tablas dentro de `chinook_staging`.
- **Usuario y contraseña**: identifican el rol con el que se abre cada conexión.
- **STG_SSLMODE**: se incluye como `prefer`; un servidor remoto puede requerir
  otra configuración de conexión según su administrador.

Las variables `STG_*` exportadas en PowerShell prevalecen sobre los archivos en
las ejecuciones normales, incluso al comprobar `.env.reader`. Las `PG*`
exportadas prevalecen para el administrador. Si una conexión ignora lo que
editaste, revisá las variables de esa terminal. El aprovisionamiento lee sus
configuraciones de cargador/lector directamente de los archivos.

No publiques los archivos `.env*` reales ni sus claves. `python-dotenv` permite
valores entre comillas si hacen falta; el proyecto no interpola `$VARIABLES`
dentro de las contraseñas.

Podés revisar las fuentes antes de conectarte a PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts/profile_sources.py --check
```

Esto compara los CSV con su manifiesto y documentación sin escribirlos.
El resultado esperado es `OK: 11 CSV, 15607 registros; manifiesto intacto`.
No crea ni carga ninguna base.

## 4. Preparar PostgreSQL: elegir una de estas rutas

### Ruta A: aprovisionamiento automático

Primero inspeccioná el destino:

```powershell
.\.venv\Scripts\python.exe scripts/provision_postgres.py --inspect
```

`--inspect` utiliza `.env.admin` para consultar versión, puerto, cuenta,
capacidades y bases existentes. No crea objetos. Revisá que sea **tu instancia
de Staging**, PostgreSQL 17, y que no haya una base homónima ajena al proyecto.
Para esta inspección basta la conexión administrativa; la creación necesita
también `.env` y `.env.reader` completos.

Luego prepará la base:

```powershell
.\.venv\Scripts\python.exe scripts/provision_postgres.py --create-new
```

`--create-new` **ejecuta la preparación; no genera archivos SQL**. En concreto:

1. Revisa las tres conexiones, el destino y los CSV/manifiesto.
2. Crea `chinook_stg_loader` y `chinook_stg_reader` si no existen.
3. Crea `chinook_staging` en UTF-8, con el cargador como propietario.
4. Utiliza [create_staging.sql](sql/create_staging.sql) para crear las 12 tablas
   cuando el esquema está vacío.
5. Utiliza [provision_access.sql](sql/provision_access.sql) para asignar los
   permisos del lector y limitar el acceso general a la base.

**Al terminar la preparación, las tablas nuevas siguen vacías.**
La salida `"data_loaded": false` es normal: todavía falta ejecutar el flujo ETL
del paso 6. El aprovisionador no inicia Prefect, no crea el DW y no carga CSV.

Por lo tanto, para que ese comando funcione, deben estar listos: PostgreSQL 17
encendido y accesible, administrador válido, Python con las dependencias,
los tres archivos de conexión completos y coherentes, CSV/manifiesto originales
y los SQL del repositorio. No requiere `psql` para esta ruta: Python se conecta
mediante psycopg.

El nombre esperado es **`chinook_staging`**, no simplemente `staging`.
Los nombres de ambos roles y el esquema `public` también están fijados para
este aprovisionador; cambiar solo el nombre en un archivo no cambia el contrato.

Los objetos creados se identifican con el comentario
`chinook_staging_etl:postgres:v1`. Si existe una base o un rol homónimo ajeno,
el script se detiene; no los adopta ni sobrescribe. Si ya hay tablas, exige la
estructura completa esperada. Las repeticiones conservan los datos existentes;
no se debe usar la preparación como sustituto de la carga.

`CREATE DATABASE` no puede formar parte de una transacción. Si el proceso se
interrumpe, puede haber creado algunos recursos: inspeccioná antes de reintentar.
No borres bases ni agregues marcas a objetos desconocidos para forzar la ejecución.

### Ruta B: preparación manual numerada

La [guía manual](sql/manual/README.md) explica cómo preparar lo mismo con el
cliente `psql` de PostgreSQL 17. Esta ruta requiere una cuenta superusuaria
autorizada para ejecutar sus comprobaciones y cambiar al propietario de las tablas.
Es una alternativa si querés revisar cada etapa o si no podés usar el aprovisionador.

| Orden | Archivo | Resultado |
| --- | --- | --- |
| 01 | [Inspeccionar instancia](sql/manual/01_inspeccionar_instancia.sql) | Muestra y comprueba el servidor y los objetos existentes. |
| 02 | [Crear roles](sql/manual/02_crear_roles.sql) | Pide las contraseñas y crea los dos roles del proyecto. |
| 03 | [Crear base](sql/manual/03_crear_base.sql) | Crea `chinook_staging`, su propietario y su marca. |
| 04 | [Crear tablas](sql/manual/04_crear_tablas.sql) | Ejecuta el DDL oficial sobre el esquema vacío. |
| 05 | [Configurar permisos](sql/manual/05_configurar_permisos.sql) | Ejecuta el SQL oficial de acceso. |
| 06 | [Verificar preparación](sql/manual/06_verificar_preparacion.sql) | Revisa estructura básica, propietario, permisos y cantidades actuales. |
| 07 | [Cargar CSV](sql/manual/07_cargar_csv.ps1) | Ejecuta el flujo Python/Prefect existente. |
| 08 | [Validar carga](sql/manual/08_validar_carga.ps1) | Audita los datos cargados y el acceso del lector. |

Los pasos 01–06 se ejecutan **dentro de psql**; 07–08, desde **PowerShell**.
Los archivos 04 y 05 incluyen los SQL originales: no hay dos versiones del DDL.
La ruta manual también respeta los nombres, marcas y separación de instancias.

Elegí **A o B** para preparar la base. Si A ya terminó correctamente, pasá al
paso 5 de este README; no ejecutes 04 manual sobre tablas ya creadas.
La alternativa manual no soluciona un servidor apagado ni una contraseña inválida.

## 5. Preparar Prefect para ver las ejecuciones

Para un dashboard local persistente, abrí **dos terminales PowerShell en la raíz
del repositorio**. Se usa 4201 para el ejemplo; este puerto es de Prefect y no
tiene relación con el 5433 de PostgreSQL.

**Terminal 1 — servidor Prefect:**

```powershell
$env:PREFECT_HOME = Join-Path (Get-Location) 'local\prefect'
New-Item -ItemType Directory -Path $env:PREFECT_HOME -Force | Out-Null
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
.\.venv\Scripts\prefect.exe config set PREFECT_API_URL=http://127.0.0.1:4201/api PREFECT_UI_API_URL=http://127.0.0.1:4201/api
.\.venv\Scripts\prefect.exe server start --host 127.0.0.1 --port 4201
```

`config set` guarda dos direcciones en el perfil local: `PREFECT_API_URL` es la
conexión que usa el cliente Python y `PREFECT_UI_API_URL` es la que usa el
dashboard en el navegador. Ambas deben apuntar a la API del servidor en 4201.
El cambio queda guardado en el perfil; no se limita a esta terminal.

Si iniciaste el servidor sin guardar previamente esa configuración, puede
aparecer un menú para configurar `PREFECT_API_URL`.
Elegí **Set `PREFECT_API_URL` in the current profile** con la flecha abajo y Enter.
Si el perfil se llama `ephemeral`, ese es su nombre de configuración; no indica
que la base Staging sea temporal. Cuando pida el valor de la URL, escribí
**`http://127.0.0.1:4201/api`**. La versión instalada puede ofrecer 4200 como
valor predeterminado en esa pregunta: reemplazalo por el puerto 4201 de esta guía.

Esta elección guarda la dirección de la API en el perfil local activo, que es
un conjunto de ajustes de Prefect. No crea otra base PostgreSQL ni otra cuenta
del proyecto. En la terminal cliente también se indica la URL explícitamente
para que el flujo publique sus resultados en ese mismo servidor.

`PREFECT_HOME` guarda configuración e historial de orquestación en el proyecto;
`New-Item` prepara la carpeta. `server start` deja la API y la interfaz web
funcionando mientras esa terminal siga abierta. Abrí
[http://127.0.0.1:4201](http://127.0.0.1:4201).

Si cambiás el perfil mientras el servidor ya está encendido, detenelo con
**Ctrl+C** en su terminal y volvé a iniciarlo para aplicar los ajustes.

### Si el dashboard muestra "Unable to connect to Prefect server"

Primero diferenciá la API del dashboard. Desde otra PowerShell podés consultar:

```powershell
Invoke-RestMethod 'http://127.0.0.1:4201/api/health'
Invoke-RestMethod 'http://127.0.0.1:4201/ui-settings' | Select-Object api_url
```

Con el servidor listo, esperamos `True` en la primera comprobación y
`http://127.0.0.1:4201/api` como `api_url` en la segunda. Si la API responde pero
el dashboard recibe una URL con 4200, hay una diferencia de configuración: el
servidor escucha en 4201, pero la interfaz intenta consultar otro puerto.

En ese caso, detené el servidor con Ctrl+C, volvé a ejecutar el bloque de
**Terminal 1**, incluyendo `config set` para las dos direcciones, y actualizá
la página cuando termine el arranque. Guardar solo una variable en la terminal
cliente puede permitir una carga correcta mientras el dashboard conserva una
dirección equivocada. No hace falta recargar los CSV para corregir esa dirección.

**Terminal 2 — cliente que ejecutará el flujo:**

```powershell
$env:PREFECT_HOME = Join-Path (Get-Location) 'local\prefect'
New-Item -ItemType Directory -Path $env:PREFECT_HOME -Force | Out-Null
$env:PREFECT_API_URL = 'http://127.0.0.1:4201/api'
```

`PREFECT_API_URL` indica dónde registrar tareas, estados y errores. Configurala
en la terminal que va a cargar los datos; estas variables duran esa sesión.
Los archivos `.env` de conexión no exportan esa variable para Prefect.

Si el equipo ya dispone de una API compartida, utilizá su URL real en la
terminal 2 y su autenticación privada; no necesitás iniciar otro servidor.
En otra PC, `127.0.0.1` apunta a esa otra PC, no a la máquina que aloja la API.

Sin una API configurada, el SDK puede iniciar un servidor temporal.
Para seguir esta guía y conservar un dashboard conocido, usá la API explícita.
Los ayudantes 07/08 la exigen. No se requieren Cloud, Docker, deployments ni
workers para ejecutar este flujo local. La SQLite de Prefect guarda metadatos
de orquestación; los datos de negocio se guardan en PostgreSQL.

## 6. Ejecutar la carga de los CSV

Con PostgreSQL preparado, `.env` correcto y la terminal 2 configurada:

```powershell
.\run.ps1
```

Es el acceso directo al siguiente comando; **ejecutá uno de los dos**:

```powershell
.\.venv\Scripts\python.exe scripts/staging_flow.py
```

El flujo **Chinook Staging ETL** ejecuta tres tareas secuenciales:

1. **Extraer CSV:** lee los archivos, comprueba manifiesto, encabezados,
   cantidades, relaciones y controles de facturas/Track.
2. **Cargar Staging:** conecta con el cargador, comprueba la base y estructura,
   obtiene un bloqueo para evitar recargas simultáneas y hace una carga completa
   mediante `DELETE + INSERT`. Verifica campos, ordinales, hashes y totales
   antes de confirmar la transacción.
3. **Validar Staging:** abre otra conexión de solo lectura, vuelve a comparar
   los datos y guarda el informe en `evidence/postgresql/run-<UUID>.json`.

El flujo puede crear las tablas si el esquema está vacío, **pero no crea la
base ni las cuentas**, y exige la marca del proyecto. Por eso la preparación
anterior es necesaria antes de la primera ejecución.

Con estas fuentes, el resultado esperado es `Completed` y **15.607 filas
fuente**, más 11 filas de metadatos en `etl_source_file`. Los controles de ventas
esperan 412 facturas, 2.240 detalles y un total de 2.328,60.
Las recargas reemplazan la fotografía completa; no duplican los registros ni
eliminan las tablas.

### Cómo interpretar la salida de la carga

Prefect asigna un nombre automático a cada ejecución, por ejemplo
`adamant-porcupine`. El enlace `/runs/flow-run/<UUID>` abre esa ejecución
concreta en el dashboard. Los nombres, identificadores y horas varían.

| Mensaje | Qué significa |
| --- | --- |
| `Beginning flow run` | Se inició una ejecución del flujo; todavía no demuestra que terminó. |
| `VALIDACIÓN PREVIA AL DATA WAREHOUSE` | Se revisan facturas y detalles de los CSV dentro de la extracción de Staging. Este mensaje no ejecuta ni carga el DW. |
| `Errores encontrados: 0` | Ese control de ventas no encontró inconsistencias. Aún faltan la carga y las demás validaciones. |
| `11 CSV verificados` y `3503 tracks validados` | La extracción terminó sus comprobaciones sobre las fuentes. |
| `registros insertados, pendientes de validacion` | Las filas se insertaron dentro de una transacción que todavía debe validarse y confirmarse. No es un error. |
| `COMMIT: 15607 registros validados dentro de la transaccion de carga` | La carga confirmó los cambios después de su validación interna. |
| Una tarea termina en `Completed()` | Esa tarea terminó; todavía pueden faltar otras tareas del flujo. |
| El **flujo completo** termina en `Completed()` | Terminaron la extracción, carga y auditoría final de esa ejecución. |

Para una carga normal, revisá el estado final del flujo, no solamente las primeras
líneas de inserción. El informe `evidence/postgresql/run-<UUID>.json` incluye
`mode: "full-refresh"`, `load_committed: true`, `total_rows: 15607` y los
controles de las 11 fuentes cuando la carga y auditoría terminaron correctamente.
El estado definitivo de la ejecución se consulta en Prefect.

Si falla la carga o su validación dentro de la transacción, se revierte esa
carga. Si falla la tercera tarea **después del COMMIT**, los datos ya confirmados
permanecen; el error lo indica y corresponde auditarlos.

Si preferís seguir la numeración de la alternativa manual, el paso 07 invoca
este mismo flujo y comprueba antes que haya `.venv`, `.env` y una API configurada:

```powershell
& .\sql\manual\07_cargar_csv.ps1
```

## 7. Comprobar lo cargado y entregar el acceso al DW

Después de una carga completa, podés auditar sin volver a cargar:

```powershell
.\run.ps1 -ValidateOnly
.\.venv\Scripts\python.exe scripts/staging_contract.py --check --env-file .env.reader
```

El primer comando compara PostgreSQL con los CSV y genera un informe; no escribe
en las tablas, aunque sí guarda evidencia local y metadatos de Prefect.
El segundo abre la conexión del lector y comprueba fidelidad y permisos de
consulta sin permisos de escritura. Ambos necesitan los datos ya cargados:
**una base recién preparada con cero filas no supera una validación de contenido**.

El paso 08 agrupa esas dos comprobaciones:

```powershell
& .\sql\manual\08_validar_carga.ps1
```

Para el DW se comparte por un canal privado: host accesible desde su equipo,
puerto, base `chinook_staging`, esquema `public`, rol `chinook_stg_reader`
y su contraseña. También debe permitirse esa conexión en el servidor/red.
No copies `.env.admin` ni uses la contraseña del cargador para esa lectura.

El [contrato DW](docs/entrega-dw.md) detalla las tablas expuestas. El otro
repositorio debe preparar **su propia base DW** siguiendo sus instrucciones;
este repositorio no crea `chinook_dw`. No hace falta duplicar los CSV en el DW.

## Problemas frecuentes

| Síntoma | Qué revisar |
| --- | --- |
| No existe `.venv\Scripts\python.exe` o falta un módulo | Crear el entorno e instalar dependencias desde la raíz del repo. |
| Conexión rechazada o timeout | Servidor encendido, host y puerto reales; si es remoto, red y reglas de acceso. |
| Contraseña inválida | Usar la clave del rol correcto; las cuentas existentes no cambian su clave al repetir la preparación. |
| `database "chinook_staging" does not exist` | Completar la preparación automática o manual antes del ETL. |
| Base/rol homónimo sin marca o propietario esperado | Inspeccionar el objeto existente; no se adopta ni se borra automáticamente. |
| Tablas incompletas o con columnas distintas | Comparar con el DDL oficial; la carga no reconstruye un esquema parcial. |
| CSV o manifiesto modificado | Comprobar `profile_sources.py --check` y restaurar las fuentes oficiales si la modificación fue accidental. |
| API de Prefect no disponible | Mantener terminal 1 abierta y revisar URL/puerto en terminal 2. |
| Dashboard con `Unable to connect`, aunque la API responde | Revisar `/ui-settings`: `api_url` debe usar el puerto del servidor. Corregir el perfil con `config set` y reiniciar Prefect. |
| Error al ejecutar un `.ps1` por política local | Usar directamente el comando Python equivalente o revisar la política permitida en tu equipo. |
| `NativeCommandError` al redirigir logs en Windows PowerShell 5 | Prefect escribe mensajes INFO en stderr; revisar el código de salida y el error real. Los ayudantes 07/08 manejan ese caso. |

Una falla de permisos en el aprovisionador puede dejar roles o la base creados.
Revisá el resultado de `--inspect` y el error antes de continuar; una salida
parcial no demuestra que ya estén listas las tablas.

## Pruebas y documentación de la entrega

Las pruebas locales se pueden ejecutar sin una base de integración, pero los
casos que usan Prefect necesitan la API configurada o pueden iniciar un servidor
temporal. No son un requisito para ejecutar la primera carga:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas PostgreSQL se omiten por defecto. Su activación, esquemas temporales,
alcance y condiciones se explican en
[pruebas y validaciones](docs/pruebas-y-validaciones.md).
No deben confundirse con ejecutar el ETL sobre la base de trabajo.

Documentación complementaria:
[validación Track](docs/validacion-track.md),
[colaboración](docs/colaboracion.md),
[avance PostgreSQL](docs/avance-postgresql.md),
[evidencias](evidence/postgresql/README.md) e
[historia de la migración](docs/limpieza-repositorio.md).
Los reportes y conteos de pruebas guardados describen ejecuciones históricas;
no garantizan que una instalación nueva ya esté configurada.
