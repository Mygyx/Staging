-- Reutiliza los mismos permisos que aplica el aprovisionador Python.
\set ON_ERROR_STOP on
\ir _comprobar_base.sql
BEGIN;
SET ROLE chinook_stg_loader;
\ir ../provision_access.sql
RESET ROLE;
COMMIT;
