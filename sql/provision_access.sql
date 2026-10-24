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
