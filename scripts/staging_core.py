"""CSV fieles -> PostgreSQL: una transaccion para refrescar y validar todo."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from itertools import zip_longest
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import IsolationLevel, sql

from profile_sources import EXPECTED_ROWS, HEADERS, ROOT, TABLE_NAMES, build_profile, read_source, row_digest

DATABASE = "chinook_staging"
PROJECT_MARKER = "chinook_staging_etl:postgres:v1"
CATALOG = "etl_source_file"
# Bloqueo cooperativo por proyecto y esquema, liberado al COMMIT/ROLLBACK.
LOCK_NAMESPACE = 17283641
EXPECTED_CONTROLS = {"total_rows": 15607, "source_cells": 66439, "empty_fields": 1339,
                     "leading_zero_postal_fields": 24, "trailing_space_fields": 8,
                     "invoice_line_rows": 2240, "sales_total": "2328.60", "invoice_total": "2328.60"}


class ConfigurationError(ValueError):
    pass


class SafetyError(RuntimeError):
    pass


class ConcurrentRefreshError(RuntimeError):
    pass


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    schema: str
    user: str
    password: str = field(repr=False)
    sslmode: str = "prefer"
    connect_timeout: int = 5
    statement_timeout_ms: int = 60000

    @classmethod
    def from_env(cls, env_file: Path | str | None = None, *, use_environment: bool = True):
        values = dict(dotenv_values(env_file or ROOT / ".env", interpolate=False))
        if use_environment:
            values.update({k: v for k, v in os.environ.items() if k.startswith("STG_")})
        missing = [key for key in ("STG_USER", "STG_PASSWORD")
                   if not values.get(key) or values[key] in {"CHANGE_ME", "TU_PASSWORD", "USUARIO_CARGADOR"}]
        if missing:
            raise ConfigurationError("Complete " + ", ".join(missing) + " en .env o en el entorno; no use credenciales Oracle.")
        result = cls(host=values.get("STG_HOST") or "127.0.0.1",
                     port=int(values.get("STG_PORT") or 5433),
                     database=values.get("STG_DATABASE") or DATABASE,
                     schema=values.get("STG_SCHEMA") or "public",
                     user=values["STG_USER"], password=values["STG_PASSWORD"],
                     sslmode=values.get("STG_SSLMODE") or "prefer",
                     connect_timeout=int(values.get("STG_CONNECT_TIMEOUT") or 5),
                     statement_timeout_ms=int(values.get("STG_STATEMENT_TIMEOUT_MS") or 60000))
        result.validate()
        return result

    def validate(self, *, administrative: bool = False):
        if not administrative and self.database != DATABASE:
            raise SafetyError("El ETL solo puede operar en la base chinook_staging.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", self.schema):
            raise ConfigurationError("STG_SCHEMA debe ser un identificador simple en minusculas.")
        if not 1 <= self.port <= 65535 or self.connect_timeout <= 0 or self.statement_timeout_ms <= 0:
            raise ConfigurationError("Puerto o limites de tiempo invalidos.")
        if not self.host or not self.user or not self.password:
            raise ConfigurationError("Faltan parametros de conexion.")


def connect(settings: Settings | None = None, *, read_only: bool = False, administrative: bool = False):
    """Un unico punto de conexion; las claves nunca forman parte del DSN/log."""
    settings = settings or Settings.from_env()
    settings.validate(administrative=administrative)
    try:
        connection = psycopg.connect(host=settings.host, port=settings.port, dbname=settings.database,
            user=settings.user, password=settings.password, sslmode=settings.sslmode,
            connect_timeout=settings.connect_timeout, application_name="chinook_staging_etl", autocommit=True,
            options=f"-c statement_timeout={settings.statement_timeout_ms}")
    except psycopg.Error as error:
        code = error.sqlstate or "connection"
        raise ConnectionError(f"No se pudo conectar a PostgreSQL {settings.host}:{settings.port}/{settings.database} ({code}). Revise credenciales y acceso.") from None
    if read_only:
        connection.read_only = True
        connection.isolation_level = IsolationLevel.REPEATABLE_READ
    return connection


def record_controls(tables: dict) -> dict:
    rows = [row for table in tables.values() for row in table["rows"]]
    lines = tables[TABLE_NAMES["InvoiceLine"]]
    invoices = tables[TABLE_NAMES["Invoice"]]
    price, quantity = (lines["header"].index(name) for name in ("UnitPrice", "Quantity"))
    total_index = invoices["header"].index("Total")
    sales = sum((Decimal(row[price]) * Decimal(row[quantity]) for row in lines["rows"]), Decimal("0"))
    total = sum((Decimal(row[total_index]) for row in invoices["rows"]), Decimal("0"))
    postal = sum(bool(re.fullmatch(r"0\d+", row[index]))
                 for table in tables.values() for index, name in enumerate(table["header"])
                 if name in {"PostalCode", "BillingPostalCode"} for row in table["rows"])
    return {"total_rows": len(rows), "source_cells": sum(map(len, rows)),
            "empty_fields": sum(value == "" for row in rows for value in row),
            "leading_zero_postal_fields": postal,
            "trailing_space_fields": sum(value.endswith(" ") for row in rows for value in row),
            "invoice_line_rows": len(lines["rows"]),
            "sales_total": str(sales), "invoice_total": str(total)}


def validate_snapshot(snapshot: dict):
    profile, tables = snapshot["profile"], snapshot["tables"]
    if set(tables) != set(TABLE_NAMES.values()) or len(profile["sources"]) != 11:
        raise ValidationError("Se requieren exactamente las once fuentes acordadas.")
    for source in profile["sources"]:
        name = Path(source["file"]).stem
        if source["table"] != TABLE_NAMES[name] or source["rows"] != EXPECTED_ROWS[name]:
            raise ValidationError(f"Conteo o tabla fuera del contrato: {source['file']}")
        data = tables[source["table"]]
        if data["header"] != HEADERS[name].split(",") or len(data["rows"]) != source["rows"]:
            raise ValidationError(f"Estructura fuera del contrato: {source['file']}")
        if any(len(row) != len(data["header"]) or any(not isinstance(v, str) for v in row) for row in data["rows"]):
            raise ValidationError(f"Campos no textuales o registro incompleto: {source['file']}")
    if record_controls(tables) != EXPECTED_CONTROLS:
        raise ValidationError("Los controles de la fotografia CSV difieren de la referencia acordada.")
    if any(r["orphan_rows"] for r in profile["relationship_checks"]):
        raise ValidationError("Las referencias fuente difieren del contrato de integridad.")


def snapshot_sources() -> dict:
    profile = build_profile()
    recorded = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    if profile != recorded:
        raise ValidationError("Los CSV difieren del manifiesto versionado; revise los cambios.")
    tables = {}
    for source in profile["sources"]:
        header, rows, raw = read_source(ROOT / "data" / "raw" / source["file"])
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValidationError(f"{source['file']} cambio durante la lectura.")
        tables[source["table"]] = {"header": header, "rows": rows}
    snapshot = {"profile": profile, "tables": tables}
    validate_snapshot(snapshot)
    return snapshot


def check_environment(connection, settings: Settings):
    row = connection.execute("SELECT current_database(), current_user, current_setting('server_version_num')::integer, "
        "current_setting('server_encoding'), (SELECT rolsuper FROM pg_roles WHERE rolname=current_user), "
        "(SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database())").fetchone()
    if row[0] != DATABASE or row[0] != settings.database:
        raise SafetyError("Conexion a una base diferente de chinook_staging.")
    if row[2] < 170000 or row[3] != "UTF8":
        raise SafetyError("Se requiere PostgreSQL 17 o posterior y codificacion UTF8.")
    if row[4]:
        raise SafetyError("El ETL y el lector no deben ejecutarse como superusuario. Use roles limitados.")
    if row[5] != PROJECT_MARKER:
        raise SafetyError("La base no tiene la marca del proyecto. No se modifican bases de proposito desconocido.")


def expected_columns(source: dict | None = None) -> list[tuple]:
    if source is None:
        return [("source_file", "text", "NO", None), ("source_sha256", "text", "NO", None),
                ("expected_rows", "integer", "NO", None), ("column_count", "integer", "NO", None),
                ("file_bytes", "bigint", "NO", None)]
    return [("CSV_ROW_NUMBER", "integer", "NO", None)] + [
        (column["name"], "text", "YES", None) for column in source["columns"]]


def check_table_shapes(connection, profile: dict, settings: Settings):
    entries = [(s["table"], expected_columns(s), "CSV_ROW_NUMBER") for s in profile["sources"]]
    entries.append((CATALOG, expected_columns(), "source_file"))
    for name, expected, key in entries:
        actual = connection.execute("SELECT column_name,data_type,is_nullable,column_default "
            "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (settings.schema, name)).fetchall()
        if actual != expected:
            raise ValidationError(f"Estructura inesperada: {settings.schema}.{name}; no se modifica.")
        keys = connection.execute("SELECT k.column_name FROM information_schema.table_constraints t "
            "JOIN information_schema.key_column_usage k ON k.constraint_catalog=t.constraint_catalog "
            "AND k.constraint_schema=t.constraint_schema AND k.constraint_name=t.constraint_name "
            "AND k.table_name=t.table_name WHERE t.constraint_type='PRIMARY KEY' "
            "AND t.table_schema=%s AND t.table_name=%s ORDER BY k.ordinal_position",
            (settings.schema, name)).fetchall()
        if keys != [(key,)]:
            raise ValidationError(f"Clave primaria inesperada: {name}")


def acquire_refresh_lock(connection, settings: Settings):
    schema_key = int.from_bytes(hashlib.sha256(settings.schema.encode()).digest()[:4], "big", signed=True)
    acquired = connection.execute("SELECT pg_try_advisory_xact_lock(%s,%s)", (LOCK_NAMESPACE, schema_key)).fetchone()[0]
    if not acquired:
        raise ConcurrentRefreshError("Otra recarga mantiene el bloqueo transaccional de este staging.")


def prepare_tables(connection, snapshot: dict, settings: Settings):
    """DDL inicial atomico. Nunca adopta tablas parciales ni objetos ajenos."""
    namespace = connection.execute("SELECT oid FROM pg_namespace WHERE nspname=%s", (settings.schema,)).fetchone()
    if namespace is None:
        raise SafetyError("El esquema debe existir antes de ejecutar el ETL.")
    objects = connection.execute("SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f')", (settings.schema,)).fetchall()
    expected = set(TABLE_NAMES.values()) | {CATALOG}
    if objects:
        if dict(objects) != dict.fromkeys(expected, "r"):
            raise SafetyError("El esquema contiene objetos parciales o ajenos. No se borra ni se altera su estructura.")
    else:
        # El unico DDL es create_staging.sql. Identifier permite reutilizarlo
        # en un esquema de pruebas sin tocar public ni duplicar definiciones.
        ddl = (ROOT / "sql" / "create_staging.sql").read_text(encoding="utf-8")
        statement = sql.SQL(ddl.replace("public.", "{schema}.")).format(schema=sql.Identifier(settings.schema))
        connection.execute(statement, prepare=False)
    check_table_shapes(connection, snapshot["profile"], settings)


def insert_snapshot(connection, snapshot: dict, settings: Settings, log=print) -> dict:
    """Full Refresh: DELETE e INSERT sin confirmar; solo sobre la lista acordada."""
    with connection.cursor() as cursor:
        for name in list(TABLE_NAMES.values()) + [CATALOG]:
            cursor.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(settings.schema, name)))
        for source in snapshot["profile"]["sources"]:
            table = source["table"]
            data = snapshot["tables"][table]
            names = ["CSV_ROW_NUMBER"] + data["header"]
            statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(settings.schema, table), sql.SQL(", ").join(map(sql.Identifier, names)),
                sql.SQL(", ").join(sql.Placeholder() for _ in names))
            # Se insertan los strings originales; '' nunca se transforma a None.
            cursor.executemany(statement, ((number, *row) for number, row in enumerate(data["rows"], 1)))
            cursor.execute(sql.SQL("INSERT INTO {} (source_file,source_sha256,expected_rows,column_count,file_bytes) "
                "VALUES (%s,%s,%s,%s,%s)").format(sql.Identifier(settings.schema, CATALOG)),
                (source["file"], source["sha256"], source["rows"], len(data["header"]), source["bytes"]))
            log(f"{table}: {source['rows']} registros insertados, pendientes de validacion")
    return {"rows_loaded": snapshot["profile"]["total_rows"]}


def compare_source_rows(connection, snapshot: dict, settings: Settings, *, source_only: bool = False) -> dict:
    verified, actual_tables = [], {}
    with connection.cursor() as cursor:
        cursor.arraysize = 1000
        for source in snapshot["profile"]["sources"]:
            table = source["table"]
            header, original = snapshot["tables"][table]["header"], snapshot["tables"][table]["rows"]
            columns = header if source_only else header + ["CSV_ROW_NUMBER"]
            cursor.execute(sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)), sql.Identifier(settings.schema, table),
                sql.Identifier("CSV_ROW_NUMBER")))
            if [c.name for c in cursor.description] != columns or any(c.type_code != 25 for c in cursor.description[:len(header)]):
                raise ValidationError(f"Nombres o tipos fuente inesperados: {table}")
            rows = []
            for number, (expected, stored) in enumerate(zip_longest(original, cursor), 1):
                if expected is None or stored is None:
                    raise ValidationError(f"Cantidad distinta en {table}, registro {number}.")
                required = tuple(expected) if source_only else tuple(expected) + (number,)
                if stored != required:
                    raise ValidationError(f"Contenido u ordinal distinto en {table}, registro {number}.")
                actual = list(stored[:len(header)])
                if row_digest(actual) != row_digest(expected):
                    raise ValidationError(f"Hash distinto en {table}, registro {number}.")
                rows.append(actual)
            actual_tables[table] = {"header": header, "rows": rows}
            verified.append({"file": source["file"], "table": table, "rows": len(rows),
                             "source_sha256": source["sha256"], "all_values_equal": True})
    controls = record_controls(actual_tables)
    if controls != EXPECTED_CONTROLS:
        raise ValidationError("Los controles monetarios o de fidelidad no coinciden con la referencia.")
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "engine": "PostgreSQL",
            "database": settings.database, "schema": settings.schema, "sources": verified,
            "controls": controls, "total_rows": controls["total_rows"],
            "comparison": "Every original CSV field equals PostgreSQL TEXT; empty fields remain empty strings"}


def verify_connection(connection, snapshot: dict, settings: Settings) -> dict:
    check_environment(connection, settings)
    check_table_shapes(connection, snapshot["profile"], settings)
    evidence = compare_source_rows(connection, snapshot, settings)
    actual = connection.execute(sql.SQL("SELECT source_file,source_sha256,expected_rows,column_count,file_bytes "
        "FROM {} ORDER BY source_file").format(sql.Identifier(settings.schema, CATALOG))).fetchall()
    expected = sorted((s["file"], s["sha256"], s["rows"], len(s["columns"]), s["bytes"]) for s in snapshot["profile"]["sources"])
    if actual != expected:
        raise ValidationError("El catalogo PostgreSQL difiere del manifiesto CSV.")
    evidence["catalog_matches_manifest"] = True
    return evidence


def load_and_validate(snapshot: dict, settings: Settings | None = None, log=print) -> dict:
    """Unica ruta de carga. El contexto transaction revierte TODO ante excepciones."""
    validate_snapshot(snapshot)  # Antes de abrir una conexion o tocar tablas.
    settings = settings or Settings.from_env()
    with connect(settings) as connection:
        with connection.transaction():
            check_environment(connection, settings)
            acquire_refresh_lock(connection, settings)
            prepare_tables(connection, snapshot, settings)
            insert_snapshot(connection, snapshot, settings, log)
            evidence = verify_connection(connection, snapshot, settings)
        # Solo se alcanza despues del COMMIT del contexto transaction.
    evidence["committed"] = True
    evidence["phase"] = "validated-before-commit"
    return evidence


def validate_existing(snapshot: dict, settings: Settings | None = None) -> dict:
    validate_snapshot(snapshot)
    settings = settings or Settings.from_env()
    with connect(settings, read_only=True) as connection:
        with connection.transaction():
            evidence = verify_connection(connection, snapshot, settings)
    evidence["phase"] = "independent-read-only-verification"
    return evidence
