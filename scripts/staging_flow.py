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
from profile_sources import TABLE_NAMES
from check_dw_readiness import verificar_ventas
from validate_tracks import validar_tracks_snapshot


def validar_facturas_snapshot(snapshot: dict) -> None:
    """Comprueba las facturas antes de cargar Staging."""

    registros = {}

    for nombre in ("Invoice", "InvoiceLine"):

        nombre_tabla = TABLE_NAMES[nombre]

        tabla = snapshot["tables"][nombre_tabla]

        registros[nombre] = [
            dict(zip(tabla["header"], fila))
            for fila in tabla["rows"]
        ]

    try:
        verificar_ventas(registros)

    except SystemExit as error:
        raise ValueError(
            "Se detectaron facturas inconsistentes. "
            "Se cancela la carga de Staging."
        ) from error




@task(
    name="Extraer CSV",
    cache_policy=NO_CACHE,
    persist_result=False,
    retries=0
)
def inspect_sources() -> dict:

    # Obtener y verificar las fuentes originales
    snapshot = snapshot_sources()

    # Verificar coherencia individual de facturas
    validar_facturas_snapshot(snapshot)

    # Verificar calidad de los datos de Track
    reporte_tracks = validar_tracks_snapshot(snapshot)

    get_run_logger().info(
        f"11 CSV verificados. "
        f"Facturas correctas. "
        f"{reporte_tracks['tracks_revisados']} tracks validados."
    )

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
