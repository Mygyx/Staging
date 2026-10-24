# Contrato de entrega: Staging -> Data Warehouse

Este repositorio es **chinook_staging_etl**, la entrega CSV -> Prefect -> Oracle
del equipo de staging. El otro equipo continúa en **chinook_datawarehouse** con
Staging -> Prefect -> transformaciones -> DW -> Excel.

## Destino Oracle

El servidor es la PC del responsable de staging, accesible por la red local.
`CHINOOK_STAGING` es un **esquema/usuario Oracle dentro de la PDB XEPDB1**. No es
una instancia nueva, una segunda máquina ni una PDB llamada chinook_staging.
En Oracle, cada usuario es propietario de un esquema con su mismo nombre.

| Dato | Valor actual |
| --- | --- |
| IPv4 de la PC del staging | `192.168.0.250` |
| Puerto Oracle | `1521/TCP` |
| Servicio/PDB | `XEPDB1` |
| Esquema de datos | `CHINOOK_STAGING` |
| Usuario lector para el DW | `CHINOOK_STG_READ` |
| DSN desde otra PC de la misma LAN | `192.168.0.250:1521/XEPDB1` |

La IP puede cambiar por DHCP. El responsable debe comprobar su IPv4 al compartir
la conexión. `localhost` en la PC del compañero apunta a la PC del compañero.
La PC del staging debe permanecer encendida, conectada a la LAN y con los
servicios de Oracle activos. Una red de invitados puede bloquear conexiones
entre equipos aunque ambos tengan Internet.

La contraseña se comparte por un canal privado. El responsable puede verla
localmente con `./show-dw-connection.ps1 -RevealPassword`; no se guarda en Git.

## Tablas acordadas

| Tabla | Registros |
| --- | ---: |
| `stg_album` | 347 |
| `stg_artist` | 275 |
| `stg_customer` | 59 |
| `stg_employee` | 8 |
| `stg_genre` | 25 |
| `stg_invoice` | 412 |
| `stg_invoice_line` | 2240 |
| `stg_media_type` | 5 |
| `stg_playlist` | 18 |
| `stg_playlist_track` | 8715 |
| `stg_track` | 3503 |
| **Total** | **15607** |

Los identificadores sin comillas son equivalentes en mayúsculas y minúsculas
en Oracle. Desde el lector se consulta, por ejemplo,
`CHINOOK_STAGING.stg_invoice_line`.

Hay exactamente 11 tablas fuente con prefijo `STG_`. `ETL_SOURCE_FILE` es una
tabla técnica de auditoría; el lector del DW no necesita acceso a ella.
`CSV_ROW_NUMBER` es una columna técnica; las consultas del contrato seleccionan
solo columnas del CSV y usan esta columna para conservar el orden.

Los valores de las columnas fuente son texto. Los vacíos del CSV son `NULL`.
El equipo del DW aplica las conversiones de tipos y las transformaciones después
de extraer estas tablas. Los controles de referencia para ventas son **2240
líneas** y **2328.60** de importe total; no prueban por sí solos el DW ni Excel.

## Columnas compatibles con el código existente

Oracle devuelve normalmente nombres de columna en mayúsculas para identificadores
sin comillas. El archivo `contracts/staging_sources.json` incluye las 11 consultas
con alias que mantienen exactamente los encabezados originales, como
`CustomerId`, `FirstName` y `InvoiceDate`.

Ejemplo de consulta:

```sql
SELECT CustomerId AS "CustomerId", FirstName AS "FirstName",
       LastName AS "LastName", Company AS "Company", Address AS "Address",
       City AS "City", State AS "State", Country AS "Country",
       PostalCode AS "PostalCode", Phone AS "Phone", Fax AS "Fax",
       Email AS "Email", SupportRepId AS "SupportRepId"
FROM CHINOOK_STAGING.stg_customer
ORDER BY CSV_ROW_NUMBER;
```

El compañero puede copiar `contracts/staging_sources.json` al repo DW y leer
con su instalación de Pandas, SQLAlchemy y python-oracledb:

```python
import json
import os
import pandas as pd
from sqlalchemy import create_engine, text

with open("contracts/staging_sources.json", encoding="utf-8") as file:
    contract = json.load(file)
queries = {source["source"]: source["query"] for source in contract["sources"]}

engine = create_engine("oracle+oracledb://", connect_args={
    "user": os.environ["STAGING_USER"],
    "password": os.environ["STAGING_PASSWORD"],
    "dsn": os.environ["STAGING_DSN"],
})
with engine.connect() as connection:
    customers = pd.read_sql_query(text(queries["Customer"]), connection,
                                  coerce_float=False)
```

## Comprobación desde la PC del compañero

Primero comprobar TCP:

```powershell
Test-NetConnection 192.168.0.250 -Port 1521
```

Después, con credenciales del lector en las variables `STAGING_USER`,
`STAGING_PASSWORD` y `STAGING_DSN`, ejecutar desde este repo:

```powershell
.\.venv\Scripts\python.exe scripts/staging_contract.py
```

El programa usa solo lecturas y comprueba las 11 cantidades, los nombres de
columnas y la igualdad entre los totales de líneas y de facturas con Decimal.
La prueba desde otra PC debe realizarla el equipo; una conexión desde el propio
servidor no demuestra que la red y el firewall del cliente permitan el acceso.

Estado verificado el 24 de octubre de 2026: el lector conecta usando la IP LAN
desde el servidor y la regla del firewall está activa, limitada a TCP/1521,
IP local `192.168.0.250`, interfaz Wi-Fi y origen `192.168.0.0/24`. La regla fue
creada por el usuario en una terminal de administrador y después se consultaron
sus filtros. Está pendiente la prueba desde la PC del compañero. El enlace del
repositorio remoto se proporcionará después, según lo indicado por el usuario.

## Instalación y acceso LAN

Después de instalar dependencias, el responsable ejecuta en su PC:

```powershell
.\setup-local-oracle.ps1
.\run.ps1
.\setup-dw-reader.ps1
.\enable-lan-access.ps1 -LocalAddress 192.168.0.250 -AllowedSubnet 192.168.0.0/24
```

La regla de Windows requiere una terminal con privilegios de administrador.
Permite TCP/1521 solo hacia esa IP y desde esa subred. No cambia el perfil de red
ni configura el router. El lector tiene `CREATE SESSION` y `READ` únicamente
sobre las 11 tablas fuente.

## Alcance de los dos equipos

El equipo staging entrega tablas, contrato, código Prefect y evidencia. Brian y
Miguel cambian su extracción de CSV por las consultas del contrato una vez que
prueben el acceso. Sus transformaciones, modelo dimensional, validaciones del
DW y conexión de Excel se mantienen bajo su repositorio y responsabilidad.

Referencias: [usuarios y esquemas Oracle](https://docs.oracle.com/en/database/oracle/oracle-database/21/multi/introduction-to-the-multitenant-architecture.html),
[privilegio READ](https://docs.oracle.com/en/database/oracle/oracle-database/21/dbseg/configuring-privilege-and-role-authorization.html).
