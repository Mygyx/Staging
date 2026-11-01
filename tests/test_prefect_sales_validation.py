
"""Pruebas de validación de ventas antes de cargar Staging."""

import io
import sys
import unittest

from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import staging_flow as etl
from profile_sources import TABLE_NAMES


class TestValidacionPrefect(unittest.TestCase):

    def setUp(self):
        # Datos inventados: no modifican los CSV originales
        self.snapshot = {
            "tables": {
                TABLE_NAMES["Invoice"]: {
                    "header": [
                        "InvoiceId", "CustomerId", "InvoiceDate",
                        "BillingAddress", "BillingCity",
                        "BillingState", "BillingCountry",
                        "BillingPostalCode", "Total"
                    ],
                    "rows": [
                        [
                            "1", "2", "2026-10-15 00:00:00",
                            "", "", "", "", "", "3.97"
                        ]
                    ]
                },
                TABLE_NAMES["InvoiceLine"]: {
                    "header": [
                        "InvoiceLineId", "InvoiceId",
                        "TrackId", "UnitPrice", "Quantity"
                    ],
                    "rows": [
                        ["1", "1", "10", "0.99", "2"],
                        ["2", "1", "11", "1.99", "1"]
                    ]
                }
            }
        }

    def test_factura_correcta_pasa_validacion(self):
        """Una factura correcta debe ser aceptada."""

        salida = io.StringIO()

        with redirect_stdout(salida):
            etl.validar_facturas_snapshot(self.snapshot)

        self.assertIn(
            "Errores encontrados: 0",
            salida.getvalue()
        )

    def test_factura_incorrecta_es_rechazada(self):
        """Un total incorrecto debe detener la validación."""

        tabla = self.snapshot["tables"][
            TABLE_NAMES["Invoice"]
        ]

        tabla["rows"][0][8] = "10.00"

        with redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(
                ValueError,
                "Se detectaron facturas inconsistentes"
            ):
                etl.validar_facturas_snapshot(
                    self.snapshot
                )

    def test_prefect_no_carga_facturas_incorrectas(self):
        """Si falla la validación, no se ejecuta la carga."""

        tabla = self.snapshot["tables"][
            TABLE_NAMES["Invoice"]
        ]

        tabla["rows"][0][8] = "10.00"

        # Función real de extracción, sin iniciar Prefect
        extraer_original = etl.inspect_sources.fn

        with (
            patch.object(
                etl,
                "snapshot_sources",
                return_value=self.snapshot
            ),
            patch.object(
                etl,
                "inspect_sources",
                side_effect=extraer_original
            ),
            patch.object(etl, "get_run_logger"),
            patch.object(etl, "ingest") as cargar,
            patch.object(etl, "validate_final") as validar,
            redirect_stdout(io.StringIO())
        ):

            with self.assertRaisesRegex(
                ValueError,
                "Se detectaron facturas inconsistentes"
            ):
                # Ejecutar lógica del flujo sin servidor Prefect
                etl.staging_etl.fn()

            cargar.assert_not_called()
            validar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
