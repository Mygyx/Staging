# Contrato: PostgreSQL Staging -> PostgreSQL DW

Repo 1: Jeremy y compañero, **CSV -> Prefect -> chinook_staging**.
Repo 2: Brian y Miguel, **chinook_staging -> Prefect -> chinook_dw -> Excel**.
Las bases están en entornos independientes. Este repositorio no modifica Repo 2.

## Configuración que se debe compartir

Motor: PostgreSQL. Base: `chinook_staging`. Esquema: `public`.
El host, puerto y política SSL se acuerdan con el responsable del staging y se
configuran, no se deducen del servidor DW. El candidato local es 127.0.0.1:5433;
desde otra PC, 127.0.0.1 apunta a esa otra PC. No se ha probado acceso remoto a
la computadora de Brian o Miguel y esta migración no abre puertos ni modifica
pg_hba.conf, servicios o reglas del firewall.

Variables: `STG_HOST`, `STG_PORT`, `STG_DATABASE`, `STG_SCHEMA`, `STG_USER`,
`STG_PASSWORD`, `STG_SSLMODE`. El usuario lector propuesto es `chinook_stg_reader`.
Su clave se comparte por un canal privado, nunca dentro del contrato ni de Git.
Sus permisos son CONNECT a nuestra base, USAGE de public y SELECT de las once
fuentes. No debe tener INSERT, UPDATE, DELETE, TRUNCATE o CREATE en el esquema.

Desde otra computadora, `STG_HOST` debe identificar la PC que aloja Staging,
mediante su IP o nombre acordado. `STG_PORT` debe ser el puerto real de esa
instancia; 5433 es el valor local comprobado. La base sigue siendo
`chinook_staging`, el esquema `public` y la cuenta `chinook_stg_reader`.
El lector no utiliza la cuenta administrativa ni la del cargador. La contraseña
y la política SSL se acuerdan por un canal privado y se configuran en el entorno
del Repo 2. No se deben copiar contraseñas al contrato JSON.

La entrega remota sigue pendiente: el responsable debe autorizar acceso de red
limitado y Brian/Miguel deben ejecutar una lectura desde su propia computadora.
Un SELECT exitoso en la PC de Jeremy no demuestra esa conectividad.

## Alcance del verificador y TEMP

El contrato version 3 conserva las mismas once consultas y columnas fuente.
El reporte nuevo usa `source_tables_read_only` y `reader_permission_scope`.
Verifica SELECT y ausencia efectiva de INSERT, UPDATE, DELETE, TRUNCATE,
REFERENCES, TRIGGER y MAINTAIN en las once tablas. Comprueba tambien ausencia
de INSERT, UPDATE y REFERENCES concedidos a columnas individuales, y ausencia
de CREATE en la base/esquema, atributos administrativos del rol y SELECT sobre
el catalogo tecnico. No es una auditoria de cada objeto del servidor ni de
posibles cambios a otro rol.

TEMP puede permanecer heredado: permite objetos temporales de la sesion,
no modificar las fuentes de public. Se informa como `database_temp_privilege`;
el verificador no concede ni revoca permisos. Los reportes historicos conservan
su formato anterior y su alcance se debe interpretar segun aquella version.

## Fuentes y cantidades

| Tabla | Registros |
| --- | ---: |
| stg_album | 347 |
| stg_artist | 275 |
| stg_customer | 59 |
| stg_employee | 8 |
| stg_genre | 25 |
| stg_invoice | 412 |
| stg_invoice_line | 2240 |
| stg_media_type | 5 |
| stg_playlist | 18 |
| stg_playlist_track | 8715 |
| stg_track | 3503 |
| **Total** | **15607** |

La descripción reproducible de las columnas y once consultas está en
`contracts/staging_sources.json`. Solo devuelve las columnas originales del CSV,
en el mismo orden, con CamelCase exacto. Ordena por `CSV_ROW_NUMBER` sin incluir
esa columna técnica en el resultado. `etl_source_file` es auditoría interna.

## Valores y transformaciones

Todas las columnas fuente son TEXT. `"CustomerId"`, `"FirstName"`, `"TrackId"`,
etc., conservan mayúsculas/minúsculas mediante identificadores entre comillas.
Los vacíos son cadenas vacías `''`, no NULL. Se conservan espacios finales,
Unicode, ceros iniciales, fechas textuales y precios como `0.99`.

**No basta con cambiar read_csv por read_sql.** Pandas dejará de aplicar la
inferencia que antes hacía al CSV: el equipo DW debe convertir identificadores,
fechas, cantidades e importes en sus transformaciones, e interpretar `''` como
faltante cuando corresponda. Esa limpieza no se aplica a las tablas staging.
No deben utilizarse floats para comprobar importes exactos.

Controles: 2240 líneas de factura, suma `UnitPrice * Quantity` de 2328.60,
y suma `Invoice.Total` de 2328.60. La granularidad de ventas del DW y sus propias
validaciones se deben comprobar en Repo 2; estos controles no verifican Excel.

## Lectura consistente con Pandas y SQLAlchemy

Copiar el contrato JSON al Repo 2. En su propio entorno requieren pandas,
SQLAlchemy y psycopg 3. La clave proviene del entorno, no se incluye en la URL:

```python
import json
import os
import pandas as pd
from sqlalchemy import create_engine, text

with open("contracts/staging_sources.json", encoding="utf-8") as file:
    contract = json.load(file)

engine = create_engine("postgresql+psycopg://", connect_args={
    "host": os.environ["STG_HOST"],
    "port": int(os.environ["STG_PORT"]),
    "dbname": os.environ["STG_DATABASE"],
    "user": os.environ["STG_USER"],
    "password": os.environ["STG_PASSWORD"],
    "sslmode": os.environ.get("STG_SSLMODE", "prefer"),
})
frames = {}
with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
    with connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        for source in contract["sources"]:
            frames[source["source"]] = pd.read_sql_query(
                text(source["query"]), connection, coerce_float=False)
```

Es esencial usar **la misma conexión y transacción** para las once consultas.
Once conexiones separadas pueden mezclar fotografías de recargas diferentes.
El DW se carga después usando su propia conexión, credenciales y transacción.

Ejemplo de consulta fuente sin columna técnica:

```sql
SELECT "InvoiceLineId", "InvoiceId", "TrackId", "UnitPrice", "Quantity"
FROM public.stg_invoice_line
ORDER BY "CSV_ROW_NUMBER";
```

Para comprobar desde un clon de Repo 1 el lector y la fidelidad frente a CSV:
`python scripts/staging_contract.py --check --env-file .env.reader`.
El programa también rechaza cuentas con permisos de escritura. Un resultado
obtenido en la PC del servidor no se presenta como prueba desde otra PC.
