/*
PASO 06 - VERIFICAR TABLAS Y PERMISOS. No carga ni modifica los datos.

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
& 'D:\PostgreSQL\17\bin\psql.exe' -X -h 127.0.0.1 -p 5433 -U postgres -d chinook_staging -W -v ON_ERROR_STOP=1 -P pager=off -f 'D:\Staging\sql\manual\06_verificar_preparacion.sql'
if ($LASTEXITCODE -ne 0) { throw 'El paso SQL fallo; revisar el error antes de continuar.' }
# FIN_POWERSHELL

OPCION B - QUERY TOOL DE PGADMIN
Abrir Query Tool en la base chinook_staging, de la MISMA instancia, como postgres.
Copiar el bloque SQL marcado, incluidos sus comentarios INICIO y FIN.
Ejecutar el bloque completo, desde INICIO_SQL_PGADMIN hasta FIN_SQL_PGADMIN.
Consultar Data Output para el resultado y Messages para los conteos por tabla.
Con tablas recien creadas se esperan 0 filas. Esta revision no carga los CSV
ni reemplaza la auditoria de contenido que realiza Python/Prefect.
No copiar los delimitadores de esta cabecera ni el bloque PowerShell.

-- INICIO_SQL_PGADMIN
BEGIN READ ONLY;

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
DECLARE
    esperadas text[] := ARRAY['stg_album','stg_artist','stg_customer','stg_employee',
        'stg_genre','stg_invoice','stg_invoice_line','stg_media_type',
        'stg_playlist','stg_playlist_track','stg_track','etl_source_file'];
    tabla text;
    clave text[];
    clave_esperada text[];
    privilegio text;
BEGIN
    IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')) <> 12
       OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
        AND (c.relkind <> 'r' OR NOT (c.relname = ANY(esperadas))
             OR pg_get_userbyid(c.relowner) <> 'chinook_stg_loader')
    ) THEN
        RAISE EXCEPTION 'Se esperan las 12 tablas oficiales, propiedad del cargador, sin objetos adicionales en public';
    END IF;
    FOREACH tabla IN ARRAY esperadas LOOP
        SELECT array_agg(k.column_name::text ORDER BY k.ordinal_position) INTO clave
        FROM information_schema.table_constraints t
        JOIN information_schema.key_column_usage k
          ON k.constraint_catalog=t.constraint_catalog AND k.constraint_schema=t.constraint_schema
         AND k.constraint_name=t.constraint_name AND k.table_name=t.table_name
        WHERE t.constraint_type='PRIMARY KEY' AND t.table_schema='public' AND t.table_name=tabla;
        clave_esperada := CASE WHEN tabla='etl_source_file'
            THEN ARRAY['source_file']::text[] ELSE ARRAY['CSV_ROW_NUMBER']::text[] END;
        IF clave IS DISTINCT FROM clave_esperada THEN
            RAISE EXCEPTION 'Clave primaria inesperada en %', tabla;
        END IF;
        IF tabla <> 'etl_source_file' THEN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=tabla
                       AND ((column_name='CSV_ROW_NUMBER' AND (data_type<>'integer' OR is_nullable<>'NO'))
                            OR (column_name<>'CSV_ROW_NUMBER' AND data_type<>'text'))) THEN
                RAISE EXCEPTION 'Tipos de columna inesperados en %', tabla;
            END IF;
            IF NOT has_table_privilege('chinook_stg_reader', format('public.%I',tabla),'SELECT') THEN
                RAISE EXCEPTION 'El lector no puede consultar %', tabla;
            END IF;
            FOREACH privilegio IN ARRAY ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
                IF has_table_privilege('chinook_stg_reader',format('public.%I',tabla),privilegio) THEN
                    RAISE EXCEPTION 'El lector tiene permiso % en %', privilegio, tabla;
                END IF;
            END LOOP;
            FOREACH privilegio IN ARRAY ARRAY['INSERT','UPDATE','REFERENCES'] LOOP
                IF has_any_column_privilege('chinook_stg_reader',format('public.%I',tabla),privilegio) THEN
                    RAISE EXCEPTION 'El lector tiene permiso % sobre una columna de %', privilegio, tabla;
                END IF;
            END LOOP;
        END IF;
    END LOOP;
    IF NOT has_database_privilege('chinook_stg_reader','chinook_staging','CONNECT')
       OR NOT has_schema_privilege('chinook_stg_reader','public','USAGE')
       OR has_database_privilege('chinook_stg_reader','chinook_staging','CREATE')
       OR has_schema_privilege('chinook_stg_reader','public','CREATE')
       OR has_table_privilege('chinook_stg_reader','public.etl_source_file','SELECT') THEN
        RAISE EXCEPTION 'Permisos de conexion, esquema o catalogo tecnico inesperados para el lector';
    END IF;
END
$$;

SELECT table_name, ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns WHERE table_schema='public'
ORDER BY table_name, ordinal_position;

SET ROLE chinook_stg_loader;
DO $$
DECLARE
    tabla text;
    filas bigint;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['stg_album','stg_artist','stg_customer','stg_employee',
        'stg_genre','stg_invoice','stg_invoice_line','stg_media_type',
        'stg_playlist','stg_playlist_track','stg_track','etl_source_file'] LOOP
        EXECUTE format('SELECT count(*) FROM public.%I',tabla) INTO filas;
        RAISE NOTICE '%: % filas',tabla,filas;
    END LOOP;
END
$$;
RESET ROLE;
COMMIT;

SELECT 'Preparacion SQL comprobada; las tablas nuevas deben tener 0 filas. La carga se inicia con Python/Prefect.' AS resultado;
-- FIN_SQL_PGADMIN

FIN DE LAS OPCIONES PARA COPIAR.
El contenido situado despues de esta cabecera es la ruta interna del archivo.
No pegar el archivo entero en Query Tool: los pasos manuales pueden usar ordenes
exclusivas de psql. En pgAdmin se utiliza solamente el bloque SQL indicado.
*/

-- Revision SQL de preparacion. No carga CSV ni reemplaza la auditoria de contenido del ETL.
\set ON_ERROR_STOP on
\ir _comprobar_base.sql
BEGIN READ ONLY;
DO $$
DECLARE
    esperadas text[] := ARRAY['stg_album','stg_artist','stg_customer','stg_employee',
        'stg_genre','stg_invoice','stg_invoice_line','stg_media_type',
        'stg_playlist','stg_playlist_track','stg_track','etl_source_file'];
    tabla text;
    clave text[];
    clave_esperada text[];
    privilegio text;
BEGIN
    IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')) <> 12
       OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
        AND (c.relkind <> 'r' OR NOT (c.relname = ANY(esperadas))
             OR pg_get_userbyid(c.relowner) <> 'chinook_stg_loader')
    ) THEN
        RAISE EXCEPTION 'Se esperan las 12 tablas oficiales, propiedad del cargador, sin objetos adicionales en public';
    END IF;
    FOREACH tabla IN ARRAY esperadas LOOP
        SELECT array_agg(k.column_name::text ORDER BY k.ordinal_position) INTO clave
        FROM information_schema.table_constraints t
        JOIN information_schema.key_column_usage k
          ON k.constraint_catalog=t.constraint_catalog AND k.constraint_schema=t.constraint_schema
         AND k.constraint_name=t.constraint_name AND k.table_name=t.table_name
        WHERE t.constraint_type='PRIMARY KEY' AND t.table_schema='public' AND t.table_name=tabla;
        clave_esperada := CASE WHEN tabla='etl_source_file'
            THEN ARRAY['source_file']::text[] ELSE ARRAY['CSV_ROW_NUMBER']::text[] END;
        IF clave IS DISTINCT FROM clave_esperada THEN
            RAISE EXCEPTION 'Clave primaria inesperada en %', tabla;
        END IF;
        IF tabla <> 'etl_source_file' THEN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=tabla
                       AND ((column_name='CSV_ROW_NUMBER' AND (data_type<>'integer' OR is_nullable<>'NO'))
                            OR (column_name<>'CSV_ROW_NUMBER' AND data_type<>'text'))) THEN
                RAISE EXCEPTION 'Tipos de columna inesperados en %', tabla;
            END IF;
            IF NOT has_table_privilege('chinook_stg_reader', format('public.%I',tabla),'SELECT') THEN
                RAISE EXCEPTION 'El lector no puede consultar %', tabla;
            END IF;
            FOREACH privilegio IN ARRAY ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
                IF has_table_privilege('chinook_stg_reader',format('public.%I',tabla),privilegio) THEN
                    RAISE EXCEPTION 'El lector tiene permiso % en %', privilegio, tabla;
                END IF;
            END LOOP;
            FOREACH privilegio IN ARRAY ARRAY['INSERT','UPDATE','REFERENCES'] LOOP
                IF has_any_column_privilege('chinook_stg_reader',format('public.%I',tabla),privilegio) THEN
                    RAISE EXCEPTION 'El lector tiene permiso % sobre una columna de %', privilegio, tabla;
                END IF;
            END LOOP;
        END IF;
    END LOOP;
    IF NOT has_database_privilege('chinook_stg_reader','chinook_staging','CONNECT')
       OR NOT has_schema_privilege('chinook_stg_reader','public','USAGE')
       OR has_database_privilege('chinook_stg_reader','chinook_staging','CREATE')
       OR has_schema_privilege('chinook_stg_reader','public','CREATE')
       OR has_table_privilege('chinook_stg_reader','public.etl_source_file','SELECT') THEN
        RAISE EXCEPTION 'Permisos de conexion, esquema o catalogo tecnico inesperados para el lector';
    END IF;
END
$$;

SELECT table_name, ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns WHERE table_schema='public'
ORDER BY table_name, ordinal_position;

SET ROLE chinook_stg_loader;
DO $$
DECLARE
    tabla text;
    filas bigint;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['stg_album','stg_artist','stg_customer','stg_employee',
        'stg_genre','stg_invoice','stg_invoice_line','stg_media_type',
        'stg_playlist','stg_playlist_track','stg_track','etl_source_file'] LOOP
        EXECUTE format('SELECT count(*) FROM public.%I',tabla) INTO filas;
        RAISE NOTICE '%: % filas',tabla,filas;
    END LOOP;
END
$$;
RESET ROLE;
COMMIT;
\echo 'Preparacion SQL comprobada. Con tablas recien creadas se esperan 0 filas; los CSV se cargan en el paso 07.'
