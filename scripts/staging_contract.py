"""Contrato de lectura para el equipo del Data Warehouse; no transforma datos."""
from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal

import oracledb

from profile_sources import HEADERS, ROOT, TABLE_NAMES

OWNER = "CHINOOK_STAGING"


def source_query(source: str) -> str:
    columns = HEADERS[source].split(",")
    selected = ", ".join(f'{column} AS "{column}"' for column in columns)
    return f"SELECT {selected} FROM {OWNER}.{TABLE_NAMES[source]} ORDER BY CSV_ROW_NUMBER"


def contract(profile: dict) -> dict:
    return {"contract_version": 1, "repository": "chinook_staging_etl",
            "oracle_service": "XEPDB1", "schema": OWNER,
            "source_values": "VARCHAR2; empty CSV fields are NULL; no normalization",
            "sources": [{"source": s["file"][:-4], "table": s["table"], "rows": s["rows"],
                         "columns": [c["name"] for c in s["columns"]],
                         "query": source_query(s["file"][:-4])} for s in profile["sources"]]}


def verify_reader() -> dict:
    with oracledb.connect(user=os.environ["STAGING_USER"],
                          password=os.environ["STAGING_PASSWORD"],
                          dsn=os.environ["STAGING_DSN"], tcp_connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            sources = json.loads((ROOT / "contracts" / "staging_sources.json").read_text(encoding="utf-8"))
            verified = []
            sales_total = Decimal("0")
            invoice_total = Decimal("0")
            for source in sources["sources"]:
                cursor.execute(source["query"])
                names = [column[0] for column in cursor.description]
                if names != source["columns"]:
                    raise ValueError(f"Columnas distintas en {source['table']}")
                rows = cursor.fetchall()
                if len(rows) != source["rows"]:
                    raise ValueError(f"Conteo distinto en {source['table']}")
                if source["source"] == "InvoiceLine":
                    price, quantity = names.index("UnitPrice"), names.index("Quantity")
                    sales_total = sum((Decimal(row[price]) * Decimal(row[quantity]) for row in rows), Decimal("0"))
                elif source["source"] == "Invoice":
                    invoice_total = sum((Decimal(row[names.index("Total")]) for row in rows), Decimal("0"))
                verified.append({"table": source["table"], "rows": len(rows), "column_names_match_csv": True})
            if sales_total != invoice_total:
                raise ValueError("El total de lineas no coincide con el de facturas.")
            return {"sources": verified, "total_rows": sum(s["rows"] for s in verified),
                    "sales_total": str(sales_total), "invoice_total": str(invoice_total),
                    "all_checks_passed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true", help="Generar el contrato desde el manifiesto")
    args = parser.parse_args()
    if args.export:
        manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
        destination = ROOT / "contracts" / "staging_sources.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes((json.dumps(contract(manifest), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print("Contrato de 11 tablas generado")
    else:
        print(json.dumps(verify_reader(), ensure_ascii=False, indent=2))
