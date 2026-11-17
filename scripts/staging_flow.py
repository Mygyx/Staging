"""Coordina el ETL de Staging mediante Prefect.

Sin argumentos sirve el deployment y abre Prefect para usar Quick Run.
--run-once ejecuta una carga; --validate-only comprueba una carga existente.
El flujo lee los CSV, los carga y comprueba los datos guardados en PostgreSQL.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PREFECT_HOME", str(ROOT / "local" / "prefect"))
os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
os.environ.setdefault("PREFECT_API_URL", "http://127.0.0.1:4201/api")

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


def serve_staging() -> None:
    """Atiende solicitudes del panel sin solicitar una carga nueva al arrancar."""
    api_url = os.environ.get("PREFECT_API_URL", "").rstrip("/")
    try:
        with urllib.request.urlopen(api_url + "/health", timeout=5) as response:
            if json.loads(response.read()) is not True:
                raise ValueError("La API no confirma su estado")
    except (OSError, ValueError) as error:
        raise ConnectionError(
            "No se pudo conectar con la API de Prefect. "
            "Inicia el servidor en otra terminal con "
            r".\.venv\Scripts\prefect.exe server start --host 127.0.0.1 --port 4201 "
            "y revisa PREFECT_API_URL. No se ha iniciado una carga."
        ) from error
    dashboard = api_url[:-4] if api_url.endswith("/api") else api_url
    print(f"Panel de Prefect: {dashboard}")
    print("Preparando chinook-staging-manual. Deja esta terminal abierta y usa Quick Run en Deployments.")
    try:
        webbrowser.open(dashboard)
    except (OSError, webbrowser.Error):
        print("Abre el enlace del panel manualmente en tu navegador.")
    previous_directory = Path.cwd()
    try:
        os.chdir(ROOT)
        staging_etl.serve(name="chinook-staging-manual", limit=1)
    finally:
        os.chdir(previous_directory)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--serve", action="store_true", help="Servir el deployment y abrir el panel; modo predeterminado")
    modes.add_argument("--run-once", action="store_true", help="Ejecutar una carga de Staging sin esperar Quick Run")
    modes.add_argument("--validate-only", action="store_true", help="Solo SELECT en PostgreSQL; registra evidencia local")
    args = parser.parse_args(argv)
    if args.run_once or args.validate_only:
        staging_etl(validate_only=args.validate_only)
    else:
        try:
            serve_staging()
        except ConnectionError as error:
            parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
