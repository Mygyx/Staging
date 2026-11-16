/*
PASO 03 - CREAR chinook_staging. Todavia no crea tablas ni carga CSV.

Elegir UNA opcion. Ambas realizan este paso; no ejecutar las dos seguidas.
Requisitos: PostgreSQL 17 encendido; superusuario de preparacion, por ejemplo postgres.
Este ejemplo usa 127.0.0.1:5433, D:\PostgreSQL\17 y D:\Staging.
Ajustar rutas, host y puerto si la instalacion es distinta.

OPCION A - POWERSHELL
Copiar desde # INICIO_POWERSHELL hasta # FIN_POWERSHELL, incluidos ambos.
La terminal ejecuta psql.exe; -W pide la clave del administrador postgres.
El archivo se procesa completo con psql, que ignora esta cabecera comentada.

# INICIO_POWERSHELL
$env:PGCLIENTENCODING = 'UTF8'
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d postgres -W -v ON_ERROR_STOP=1 -P pager=off -f 'D:\Staging\sql\manual\03_crear_base.sql'
if ($LASTEXITCODE -ne 0) { throw 'El paso SQL fallo; revisar el error antes de continuar.' }
# FIN_POWERSHELL

OPCION B - QUERY TOOL DE PGADMIN
Abrir Query Tool en la base postgres, de la MISMA instancia, como postgres.
Copiar el bloque SQL marcado, incluidos sus comentarios INICIO y FIN.
ESTE PASO TIENE TRES BLOQUES: ejecutarlos POR SEPARADO, nunca juntos.
1. Copiar INICIO_SQL_PGADMIN_1_COMPROBAR hasta FIN_SQL_PGADMIN_1_COMPROBAR.
   Si falla, detenerse. Si devuelve crear_base = false, la base ya fue
   reconocida: OMITIR los bloques 2 y 3 y abrir Query Tool en chinook_staging.
2. Solo si crear_base = true: activar Auto-commit y cerrar cualquier transaccion
   previa (ROLLBACK si quedo abierta). Seleccionar y ejecutar UNICAMENTE desde
   INICIO_SQL_PGADMIN_2_CREAR_BASE hasta FIN_SQL_PGADMIN_2_CREAR_BASE.
   CREATE DATABASE debe enviarse solo; no admite BEGIN/COMMIT ni DO.
3. Solo tras el exito del bloque 2: ejecutar desde INICIO_SQL_PGADMIN_3_MARCAR_BASE
   hasta FIN_SQL_PGADMIN_3_MARCAR_BASE para identificar la base recien creada.
   No usar este comentario para adoptar una base anterior o desconocida.
4. Refrescar Databases en pgAdmin y abrir OTRA Query Tool sobre chinook_staging
   para los pasos 04-06; no basta con cambiar el texto del editor.
Si se interrumpe entre 2 y 3, revisar el resultado antes de continuar.
No copiar los delimitadores de esta cabecera ni el bloque PowerShell.

-- INICIO_SQL_PGADMIN_1_COMPROBAR
DO $$
BEGIN
    IF current_database() <> 'postgres' THEN
        RAISE EXCEPTION 'Conectarse a postgres para inspeccionar y crear roles/base';
    END IF;
    IF current_setting('server_version_num')::integer / 10000 <> 17 THEN
        RAISE EXCEPTION 'Esta ruta de aprovisionamiento requiere PostgreSQL 17';
    END IF;
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
        RAISE EXCEPTION 'La ruta SQL manual requiere un superusuario autorizado, por ejemplo postgres';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_database WHERE lower(datname) IN ('chinook_dw', 'chinook_datawarehouse')) THEN
        RAISE EXCEPTION 'La instancia contiene el DW; Staging debe usar la instancia separada acordada';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'chinook_staging'
        AND (pg_get_userbyid(datdba) <> 'chinook_stg_loader' OR
             shobj_description(oid, 'pg_database') IS DISTINCT FROM 'chinook_staging_etl:postgres:v1')
    ) THEN
        RAISE EXCEPTION 'chinook_staging ya existe sin el propietario/marca esperados; no se adopta';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles r
        WHERE r.rolname IN ('chinook_stg_loader', 'chinook_stg_reader')
        AND (shobj_description(r.oid, 'pg_authid') IS DISTINCT FROM 'chinook_staging_etl:postgres:v1'
             OR NOT r.rolcanlogin OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
             OR r.rolreplication OR r.rolbypassrls
             OR EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid))
    ) THEN
        RAISE EXCEPTION 'Hay un rol homonimo ajeno o con privilegios inesperados; no se modifica';
    END IF;
END
$$;

DO $$
BEGIN
    IF (SELECT count(*) FROM pg_roles
        WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader')) <> 2 THEN
        RAISE EXCEPTION 'Ejecutar primero 02_crear_roles.sql';
    END IF;
END
$$;

SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'chinook_staging') AS crear_base;
-- FIN_SQL_PGADMIN_1_COMPROBAR

-- INICIO_SQL_PGADMIN_2_CREAR_BASE
CREATE DATABASE chinook_staging OWNER chinook_stg_loader
    TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';
-- FIN_SQL_PGADMIN_2_CREAR_BASE

-- INICIO_SQL_PGADMIN_3_MARCAR_BASE
COMMENT ON DATABASE chinook_staging IS 'chinook_staging_etl:postgres:v1';
-- FIN_SQL_PGADMIN_3_MARCAR_BASE

FIN DE LAS OPCIONES PARA COPIAR.
El contenido situado despues de esta cabecera es la ruta interna del archivo.
No pegar el archivo entero en Query Tool: los pasos manuales pueden usar ordenes
exclusivas de psql. En pgAdmin se utiliza solamente el bloque SQL indicado.
*/

-- Ejecutar en postgres, fuera de BEGIN/COMMIT: CREATE DATABASE no admite transaccion.
\set ON_ERROR_STOP on
\ir 01_inspeccionar_instancia.sql

DO $$
BEGIN
    IF (SELECT count(*) FROM pg_roles
        WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader')) <> 2 THEN
        RAISE EXCEPTION 'Ejecutar primero 02_crear_roles.sql';
    END IF;
END
$$;

SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'chinook_staging') AS crear_base
\gset
\if :crear_base
CREATE DATABASE chinook_staging OWNER chinook_stg_loader
    TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';
COMMENT ON DATABASE chinook_staging IS 'chinook_staging_etl:postgres:v1';
\else
\echo 'La base ya tiene propietario y marca del proyecto: se conserva.'
\endif

\echo 'Base preparada. Conectarse a chinook_staging antes del paso 04.'
