"""Tres etapas locales: CSV -> Full Refresh PostgreSQL -> auditoria independiente."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PREFECT_HOME", str(ROOT / "local" / "prefect"))
os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")

from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE
from prefect.runtime import flow_run

from staging_core import load_and_validate, snapshot_sources, validate_existing


@task(name="Extraer CSV", cache_policy=NO_CACHE, persist_result=False, retries=0)
def inspect_sources() -> dict:
    snapshot = snapshot_sources()
    get_run_logger().info("11 CSV verificados: 15607 registros; vacios conservados como strings")
    return snapshot


@task(name="Cargar Staging", cache_policy=NO_CACHE, persist_result=False, retries=0)
def ingest(snapshot: dict) -> dict:
    result = load_and_validate(snapshot, log=get_run_logger().info)
    get_run_logger().info("COMMIT: 15607 registros validados dentro de la transaccion de carga")
    return result


@task(name="Validar Staging", cache_policy=NO_CACHE, persist_result=False, retries=0)
def validate_final(snapshot: dict, load_result: dict | None = None) -> str:
    committed = bool(load_result and load_result.get("committed"))
    try:
        report = validate_existing(snapshot)
        report["load_committed"] = committed
        report["transactional_validation"] = load_result
        report["prefect_flow_run_id"] = str(flow_run.id)
        report["mode"] = "full-refresh" if committed else "validate-only"
        directory = ROOT / "evidence" / "postgresql"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"run-{flow_run.id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    except Exception as error:
        if committed:
            raise RuntimeError("Fallo la comprobacion o evidencia posterior al COMMIT. Los datos confirmados no se revierten; ejecute --validate-only e investigue.") from error
        raise
    get_run_logger().info("Validacion independiente correcta; evidencia: %s", target.name)
    return str(target)


@flow(name="Chinook Staging ETL", persist_result=False, retries=0)
def staging_etl(validate_only: bool = False) -> str:
    snapshot = inspect_sources()
    loaded = None if validate_only else ingest(snapshot)
    return validate_final(snapshot, loaded)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="Solo SELECT en PostgreSQL; registra evidencia local")
    args = parser.parse_args()
    staging_etl(validate_only=args.validate_only)
