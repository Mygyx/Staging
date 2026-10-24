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
