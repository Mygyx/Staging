-- Generado por scripts/generate_sql.py. No editar manualmente.
WHENEVER OSERROR EXIT FAILURE ROLLBACK
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK
SET DEFINE OFF
SET ESCAPE OFF
SET SQLCASE MIXED
SET SQLBLANKLINES ON
SET AUTOCOMMIT OFF
SET SERVEROUTPUT ON
SET FEEDBACK OFF
SET VERIFY OFF
SET ECHO OFF
PROMPT Creando tablas de staging...
@@01_create_tables.sql
@@02_load_data.sql
@@03_validate_data.sql
COMMIT;
PROMPT Carga confirmada despues de validar todos los registros.
@@04_summary.sql
