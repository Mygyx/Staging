"""Inventario reproducible; solo biblioteca estandar, sin inferir tipos de datos."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {
    "Album": "AlbumId,Title,ArtistId",
    "Artist": "ArtistId,Name",
    "Customer": "CustomerId,FirstName,LastName,Company,Address,City,State,Country,PostalCode,Phone,Fax,Email,SupportRepId",
    "Employee": "EmployeeId,LastName,FirstName,Title,ReportsTo,BirthDate,HireDate,Address,City,State,Country,PostalCode,Phone,Fax,Email",
    "Genre": "GenreId,Name",
    "Invoice": "InvoiceId,CustomerId,InvoiceDate,BillingAddress,BillingCity,BillingState,BillingCountry,BillingPostalCode,Total",
    "InvoiceLine": "InvoiceLineId,InvoiceId,TrackId,UnitPrice,Quantity",
    "MediaType": "MediaTypeId,Name",
    "Playlist": "PlaylistId,Name",
    "PlaylistTrack": "PlaylistId,TrackId",
    "Track": "TrackId,Name,AlbumId,MediaTypeId,GenreId,Composer,Milliseconds,Bytes,UnitPrice",
}
TABLE_NAMES = {name: "stg_" + re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
               for name in HEADERS}
EXPECTED_ROWS = dict(zip(HEADERS, [347, 275, 59, 8, 25, 412, 2240, 5, 18, 8715, 3503]))
RELATIONS = [
    ("Album", "ArtistId", "Artist", "ArtistId"),
    ("Customer", "SupportRepId", "Employee", "EmployeeId"),
    ("Employee", "ReportsTo", "Employee", "EmployeeId"),
    ("Invoice", "CustomerId", "Customer", "CustomerId"),
    ("InvoiceLine", "InvoiceId", "Invoice", "InvoiceId"),
    ("InvoiceLine", "TrackId", "Track", "TrackId"),
    ("PlaylistTrack", "PlaylistId", "Playlist", "PlaylistId"),
    ("PlaylistTrack", "TrackId", "Track", "TrackId"),
    ("Track", "AlbumId", "Album", "AlbumId"),
    ("Track", "MediaTypeId", "MediaType", "MediaTypeId"),
    ("Track", "GenreId", "Genre", "GenreId"),
]


def read_source(path: Path) -> tuple[list[str], list[list[str]], bytes]:
    raw = path.read_bytes()
    # utf-8-sig quita solo un BOM inicial si existe, nunca modifica el archivo.
    with io.StringIO(raw.decode("utf-8-sig", errors="strict"), newline="") as stream:
        reader = csv.reader(stream, delimiter=",", quotechar='"', strict=True)
        header = next(reader)
        rows = list(reader)
    if header != HEADERS[path.stem].split(","):
        raise ValueError(f"{path.name}: encabezado inesperado")
    for number, row in enumerate(rows, 1):
        if len(row) != len(header):
            raise ValueError(f"{path.name}, registro {number}: cantidad de campos invalida")
        if any("\x00" in value for value in row):
            raise ValueError(f"{path.name}, registro {number}: contiene NUL")
    return header, rows, raw


def row_digest(row: list[str]) -> str:
    """SHA256 de campos UTF-8 con prefijos de longitud en bytes; incluye vacios."""
    canonical = "".join(f"{len(value.encode('utf-8'))}:{value}" for value in row)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_profile(source_dir: Path = ROOT / "data" / "raw") -> dict:
    expected = {f"{name}.csv" for name in HEADERS}
    actual = {path.name for path in source_dir.glob("*.csv")}
    if actual != expected:
        raise ValueError(f"Archivos faltantes: {expected-actual}; adicionales: {actual-expected}")
    tables, sources = {}, []
    for name in HEADERS:
        path = source_dir / f"{name}.csv"
        header, rows, raw = read_source(path)
        tables[name] = (header, rows)
        columns = []
        for index, column in enumerate(header):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", column):
                raise ValueError(f"Identificador PostgreSQL invalido: {column}")
            values = [row[index] for row in rows]
            columns.append({
                "name": column,
                "max_chars": max(map(len, values), default=0),
                "max_utf8_bytes": max((len(v.encode("utf-8")) for v in values), default=0),
                "empty_fields": values.count(""),
                "surrounding_whitespace": sum(v != v.strip() for v in values),
                "distinct_values": len(set(values)),
            })
        sources.append({
            "file": path.name, "table": TABLE_NAMES[name],
            "encoding": "UTF-8", "utf8_bom": raw.startswith(b"\xef\xbb\xbf"),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows), "columns": columns,
            "duplicate_rows": len(rows) - len(set(map(tuple, rows))),
        })
    relations = []
    for child, child_col, parent, parent_col in RELATIONS:
        child_header, child_rows = tables[child]
        parent_header, parent_rows = tables[parent]
        valid = {row[parent_header.index(parent_col)] for row in parent_rows}
        invalid = [row[child_header.index(child_col)] for row in child_rows
                   if row[child_header.index(child_col)] and row[child_header.index(child_col)] not in valid]
        relations.append({"child": f"{child}.{child_col}",
                          "parent": f"{parent}.{parent_col}", "orphan_rows": len(invalid)})
    return {"format_version": 2, "total_rows": sum(s["rows"] for s in sources),
            "sources": sources, "relationship_checks": relations}


def profile_markdown(profile: dict) -> str:
    lines = ["# Inventario y calidad de las fuentes", "",
             "Generado por `python scripts/profile_sources.py`. No se modifica ningun CSV.", "",
             "| CSV | Tabla | Registros | Campos | Vacíos | Filas duplicadas |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for source in profile["sources"]:
        empty = sum(c["empty_fields"] for c in source["columns"])
        lines.append(f"| {source['file']} | {source['table']} | {source['rows']} | {len(source['columns'])} | {empty} | {source['duplicate_rows']} |")
    lines += ["", f"Total: **{profile['total_rows']} registros**.", "",
              "Los vacíos y duplicados se conservan. No se aplican recortes, normalización",
              "de Unicode, conversión numérica ni conversión de fechas. El manifiesto",
              "`data/manifest.json` detalla SHA-256 del archivo completo, tamaños por",
              "columna, vacíos, espacios en extremos y valores distintos.", "",
              "Las relaciones se revisan solo para informar calidad; no generan FK",
              "que puedan rechazar registros originales.", "",
              "| Campo hijo | Campo padre | Registros huérfanos |", "| --- | --- | ---: |"]
    lines += [f"| {r['child']} | {r['parent']} | {r['orphan_rows']} |" for r in profile["relationship_checks"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprueba evidencia sin escribir")
    args = parser.parse_args()
    profile = build_profile()
    outputs = {
        ROOT / "data" / "manifest.json": json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        ROOT / "docs" / "fuentes.md": profile_markdown(profile),
    }
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_bytes() != content.encode("utf-8"):
                raise SystemExit(f"Fuente o evidencia modificada: {path.relative_to(ROOT)}")
        else:
            path.write_bytes(content.encode("utf-8"))
    print(f"OK: {len(profile['sources'])} CSV, {profile['total_rows']} registros; "
          + ("manifiesto intacto" if args.check else "inventario generado"))


if __name__ == "__main__":
    main()
