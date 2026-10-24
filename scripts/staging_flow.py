"""Flujo Prefect: CSV originales -> tablas staging Oracle -> evidencia."""
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

from staging_core import load_and_validate, prepare_tables, snapshot_sources, validate_existing


@task(name="Verificar CSV contra manifiesto", cache_policy=NO_CACHE, persist_result=False, retries=0)
def inspect_sources() -> dict:
    snapshot = snapshot_sources()
    get_run_logger().info("11 CSV verificados: %s registros", snapshot["profile"]["total_rows"])
    return snapshot


@task(name="Preparar tablas Oracle", cache_policy=NO_CACHE, persist_result=False, retries=0)
def provision(snapshot: dict) -> str:
    result = prepare_tables(snapshot)
    get_run_logger().info(result)
    return result


@task(name="Cargar y validar antes de COMMIT", cache_policy=NO_CACHE, persist_result=False, retries=0)
def ingest(snapshot: dict) -> dict:
    logger = get_run_logger()
    evidence = load_and_validate(snapshot, log=logger.info)
    logger.info("COMMIT: %s registros comparados campo por campo", evidence["total_rows"])
    return evidence


@task(name="Revisar staging existente", cache_policy=NO_CACHE, persist_result=False, retries=0)
def audit(snapshot: dict) -> dict:
    return validate_existing(snapshot)


@task(name="Guardar evidencia", cache_policy=NO_CACHE, persist_result=False, retries=0)
def save_evidence(evidence: dict) -> str:
    evidence["prefect_flow_run_id"] = str(flow_run.id)
    target = ROOT / "evidence" / f"run-{flow_run.id}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    get_run_logger().info("Evidencia: %s", target.name)
    return str(target)


@flow(name="Invacom - staging CSV a Oracle", persist_result=False, retries=0)
def staging_oracle(validate_only: bool = False) -> str:
    snapshot = inspect_sources()
    if validate_only:
        evidence = audit(snapshot)
    else:
        provision(snapshot)
        evidence = ingest(snapshot)
    return save_evidence(evidence)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="Solo comparar; no crea ni carga")
    args = parser.parse_args()
    staging_oracle(validate_only=args.validate_only)
