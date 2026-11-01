
"""Prueba que el flujo rechaza Tracks incorrectos."""

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


class TestPrefectTrackValidation(unittest.TestCase):

    def setUp(self):
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
                            "", "", "", "", "", "1.98"
                        ]
                    ]
                },
                TABLE_NAMES["InvoiceLine"]: {
                    "header": [
                        "InvoiceLineId", "InvoiceId",
                        "TrackId", "UnitPrice", "Quantity"
                    ],
                    "rows": [
                        ["1", "1", "1", "0.99", "2"]
                    ]
                },
                TABLE_NAMES["Track"]: {
                    "header": [
                        "TrackId", "Milliseconds",
                        "Bytes", "UnitPrice"
                    ],
                    "rows": [
                        ["1", "240000", "5000000", "0.99"]
                    ]
                }
            }
        }

    def test_extraccion_acepta_track_valido(self):
        with (
            patch.object(
                etl, "snapshot_sources",
                return_value=self.snapshot
            ),
            patch.object(etl, "get_run_logger"),
            redirect_stdout(io.StringIO())
        ):
            resultado = etl.inspect_sources.fn()

        self.assertIs(resultado, self.snapshot)

    def test_track_invalido_bloquea_carga(self):
        tabla = self.snapshot["tables"][TABLE_NAMES["Track"]]

        # Simular una cancion con duracion cero
        tabla["rows"][0][1] = "0"

        extraccion_real = etl.inspect_sources.fn

        with (
            patch.object(
                etl, "snapshot_sources",
                return_value=self.snapshot
            ),
            patch.object(
                etl, "inspect_sources",
                side_effect=extraccion_real
            ),
            patch.object(etl, "get_run_logger"),
            patch.object(etl, "ingest") as cargar,
            patch.object(etl, "validate_final") as validar,
            redirect_stdout(io.StringIO())
        ):
            with self.assertRaisesRegex(ValueError, "Track"):
                etl.staging_etl.fn()

            cargar.assert_not_called()
            validar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
