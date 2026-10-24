"""Genera SQL Oracle determinista a partir del manifiesto verificado."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from profile_sources import ROOT, build_profile, read_source, row_digest

SETTINGS = """WHENEVER OSERROR EXIT FAILURE ROLLBACK
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK
SET DEFINE OFF
SET ESCAPE OFF
SET SQLCASE MIXED
SET SQLBLANKLINES ON
SET AUTOCOMMIT OFF
SET SERVEROUTPUT ON
SET FEEDBACK OFF
SET VERIFY OFF
SET ECHO OFF
"""
BANNER = "-- Generado por scripts/generate_sql.py. No editar manualmente.\n"


def literal(value: str) -> str:
    """SQL ASCII: evita depender de la codificacion configurada en el cliente."""
    if value == "":
        return "NULL"
    if all(32 <= ord(char) <= 126 for char in value):
        return "'" + value.replace("'", "''") + "'"
    encoded = []
    for char in value:
        if char == "\\":
            encoded.append("\\\\")
        elif 32 <= ord(char) <= 126:
            encoded.append(char.replace("'", "''"))
        else:
            utf16 = char.encode("utf-16-be")
            encoded.extend("\\" + utf16[i:i+2].hex().upper() for i in range(0, len(utf16), 2))
    return "UNISTR('" + "".join(encoded) + "')"


def block(body: list[str], declarations: list[str] | None = None) -> str:
    prefix = "DECLARE\n" + "\n".join(declarations) + "\n" if declarations else ""
    return prefix + "BEGIN\n" + "\n".join(body) + "\nEND;\n/\n"


def generate(profile: dict, source_dir: Path = ROOT / "data" / "raw") -> dict[str, str]:
    sources = profile["sources"]
    tables = [s["table"] for s in sources] + ["STG_SOURCE_FILE"]
    env = block([
        "  SELECT value INTO v_charset FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET';",
        "  IF v_charset <> 'AL32UTF8' THEN",
        "    RAISE_APPLICATION_ERROR(-20001, 'Se requiere AL32UTF8 para preservar los valores UTF-8.');",
        "  END IF;",
        "  IF SYS_CONTEXT('USERENV', 'CON_NAME') = 'CDB$ROOT' OR",
        "     SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') IN ('SYS', 'SYSTEM') THEN",
        "    RAISE_APPLICATION_ERROR(-20002, 'Use un esquema de staging dentro de una PDB, no SYS ni SYSTEM.');",
        "  END IF;",
    ], ["  v_charset VARCHAR2(128);"])
    table_list = ", ".join(literal(t) for t in tables)
    collision = block([
        "  SELECT COUNT(*) INTO v_count FROM all_objects",
        "  WHERE owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')",
        f"    AND object_name IN ({table_list});",
        "  IF v_count <> 0 THEN",
        "    RAISE_APPLICATION_ERROR(-20003, 'Ya existen objetos STG. No se elimina ni reemplaza informacion.');",
        "  END IF;",
    ], ["  v_count NUMBER;"])
    ddl = [BANNER, SETTINGS, env, collision]
    for source in sources:
        definitions = []
        for column in source["columns"]:
            size = max(1, column["max_utf8_bytes"])
            if size > 4000:
                raise ValueError(f"{source['file']}.{column['name']}: excede VARCHAR2 estandar")
            definitions.append(f"  {column['name']} VARCHAR2({size} BYTE)")
        definitions.append("  CSV_ROW_NUMBER NUMBER(10) NOT NULL")
        definitions.append(f"  CONSTRAINT PK_{source['table']} PRIMARY KEY (CSV_ROW_NUMBER)")
        ddl.append(f"CREATE TABLE {source['table']} (\n" + ",\n".join(definitions) + "\n);\n")
    ddl.append("""CREATE TABLE STG_SOURCE_FILE (
  SOURCE_FILE VARCHAR2(128 BYTE) NOT NULL,
  SOURCE_SHA256 VARCHAR2(64 BYTE) NOT NULL,
  EXPECTED_ROWS NUMBER(10) NOT NULL,
  COLUMN_COUNT NUMBER(10) NOT NULL,
  FILE_BYTES NUMBER(10) NOT NULL,
  CONSTRAINT PK_STG_SOURCE_FILE PRIMARY KEY (SOURCE_FILE)
);
""")
    load = [BANNER, SETTINGS, env]
    guard = []
    for table in tables:
        guard += [f"  SELECT COUNT(*) INTO v_count FROM {table};",
                  f"  IF v_count <> 0 THEN RAISE_APPLICATION_ERROR(-20004, '{table} debe estar vacia.'); END IF;"]
    load.append(block(guard, ["  v_count NUMBER;"]))
    validate = [BANNER, SETTINGS, env]
    counts = []
    for source in sources:
        table, filename = source["table"], source["file"]
        header, rows, _ = read_source(source_dir / filename)
        columns = ", ".join(header + ["CSV_ROW_NUMBER"])
        load.append(f"PROMPT Cargando {filename}: {len(rows)} registros\n")
        for number, row in enumerate(rows, 1):
            # STANDARD_HASH sobre VARCHAR2 admite hasta 4000 bytes en SQL estandar.
            canonical_bytes = sum(len(v.encode("utf-8")) + len(str(len(v.encode("utf-8")))) + 1 for v in row)
            if canonical_bytes > 4000:
                raise ValueError(f"{filename}:{number}: hash requiere adaptar a CLOB")
            values = ", ".join([literal(v) for v in row] + [str(number)])
            statement = f"INSERT INTO {table} ({columns}) VALUES ({values});\n"
            if len(statement) > 2400:
                raise ValueError(f"{filename}:{number}: sentencia demasiado larga para SQL*Plus")
            load.append(statement)
        load.append("INSERT INTO STG_SOURCE_FILE (SOURCE_FILE, SOURCE_SHA256, EXPECTED_ROWS, COLUMN_COUNT, FILE_BYTES) "
                    f"VALUES ({literal(filename)}, {literal(source['sha256'])}, {len(rows)}, {len(header)}, {source['bytes']});\n")
        counts += [f"  SELECT COUNT(*) INTO v_count FROM {table};",
                   f"  IF v_count <> {len(rows)} THEN RAISE_APPLICATION_ERROR(-20005, 'Conteo incorrecto: {table}'); END IF;"]
        counts += ["  SELECT COUNT(*) INTO v_count FROM STG_SOURCE_FILE",
                   f"  WHERE SOURCE_FILE = {literal(filename)} AND SOURCE_SHA256 = {literal(source['sha256'])}",
                   f"    AND EXPECTED_ROWS = {len(rows)} AND COLUMN_COUNT = {len(header)} AND FILE_BYTES = {source['bytes']};",
                   f"  IF v_count <> 1 THEN RAISE_APPLICATION_ERROR(-20006, 'Manifiesto incorrecto: {filename}'); END IF;"]
        canonical = " ||\n        ".join(
            f"TO_CHAR(NVL(LENGTHB({col}), 0), 'FM999999990') || ':' || {col}" for col in header)
        for start in range(0, len(rows), 400):
            declarations = [
                "  PROCEDURE check_row(p_row NUMBER, p_expected VARCHAR2) IS",
                "    v_actual VARCHAR2(64);",
                "  BEGIN",
                "    SELECT LOWER(RAWTOHEX(STANDARD_HASH(",
                f"        {canonical}, 'SHA256')))",
                f"      INTO v_actual FROM {table} WHERE CSV_ROW_NUMBER = p_row;",
                "    IF v_actual <> p_expected OR v_actual IS NULL THEN",
                f"      RAISE_APPLICATION_ERROR(-20007, 'Contenido distinto: {table}, registro ' || p_row);",
                "    END IF;",
                "  END;",
            ]
            calls = [f"  check_row({i}, '{row_digest(row)}');"
                     for i, row in enumerate(rows[start:start+400], start+1)]
            validate.append(block(calls, declarations))
        validate.append(f"PROMPT OK {table}: {len(rows)} registros verificados por SHA-256\n")
    counts += ["  SELECT COUNT(*) INTO v_count FROM STG_SOURCE_FILE;",
               f"  IF v_count <> {len(sources)} THEN RAISE_APPLICATION_ERROR(-20008, 'Archivos adicionales en manifiesto.'); END IF;"]
    validate.insert(3, block(counts, ["  v_count NUMBER;"]))
    validate.append(f"PROMPT OK: {profile['total_rows']} registros, {len(sources)} CSV; contenido verificado.\n")
    install = BANNER + SETTINGS + """PROMPT Creando tablas de staging...
@@01_create_tables.sql
@@02_load_data.sql
@@03_validate_data.sql
COMMIT;
PROMPT Carga confirmada despues de validar todos los registros.
@@04_summary.sql
"""
    summary = BANNER + "SET PAGESIZE 100\nSET LINESIZE 180\nCOLUMN SOURCE_FILE FORMAT A22\nCOLUMN SOURCE_SHA256 FORMAT A64\n" + \
        "SELECT SOURCE_FILE, EXPECTED_ROWS, SOURCE_SHA256 FROM STG_SOURCE_FILE ORDER BY SOURCE_FILE;\n" + \
        "SELECT SUM(EXPECTED_ROWS) AS TOTAL_SOURCE_ROWS FROM STG_SOURCE_FILE;\n"
    return {"00_install.sql": install, "01_create_tables.sql": "\n".join(ddl),
            "02_load_data.sql": "\n".join(load), "03_validate_data.sql": "\n".join(validate),
            "04_summary.sql": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprueba SQL generado sin escribir")
    args = parser.parse_args()
    profile = build_profile()
    recorded = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    if recorded != profile:
        raise SystemExit("Los CSV difieren del manifiesto. Investigue antes de regenerar SQL.")
    files = generate(profile)
    for name, content in files.items():
        path = ROOT / "sql" / name
        raw = content.encode("ascii")
        if args.check:
            if not path.exists() or path.read_bytes() != raw:
                raise SystemExit(f"SQL distinto del CSV/manifiesto: {name}")
        else:
            path.write_bytes(raw)
    print(f"OK: {len(files)} scripts SQL " + ("verificados" if args.check else "generados"))


if __name__ == "__main__":
    main()
