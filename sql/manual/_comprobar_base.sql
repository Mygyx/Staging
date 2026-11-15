-- Comprobacion compartida de los pasos 04-06. No prepara ni adopta objetos.
\set ON_ERROR_STOP on
\encoding UTF8
DO $$
BEGIN
    IF current_database() <> 'chinook_staging' THEN
        RAISE EXCEPTION 'Conectarse a chinook_staging antes de continuar';
    END IF;
    IF current_setting('server_version_num')::integer / 10000 <> 17 OR
       current_setting('server_encoding') <> 'UTF8' THEN
        RAISE EXCEPTION 'Se requiere PostgreSQL 17 con UTF8';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_database WHERE lower(datname) IN ('chinook_dw', 'chinook_datawarehouse')) THEN
        RAISE EXCEPTION 'La instancia contiene el DW y no cumple la separacion acordada';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = current_database()
        AND pg_get_userbyid(datdba) = 'chinook_stg_loader'
        AND shobj_description(oid, 'pg_database') = 'chinook_staging_etl:postgres:v1'
    ) THEN
        RAISE EXCEPTION 'Propietario o marca de base inesperados; no se continua';
    END IF;
    IF (SELECT count(*) FROM pg_roles WHERE rolname IN ('chinook_stg_loader', 'chinook_stg_reader')) <> 2
       OR EXISTS (
        SELECT 1 FROM pg_roles r WHERE r.rolname IN ('chinook_stg_loader', 'chinook_stg_reader')
        AND (shobj_description(r.oid, 'pg_authid') IS DISTINCT FROM 'chinook_staging_etl:postgres:v1'
             OR NOT r.rolcanlogin OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
             OR r.rolreplication OR r.rolbypassrls
             OR EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid))
    ) THEN
        RAISE EXCEPTION 'Roles ausentes, ajenos o privilegiados; revisar el paso 02';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'public') THEN
        RAISE EXCEPTION 'Falta el esquema public';
    END IF;
END
$$;
