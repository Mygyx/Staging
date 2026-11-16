/*
PASO 01 - INSPECCIONAR LA INSTANCIA. Solo consulta y comprueba.

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
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d postgres -W -v ON_ERROR_STOP=1 -P pager=off -f 'D:\Staging\sql\manual\01_inspeccionar_instancia.sql'
if ($LASTEXITCODE -ne 0) { throw 'El paso SQL fallo; revisar el error antes de continuar.' }
# FIN_POWERSHELL

OPCION B - QUERY TOOL DE PGADMIN
Abrir Query Tool en la base postgres, de la MISMA instancia, como postgres.
Copiar el bloque SQL marcado, incluidos sus comentarios INICIO y FIN.
Ejecutar el bloque completo de una sola vez, sin quitar sus comprobaciones.
No copiar los delimitadores de esta cabecera ni el bloque PowerShell.

-- INICIO_SQL_PGADMIN
SELECT current_database() AS base_actual, current_user AS administrador,
       current_setting('server_version') AS version,
       inet_server_addr() AS direccion, inet_server_port() AS puerto;

SELECT datname AS base, pg_get_userbyid(datdba) AS propietario,
       shobj_description(oid, 'pg_database') AS marca
FROM pg_database WHERE NOT datistemplate ORDER BY datname;

SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       shobj_description(oid, 'pg_authid') AS marca
FROM pg_roles WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader');

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
-- FIN_SQL_PGADMIN

FIN DE LAS OPCIONES PARA COPIAR.
El contenido situado despues de esta cabecera es la ruta interna del archivo.
No pegar el archivo entero en Query Tool: los pasos manuales pueden usar ordenes
exclusivas de psql. En pgAdmin se utiliza solamente el bloque SQL indicado.
*/

-- Inicio de la ruta interna psql: la misma inspeccion SQL de la opcion B.
SELECT current_database() AS base_actual, current_user AS administrador,
       current_setting('server_version') AS version,
       inet_server_addr() AS direccion, inet_server_port() AS puerto;

SELECT datname AS base, pg_get_userbyid(datdba) AS propietario,
       shobj_description(oid, 'pg_database') AS marca
FROM pg_database WHERE NOT datistemplate ORDER BY datname;

SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       shobj_description(oid, 'pg_authid') AS marca
FROM pg_roles WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader');

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
