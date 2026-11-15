-- Reutiliza el DDL oficial. Las tablas se crean con el cargador como propietario.
\set ON_ERROR_STOP on
\ir _comprobar_base.sql
BEGIN;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    ) THEN
        RAISE EXCEPTION 'public ya tiene objetos; no se recrean ni borran. Revisar 06 y omitir 04 solo si la estructura esta completa';
    END IF;
END
$$;
SET ROLE chinook_stg_loader;
\ir ../create_staging.sql
RESET ROLE;
COMMIT;
