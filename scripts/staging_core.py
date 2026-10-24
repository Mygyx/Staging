"""Carga y comparacion exacta: sin conversiones de tipos en datos fuente."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from itertools import zip_longest

import oracledb

from profile_sources import ROOT, build_profile, read_source, row_digest


def snapshot_sources() -> dict:
    profile = build_profile()
    recorded = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    if profile != recorded:
        raise ValueError("Los CSV difieren del manifiesto versionado; revise los cambios.")
    tables = {}
    for source in profile["sources"]:
        header, rows, raw = read_source(ROOT / "data" / "raw" / source["file"])
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"{source['file']} cambio durante la lectura.")
        tables[source["table"]] = {"header": header, "rows": rows}
    return {"profile": profile, "tables": tables}


def connect():
    required = ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN")
    if any(not os.environ.get(name) for name in required):
        raise ValueError("Defina ORACLE_USER, ORACLE_PASSWORD y ORACLE_DSN o use run.ps1.")
    connection = oracledb.connect(user=os.environ["ORACLE_USER"],
                                password=os.environ["ORACLE_PASSWORD"],
                                dsn=os.environ["ORACLE_DSN"])
    connection.autocommit = False
    return connection


def check_environment(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET'")
        if cursor.fetchone()[0] != "AL32UTF8":
            raise ValueError("Se requiere NLS_CHARACTERSET=AL32UTF8.")
        cursor.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA'), SYS_CONTEXT('USERENV','CON_NAME') FROM dual")
        schema, container = cursor.fetchone()
        if schema in {"SYS", "SYSTEM"} or container == "CDB$ROOT":
            raise ValueError("Conecte a un usuario de staging dentro de una PDB.")


def expected_columns(source: dict) -> list[tuple]:
    return [(c["name"].upper(), "VARCHAR2", max(1, c["max_utf8_bytes"]), "B", "Y")
            for c in source["columns"]] + [("CSV_ROW_NUMBER", "NUMBER", 22, None, "N")]


def check_table_shapes(connection, profile: dict) -> None:
    with connection.cursor() as cursor:
        for source in profile["sources"]:
            cursor.execute("SELECT column_name, data_type, data_length, char_used, nullable "
                           "FROM user_tab_columns WHERE table_name = :1 ORDER BY column_id",
                           [source["table"]])
            if cursor.fetchall() != expected_columns(source):
                raise ValueError(f"Estructura inesperada en {source['table']}; no se modifica.")


def prepare_tables(snapshot: dict) -> str:
    profile = snapshot["profile"]
    names = [s["table"] for s in profile["sources"]] + ["STG_SOURCE_FILE"]
    placeholders = ",".join(f":{i}" for i in range(1, len(names)+1))
    with connect() as connection:
        check_environment(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT object_name, object_type FROM user_objects WHERE object_name IN ({placeholders})", names)
            existing = cursor.fetchall()
            if existing:
                if sorted(existing) != sorted((name, "TABLE") for name in names):
                    raise ValueError("Existen objetos STG incompletos o incompatibles. Revise el esquema.")
                check_table_shapes(connection, profile)
                return "Tablas existentes: estructura revisada"
            ddl = (ROOT / "sql" / "01_create_tables.sql").read_text(encoding="ascii")
            statements = re.findall(r"CREATE TABLE [A-Z_]+ \(.*?\n\);", ddl, re.DOTALL)
            if len(statements) != len(names):
                raise ValueError("No se reconocen las 12 sentencias CREATE TABLE.")
            for statement in statements:
                cursor.execute(statement[:-1])
        check_table_shapes(connection, profile)
    return "12 tablas creadas"


def verify_connection(connection, snapshot: dict) -> dict:
    """Relee cada campo de Oracle y lo compara, incluyendo espacios y Unicode."""
    check_environment(connection)
    profile = snapshot["profile"]
    check_table_shapes(connection, profile)
    verified = []
    with connection.cursor() as cursor:
        cursor.arraysize = 1000
        for source in profile["sources"]:
            table = source["table"]
            header, rows = snapshot["tables"][table]["header"], snapshot["tables"][table]["rows"]
            cursor.execute(f"SELECT {', '.join(header)}, CSV_ROW_NUMBER FROM {table} ORDER BY CSV_ROW_NUMBER")
            count = 0
            for number, (original, stored) in enumerate(zip_longest(rows, cursor), 1):
                if original is None or stored is None:
                    raise ValueError(f"Cantidad distinta en {table}, registro {number}.")
                expected = tuple(None if v == "" else v for v in original) + (number,)
                if stored != expected:
                    raise ValueError(f"Contenido distinto en {table}, registro {number}.")
                actual = ["" if v is None else v for v in stored[:-1]]
                if row_digest(actual) != row_digest(original):
                    raise ValueError(f"Hash distinto en {table}, registro {number}.")
                count += 1
            verified.append({"file": source["file"], "table": table, "rows": count,
                             "source_sha256": source["sha256"], "all_values_equal": True})
        cursor.execute("SELECT SOURCE_FILE, SOURCE_SHA256, EXPECTED_ROWS, COLUMN_COUNT, FILE_BYTES "
                       "FROM STG_SOURCE_FILE ORDER BY SOURCE_FILE")
        expected_manifest = sorted((s["file"], s["sha256"], s["rows"], len(s["columns"]), s["bytes"])
                                   for s in profile["sources"])
        if cursor.fetchall() != expected_manifest:
            raise ValueError("El manifiesto en Oracle difiere del manifiesto de los CSV.")
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_rows": sum(s["rows"] for s in verified), "sources": verified,
            "comparison": "Every source field equals its Oracle value; empty CSV fields map to NULL"}


def load_and_validate(snapshot: dict, log=print) -> dict:
    """Una conexion y una transaccion para las 11 fuentes y su manifiesto."""
    with connect() as connection:
        check_environment(connection)
        check_table_shapes(connection, snapshot["profile"])
        try:
            with connection.cursor() as cursor:
                tables = [s["table"] for s in snapshot["profile"]["sources"]] + ["STG_SOURCE_FILE"]
                # Mismo orden para bloquear ejecuciones concurrentes. NOWAIT no deja
                # dos cargas avanzar juntas; no hay DELETE, TRUNCATE ni sobreescritura.
                for table in tables:
                    cursor.execute(f"LOCK TABLE {table} IN EXCLUSIVE MODE NOWAIT")
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    if cursor.fetchone()[0] != 0:
                        raise ValueError(f"{table} contiene datos. Use --validate-only para revisarlos.")
                for source in snapshot["profile"]["sources"]:
                    table = source["table"]
                    data = snapshot["tables"][table]
                    columns = data["header"] + ["CSV_ROW_NUMBER"]
                    placeholders = ", ".join(f":{i}" for i in range(1, len(columns)+1))
                    statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                    cursor.setinputsizes(*[max(1, c["max_utf8_bytes"]) for c in source["columns"]], oracledb.DB_TYPE_NUMBER)
                    rows = [tuple(None if value == "" else value for value in row) + (number,)
                            for number, row in enumerate(data["rows"], 1)]
                    cursor.executemany(statement, rows)
                    # Nueva sentencia: liberar los tamaños de binds de la tabla anterior.
                    with connection.cursor() as metadata_cursor:
                        metadata_cursor.execute("INSERT INTO STG_SOURCE_FILE "
                            "(SOURCE_FILE, SOURCE_SHA256, EXPECTED_ROWS, COLUMN_COUNT, FILE_BYTES) "
                            "VALUES (:1, :2, :3, :4, :5)",
                            [source["file"], source["sha256"], source["rows"], len(source["columns"]), source["bytes"]])
                    log(f"Cargado {table}: {len(rows)} registros, pendiente de validacion")
            evidence = verify_connection(connection, snapshot)
            connection.commit()
            evidence["committed"] = True
            return evidence
        except BaseException:
            connection.rollback()
            raise


def validate_existing(snapshot: dict) -> dict:
    with connect() as connection:
        # Una fotografia consistente de todas las tablas durante la validacion.
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        evidence = verify_connection(connection, snapshot)
        evidence["mode"] = "validate-only"
        return evidence
