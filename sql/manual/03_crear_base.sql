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
