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
