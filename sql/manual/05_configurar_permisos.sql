/*
PASO 05 - ASIGNAR PERMISOS. No crea base, tablas ni contrasenas.

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
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d chinook_staging -W -v ON_ERROR_STOP=1 -P pager=off -f 'D:\Staging\sql\manual\05_configurar_permisos.sql'
if ($LASTEXITCODE -ne 0) { throw 'El paso SQL fallo; revisar el error antes de continuar.' }
# FIN_POWERSHELL

OPCION B - QUERY TOOL DE PGADMIN
Abrir Query Tool en la base chinook_staging, de la MISMA instancia, como postgres.
Copiar el bloque SQL marcado, incluidos sus comentarios INICIO y FIN.
Ejecutar el bloque completo, desde INICIO_SQL_PGADMIN hasta FIN_SQL_PGADMIN.
Incluye las comprobaciones y los permisos de ../provision_access.sql, sin usar \ir.
El lector obtiene SELECT sobre las 11 fuentes; no escritura ni lectura del catalogo tecnico.
No copiar los delimitadores de esta cabecera ni el bloque PowerShell.

-- INICIO_SQL_PGADMIN
BEGIN;

-- Comprobacion compartida de los pasos 04-06. No prepara ni adopta objetos.
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

SET ROLE chinook_stg_loader;

-- Aplicar solo en nuestra base marcada, tras crear los dos roles y las tablas.
-- No crea contrasenas ni concede privilegios sobre otras bases.
DO $$
BEGIN
    IF current_database() <> 'chinook_staging' OR
       (SELECT shobj_description(oid, 'pg_database') FROM pg_database
        WHERE datname = current_database()) IS DISTINCT FROM 'chinook_staging_etl:postgres:v1' THEN
        RAISE EXCEPTION 'Base de proposito no autorizado; no se cambian permisos';
    END IF;
END
$$;
REVOKE CONNECT ON DATABASE chinook_staging FROM PUBLIC;
GRANT CONNECT ON DATABASE chinook_staging TO chinook_stg_loader, chinook_stg_reader;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM chinook_stg_reader;
GRANT USAGE ON SCHEMA public TO chinook_stg_reader;
REVOKE ALL PRIVILEGES ON TABLE
    public.stg_album, public.stg_artist, public.stg_customer, public.stg_employee,
    public.stg_genre, public.stg_invoice, public.stg_invoice_line,
    public.stg_media_type, public.stg_playlist, public.stg_playlist_track, public.stg_track,
    public.etl_source_file
FROM chinook_stg_reader;
GRANT SELECT ON TABLE
    public.stg_album, public.stg_artist, public.stg_customer, public.stg_employee,
    public.stg_genre, public.stg_invoice, public.stg_invoice_line,
    public.stg_media_type, public.stg_playlist, public.stg_playlist_track, public.stg_track
TO chinook_stg_reader;

RESET ROLE;
COMMIT;
-- FIN_SQL_PGADMIN

FIN DE LAS OPCIONES PARA COPIAR.
El contenido situado despues de esta cabecera es la ruta interna del archivo.
No pegar el archivo entero en Query Tool: los pasos manuales pueden usar ordenes
exclusivas de psql. En pgAdmin se utiliza solamente el bloque SQL indicado.
*/

-- Reutiliza los mismos permisos que aplica el aprovisionador Python.
\set ON_ERROR_STOP on
\ir _comprobar_base.sql
BEGIN;
SET ROLE chinook_stg_loader;
\ir ../provision_access.sql
RESET ROLE;
COMMIT;
