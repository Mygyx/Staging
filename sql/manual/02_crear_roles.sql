/*
PASO 02 - CREAR LAS CUENTAS CARGADORA Y LECTORA. No crea la base.

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
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d postgres -W -v ON_ERROR_STOP=1 -P pager=off -f 'D:\Staging\sql\manual\02_crear_roles.sql'
if ($LASTEXITCODE -ne 0) { throw 'El paso SQL fallo; revisar el error antes de continuar.' }
# FIN_POWERSHELL

OPCION B - QUERY TOOL DE PGADMIN
Abrir Query Tool en la base postgres, de la MISMA instancia, como postgres.
Copiar el bloque SQL marcado, incluidos sus comentarios INICIO y FIN.
En la COPIA de pgAdmin, sustituir solo los valores asignados a clave_cargador
y clave_lector; deben coincidir con .env y .env.reader. No cambiar el texto
REEMPLAZAR... de las comprobaciones IF. Si una clave contiene una comilla
simple, escribirla duplicada dentro del literal SQL: por ejemplo, ab''cd.
Las cuentas que ya pertenecen al proyecto conservan su clave.
No guardar las claves reales en este archivo del repositorio.
La opcion PowerShell pide las nuevas claves de forma interactiva con psql;
el Query Tool usa los dos valores escritos en su editor.
No copiar los delimitadores de esta cabecera ni el bloque PowerShell.

-- INICIO_SQL_PGADMIN
BEGIN;

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

SET LOCAL password_encryption = 'scram-sha-256';
DO $crear_roles$
DECLARE
    -- Reemplazar estos valores SOLO en la copia del editor de pgAdmin.
    clave_cargador text := 'REEMPLAZAR_CLAVE_CARGADOR';
    clave_lector text := 'REEMPLAZAR_CLAVE_LECTOR';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chinook_stg_loader') THEN
        IF clave_cargador = 'REEMPLAZAR_CLAVE_CARGADOR' OR btrim(clave_cargador) = '' THEN
            RAISE EXCEPTION 'Indicar la clave del cargador en clave_cargador antes de ejecutar';
        END IF;
        CREATE ROLE chinook_stg_loader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
        COMMENT ON ROLE chinook_stg_loader IS 'chinook_staging_etl:postgres:v1';
        EXECUTE format('ALTER ROLE chinook_stg_loader PASSWORD %L', clave_cargador);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chinook_stg_reader') THEN
        IF clave_lector = 'REEMPLAZAR_CLAVE_LECTOR' OR btrim(clave_lector) = '' THEN
            RAISE EXCEPTION 'Indicar la clave del lector en clave_lector antes de ejecutar';
        END IF;
        CREATE ROLE chinook_stg_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
        COMMENT ON ROLE chinook_stg_reader IS 'chinook_staging_etl:postgres:v1';
        EXECUTE format('ALTER ROLE chinook_stg_reader PASSWORD %L', clave_lector);
    END IF;
END
$crear_roles$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_authid
               WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader')
               AND rolpassword IS NULL) THEN
        RAISE EXCEPTION 'Falta una contrasena: no se confirman cuentas sin clave';
    END IF;
END
$$;
ALTER ROLE chinook_stg_loader LOGIN;
ALTER ROLE chinook_stg_reader LOGIN;
COMMIT;
-- FIN_SQL_PGADMIN

FIN DE LAS OPCIONES PARA COPIAR.
El contenido situado despues de esta cabecera es la ruta interna del archivo.
No pegar el archivo entero en Query Tool: los pasos manuales pueden usar ordenes
exclusivas de psql. En pgAdmin se utiliza solamente el bloque SQL indicado.
*/

-- psql pide las claves nuevas sin mostrarlas ni guardarlas en este archivo.
-- Las claves elegidas deben coincidir con .env y .env.reader.
\set ON_ERROR_STOP on
\ir 01_inspeccionar_instancia.sql

SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chinook_stg_loader') AS loader_existe,
       EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chinook_stg_reader') AS reader_existe
\gset

BEGIN;
SET LOCAL password_encryption = 'scram-sha-256';

\if :loader_existe
\echo 'El cargador ya pertenece al proyecto: se conserva su clave.'
\else
CREATE ROLE chinook_stg_loader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
COMMENT ON ROLE chinook_stg_loader IS 'chinook_staging_etl:postgres:v1';
\password chinook_stg_loader
\endif

\if :reader_existe
\echo 'El lector ya pertenece al proyecto: se conserva su clave.'
\else
CREATE ROLE chinook_stg_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
COMMENT ON ROLE chinook_stg_reader IS 'chinook_staging_etl:postgres:v1';
\password chinook_stg_reader
\endif

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_authid
               WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader')
               AND rolpassword IS NULL) THEN
        RAISE EXCEPTION 'Falta una contrasena: no se confirman cuentas sin clave';
    END IF;
END
$$;
ALTER ROLE chinook_stg_loader LOGIN;
ALTER ROLE chinook_stg_reader LOGIN;
COMMIT;
