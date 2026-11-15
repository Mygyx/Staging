-- Ejecutar con psql, conectado como superusuario a la base de mantenimiento postgres.
-- Este archivo solo consulta y comprueba; no crea ni modifica objetos.
\set ON_ERROR_STOP on
\encoding UTF8

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
