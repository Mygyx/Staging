"""Inspeccion autenticada y aprovisionamiento optativo de una base nueva y propia."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

from profile_sources import ROOT
from staging_core import DATABASE, PROJECT_MARKER, ConfigurationError, SafetyError, Settings, acquire_refresh_lock, check_environment, connect, prepare_tables, snapshot_sources

LOADER = "chinook_stg_loader"
READER = "chinook_stg_reader"


def administrative_settings(path: Path) -> Settings:
    values = dict(dotenv_values(path, interpolate=False))
    values.update({key: value for key, value in os.environ.items() if key in {
        "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"}})
    if any(not values.get(key) or values[key] == "CHANGE_ME" for key in ("PGUSER", "PGPASSWORD")):
        raise ConfigurationError("Faltan PGUSER/PGPASSWORD en .env.admin. Configure el acceso administrativo PostgreSQL autorizado.")
    return Settings(values.get("PGHOST") or "127.0.0.1", int(values.get("PGPORT") or 5433),
                    values.get("PGDATABASE") or "postgres", "public", values["PGUSER"], values["PGPASSWORD"])


def inspect_server(settings: Settings) -> dict:
    with connect(settings, read_only=True, administrative=True) as connection:
        with connection.transaction():
            identity = connection.execute("SELECT current_database(),current_user,current_setting('server_version'),"
                "current_setting('server_version_num')::integer,inet_server_port()").fetchone()
            databases = connection.execute("SELECT datname,pg_get_userbyid(datdba),"
                "shobj_description(oid,'pg_database') FROM pg_database WHERE NOT datistemplate ORDER BY datname").fetchall()
            privileges = connection.execute("SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user").fetchone()
    return {"connected_database": identity[0], "administrative_user": identity[1], "server_version": identity[2],
            "server_version_num": identity[3], "port": identity[4],
            "capabilities": dict(zip(("superuser", "create_database", "create_role"), privileges)),
            "databases": [{"name": row[0], "owner": row[1], "marked_for_this_project": row[2] == PROJECT_MARKER}
                          for row in databases]}


def guard_target(report: dict, loader: Settings, reader: Settings):
    if report["server_version_num"] // 10000 != 17:
        raise SafetyError("El candidato autorizado es PostgreSQL 17; revise la instancia antes de continuar.")
    if loader.user != LOADER or reader.user != READER or loader.schema != "public" or reader.schema != "public":
        raise ConfigurationError("El aprovisionador usa chinook_stg_loader, chinook_stg_reader y public. Otras configuraciones requieren provision manual revisada.")
    for database in report["databases"]:
        if database["name"].lower() in {"chinook_dw", "chinook_datawarehouse"}:
            raise SafetyError("Esta instancia contiene una base del DW; no cumple la separacion acordada.")
        if database["name"] == DATABASE and (not database["marked_for_this_project"] or database["owner"] != loader.user):
            raise SafetyError("chinook_staging ya existe con proposito o propietario no autorizado. No se crea ni sobrescribe ningun objeto.")


def provision(admin: Settings, loader: Settings, reader: Settings) -> dict:
    loader.validate()
    reader.validate()
    if any((config.host, config.port) != (admin.host, admin.port) for config in (loader, reader)):
        raise SafetyError("Las tres configuraciones deben apuntar a la misma instancia verificada.")
    report = inspect_server(admin)  # Lectura autenticada ANTES de cualquier CREATE.
    guard_target(report, loader, reader)
    snapshot = snapshot_sources()
    with connect(admin, administrative=True) as connection:
        existing = connection.execute("SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,"
            "shobj_description(oid,'pg_authid'),EXISTS(SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid) "
            "FROM pg_roles WHERE rolname=ANY(%s)", ([LOADER, READER],)).fetchall()
        for role in existing:
            if role[4] != PROJECT_MARKER or any(role[1:4]) or role[5]:
                raise SafetyError("Existe un rol homonimo no administrado por este proyecto; no se altera.")
        known = {role[0] for role in existing}
        with connection.transaction():
            for config in (loader, reader):
                if config.user not in known:
                    # DDL no admite valores bind ordinarios: Literal escapa la clave;
                    # no se imprime ni se guarda la sentencia resultante.
                    connection.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}").format(
                        sql.Identifier(config.user), sql.Literal(config.password)))
                    connection.execute(sql.SQL("COMMENT ON ROLE {} IS {}").format(sql.Identifier(config.user), sql.Literal(PROJECT_MARKER)))
        if not any(d["name"] == DATABASE for d in report["databases"]):
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'").format(
                sql.Identifier(DATABASE), sql.Identifier(loader.user)))
            connection.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(DATABASE), sql.Literal(PROJECT_MARKER)))
        # Los roles existentes nunca cambian de clave automaticamente.
    with connect(loader) as connection:
        with connection.transaction():
            check_environment(connection, loader)
            acquire_refresh_lock(connection, loader)
            prepare_tables(connection, snapshot, loader)
            connection.execute((ROOT / "sql/provision_access.sql").read_text(encoding="utf-8"), prepare=False)
    report["provisioned_database"] = DATABASE
    report["runtime_loader"] = loader.user
    report["reader"] = reader.user
    report["data_loaded"] = False
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--inspect", action="store_true", help="Solo listar metadatos; no crear objetos")
    actions.add_argument("--create-new", action="store_true", help="Crear nuestra base/roles si no hay homonimos ajenos")
    parser.add_argument("--admin-env", type=Path, default=ROOT / ".env.admin")
    args = parser.parse_args()
    try:
        admin = administrative_settings(args.admin_env)
        result = inspect_server(admin) if args.inspect else provision(admin,
            Settings.from_env(ROOT / ".env", use_environment=False),
            Settings.from_env(ROOT / ".env.reader", use_environment=False))
        print(json.dumps(result, indent=2))
    except (ConfigurationError, SafetyError, ConnectionError) as error:
        parser.exit(2, str(error) + "\n")
    except psycopg.Error as error:
        parser.exit(2, f"Aprovisionamiento detenido (SQLSTATE {error.sqlstate}). No se eliminan objetos ni se modifican bases ajenas; revise los recursos creados antes de reintentar.\n")
