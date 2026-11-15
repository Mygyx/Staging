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
