"""Interfaz PostgreSQL para el DW: encabezados CSV, TEXT y lectura consistente."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from psycopg import sql

from profile_sources import HEADERS, ROOT, TABLE_NAMES
from staging_core import CATALOG, DATABASE, EXPECTED_CONTROLS, Settings, SafetyError, check_environment, compare_source_rows, connect, snapshot_sources, validate_snapshot

FORBIDDEN_SOURCE_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN")
FORBIDDEN_COLUMN_PRIVILEGES = ("INSERT", "UPDATE", "REFERENCES")
TEMP_POLICY = "TEMP may remain inherited for session-local objects; it does not authorize changes to staging source tables. This verifier changes no grants."


def source_query(source: str, schema: str = "public") -> str:
    return sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
        sql.SQL(", ").join(map(sql.Identifier, HEADERS[source].split(","))),
        sql.Identifier(schema, TABLE_NAMES[source]), sql.Identifier("CSV_ROW_NUMBER")).as_string()


def contract(profile: dict) -> dict:
    return {"contract_version": 3, "repository": "chinook_staging_etl", "engine": "PostgreSQL",
            "database": DATABASE, "schema": "public", "source_type": "TEXT",
            "empty_csv_fields": "empty string, never automatically NULL",
            "technical_ordinal": "CSV_ROW_NUMBER; excluded from the source queries",
            "technical_ordinal_type": "INTEGER",
            "reader_user_example": "chinook_stg_reader", "host_environment": "STG_HOST",
            "port_environment": "STG_PORT", "local_port_candidate": 5433,
            "isolation": "REPEATABLE READ READ ONLY across all eleven SELECTs",
            "reader_policy": {"required_source_privileges": ["SELECT"],
                              "forbidden_source_privileges": list(FORBIDDEN_SOURCE_PRIVILEGES),
                              "forbidden_column_privileges": list(FORBIDDEN_COLUMN_PRIVILEGES),
                              "schema_create": False, "database_create": False,
                              "technical_catalog_select": False, "temp": TEMP_POLICY,
                              "scope": "Current reader role and the eleven source tables; not a security audit of every server object or possible role switch."},
            "controls": EXPECTED_CONTROLS,
            "sources": [{"source": s["file"][:-4], "table": s["table"], "rows": s["rows"],
                         "columns": [c["name"] for c in s["columns"]],
                         "query": source_query(s["file"][:-4])} for s in profile["sources"]]}


def verify_reader(settings: Settings | None = None, snapshot: dict | None = None) -> dict:
    settings = settings or Settings.from_env(ROOT / ".env.reader")
    snapshot = snapshot or snapshot_sources()
    validate_snapshot(snapshot)
    with connect(settings, read_only=True) as connection:
        with connection.transaction():
            check_environment(connection, settings)
            role_flags = connection.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                "FROM pg_roles WHERE rolname=current_user").fetchone()
            if any(role_flags):
                raise SafetyError("El lector no debe tener atributos administrativos de rol.")
            database_create, database_temp = connection.execute("SELECT "
                "has_database_privilege(current_user,current_database(),'CREATE'),"
                "has_database_privilege(current_user,current_database(),'TEMP')").fetchone()
            if database_create:
                raise SafetyError("El lector no debe poder crear esquemas en la base.")
            if connection.execute("SELECT has_schema_privilege(current_user,%s,'CREATE')", (settings.schema,)).fetchone()[0]:
                raise SafetyError("El lector no debe tener permiso CREATE en el esquema.")
            catalog = sql.Identifier(settings.schema, CATALOG).as_string()
            if connection.execute("SELECT has_table_privilege(current_user,%s,'SELECT')", (catalog,)).fetchone()[0]:
                raise SafetyError("El catalogo tecnico no forma parte del acceso lector acordado.")
            for table in TABLE_NAMES.values():
                relation = sql.Identifier(settings.schema, table).as_string()
                if not connection.execute("SELECT has_table_privilege(current_user,%s,'SELECT')", (relation,)).fetchone()[0]:
                    raise SafetyError(f"Falta permiso SELECT en {table}.")
                for privilege in FORBIDDEN_SOURCE_PRIVILEGES:
                    if connection.execute("SELECT has_table_privilege(current_user,%s,%s)", (relation, privilege)).fetchone()[0]:
                        raise SafetyError(f"El lector tiene permiso de escritura {privilege} en {table}.")
                for privilege in FORBIDDEN_COLUMN_PRIVILEGES:
                    if connection.execute("SELECT has_any_column_privilege(current_user,%s,%s)", (relation, privilege)).fetchone()[0]:
                        raise SafetyError(f"El lector tiene permiso {privilege} en alguna columna de {table}.")
            result = compare_source_rows(connection, snapshot, settings, source_only=True)
    result["source_tables_read_only"] = True
    result["reader_permission_scope"] = {"role": settings.user, "schema": settings.schema,
        "source_tables_checked": list(TABLE_NAMES.values()),
        "required_privileges": ["SELECT"], "forbidden_privileges": list(FORBIDDEN_SOURCE_PRIVILEGES),
        "forbidden_column_privileges": list(FORBIDDEN_COLUMN_PRIVILEGES),
        "administrative_role_flags": False, "database_create": False,
        "schema_create": False, "technical_catalog_select": False,
        "scope": "Current role and these sources; no claim about every server object or role switch."}
    result["database_temp_privilege"] = database_temp
    result["temp_policy"] = TEMP_POLICY
    result["tested_from_other_pc"] = False
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--export", action="store_true", help="Generar contrato despues de verificar los CSV")
    action.add_argument("--check", action="store_true", help="Comprobar SELECT y ausencia de permisos de escritura")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.reader")
    args = parser.parse_args()
    if args.export:
        target = ROOT / "contracts" / "staging_sources.json"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((json.dumps(contract(snapshot_sources()["profile"]), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print("Contrato PostgreSQL de once tablas generado; no se conecto a ninguna base")
    else:
        print(json.dumps(verify_reader(Settings.from_env(args.env_file)), ensure_ascii=False, indent=2))
