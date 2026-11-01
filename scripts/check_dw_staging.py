
"""Valida las ventas almacenadas en PostgreSQL Staging.

La conexión es únicamente de lectura.
No modifica ninguna tabla.
"""

from profile_sources import HEADERS, ROOT
from staging_contract import source_query
from staging_core import Settings, connect
from check_dw_readiness import verificar_ventas


def leer_ventas_staging(settings=None):
    """Lee facturas y detalles en una sola transacción."""

    settings = settings or Settings.from_env(
        ROOT / ".env.reader"
    )

    resultado = {}

    # Reutilizar la conexión segura del proyecto
    with connect(settings, read_only=True) as conexion:

        # Ambas tablas se consultan en la misma transacción
        with conexion.transaction():

            for nombre in ("Invoice", "InvoiceLine"):

                columnas = HEADERS[nombre].split(",")

                consulta = source_query(
                    nombre,
                    settings.schema
                )

                filas = conexion.execute(consulta).fetchall()

                resultado[nombre] = [
                    dict(zip(columnas, fila))
                    for fila in filas
                ]

    return resultado


def main():
    registros = leer_ventas_staging()

    print("Origen: PostgreSQL Staging (solo lectura)")

    verificar_ventas(registros)


if __name__ == "__main__":
    main()
