# Inventario y calidad de las fuentes

Generado por `python scripts/profile_sources.py`. No se modifica ningun CSV.

| CSV | Tabla | Registros | Campos | Vacíos | Filas duplicadas |
| --- | --- | ---: | ---: | ---: | ---: |
| Album.csv | STG_ALBUM | 347 | 3 | 0 | 0 |
| Artist.csv | STG_ARTIST | 275 | 2 | 0 | 0 |
| Customer.csv | STG_CUSTOMER | 59 | 13 | 130 | 0 |
| Employee.csv | STG_EMPLOYEE | 8 | 15 | 1 | 0 |
| Genre.csv | STG_GENRE | 25 | 2 | 0 | 0 |
| Invoice.csv | STG_INVOICE | 412 | 9 | 230 | 0 |
| InvoiceLine.csv | STG_INVOICELINE | 2240 | 5 | 0 | 0 |
| MediaType.csv | STG_MEDIATYPE | 5 | 2 | 0 | 0 |
| Playlist.csv | STG_PLAYLIST | 18 | 2 | 0 | 0 |
| PlaylistTrack.csv | STG_PLAYLISTTRACK | 8715 | 2 | 0 | 0 |
| Track.csv | STG_TRACK | 3503 | 9 | 978 | 0 |

Total: **15607 registros**.

Los vacíos y duplicados se conservan. No se aplican recortes, normalización
de Unicode, conversión numérica ni conversión de fechas. El manifiesto
`data/manifest.json` detalla SHA-256 del archivo completo, tamaños por
columna, vacíos, espacios en extremos y valores distintos.

Las relaciones se revisan solo para informar calidad; no generan FK
que puedan rechazar registros originales.

| Campo hijo | Campo padre | Registros huérfanos |
| --- | --- | ---: |
| Album.ArtistId | Artist.ArtistId | 0 |
| Customer.SupportRepId | Employee.EmployeeId | 0 |
| Employee.ReportsTo | Employee.EmployeeId | 0 |
| Invoice.CustomerId | Customer.CustomerId | 0 |
| InvoiceLine.InvoiceId | Invoice.InvoiceId | 0 |
| InvoiceLine.TrackId | Track.TrackId | 0 |
| PlaylistTrack.PlaylistId | Playlist.PlaylistId | 0 |
| PlaylistTrack.TrackId | Track.TrackId | 0 |
| Track.AlbumId | Album.AlbumId | 0 |
| Track.MediaTypeId | MediaType.MediaTypeId | 0 |
| Track.GenreId | Genre.GenreId | 0 |
