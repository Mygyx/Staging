/*
PASO 04 - CREAR LAS 12 TABLAS OFICIALES. Solo inicializacion.

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
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d chinook_staging -W -v ON_ERROR_STOP=1 -P pager=off -f 'D:\Staging\sql\manual\04_crear_tablas.sql'
if ($LASTEXITCODE -ne 0) { throw 'El paso SQL fallo; revisar el error antes de continuar.' }
# FIN_POWERSHELL

OPCION B - QUERY TOOL DE PGADMIN
Abrir Query Tool en la base chinook_staging, de la MISMA instancia, como postgres.
Copiar el bloque SQL marcado, incluidos sus comentarios INICIO y FIN.
Ejecutar el bloque completo, desde INICIO_SQL_PGADMIN hasta FIN_SQL_PGADMIN.
Incluye las comprobaciones y el DDL de ../create_staging.sql, sin usar \ir.
Se detiene si public ya tiene objetos: no borrar tablas para volver a correrlo.
Si la preparacion ya termino, pasar a 06 o a la carga mediante Prefect.
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

-- PostgreSQL 17+. La carga no recrea tablas existentes.
-- CSV_ROW_NUMBER es tecnico; todas las columnas fuente conservan TEXT y CamelCase.
CREATE TABLE public.stg_album (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "AlbumId" TEXT, "Title" TEXT, "ArtistId" TEXT
);
CREATE TABLE public.stg_artist (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "ArtistId" TEXT, "Name" TEXT
);
CREATE TABLE public.stg_customer (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "CustomerId" TEXT, "FirstName" TEXT, "LastName" TEXT, "Company" TEXT,
    "Address" TEXT, "City" TEXT, "State" TEXT, "Country" TEXT, "PostalCode" TEXT,
    "Phone" TEXT, "Fax" TEXT, "Email" TEXT, "SupportRepId" TEXT
);
CREATE TABLE public.stg_employee (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "EmployeeId" TEXT, "LastName" TEXT, "FirstName" TEXT, "Title" TEXT,
    "ReportsTo" TEXT, "BirthDate" TEXT, "HireDate" TEXT, "Address" TEXT,
    "City" TEXT, "State" TEXT, "Country" TEXT, "PostalCode" TEXT,
    "Phone" TEXT, "Fax" TEXT, "Email" TEXT
);
CREATE TABLE public.stg_genre (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "GenreId" TEXT, "Name" TEXT
);
CREATE TABLE public.stg_invoice (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "InvoiceId" TEXT, "CustomerId" TEXT, "InvoiceDate" TEXT,
    "BillingAddress" TEXT, "BillingCity" TEXT, "BillingState" TEXT,
    "BillingCountry" TEXT, "BillingPostalCode" TEXT, "Total" TEXT
);
CREATE TABLE public.stg_invoice_line (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "InvoiceLineId" TEXT, "InvoiceId" TEXT, "TrackId" TEXT,
    "UnitPrice" TEXT, "Quantity" TEXT
);
CREATE TABLE public.stg_media_type (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "MediaTypeId" TEXT, "Name" TEXT
);
CREATE TABLE public.stg_playlist (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "PlaylistId" TEXT, "Name" TEXT
);
CREATE TABLE public.stg_playlist_track (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "PlaylistId" TEXT, "TrackId" TEXT
);
CREATE TABLE public.stg_track (
    "CSV_ROW_NUMBER" INTEGER PRIMARY KEY,
    "TrackId" TEXT, "Name" TEXT, "AlbumId" TEXT, "MediaTypeId" TEXT,
    "GenreId" TEXT, "Composer" TEXT, "Milliseconds" TEXT, "Bytes" TEXT,
    "UnitPrice" TEXT
);
-- Metadatos: no constituye una fuente adicional ni se entrega al lector DW.
CREATE TABLE public.etl_source_file (
    source_file TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL,
    expected_rows INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    file_bytes BIGINT NOT NULL
);

RESET ROLE;
COMMIT;
-- FIN_SQL_PGADMIN

FIN DE LAS OPCIONES PARA COPIAR.
El contenido situado despues de esta cabecera es la ruta interna del archivo.
No pegar el archivo entero en Query Tool: los pasos manuales pueden usar ordenes
exclusivas de psql. En pgAdmin se utiliza solamente el bloque SQL indicado.
*/

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
