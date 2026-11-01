
"""Pruebas de calidad para los datos de Track."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from profile_sources import TABLE_NAMES
from validate_tracks import validar_tracks, validar_tracks_snapshot


class TestValidacionTracks(unittest.TestCase):

    def setUp(self):
        self.registros = [
            {
                "TrackId": "1",
                "Milliseconds": "240000",
                "Bytes": "5000000",
                "UnitPrice": "0.99"
            },
            {
                "TrackId": "2",
                "Milliseconds": "180000",
                "Bytes": "4000000",
                "UnitPrice": "1.99"
            }
        ]

    def test_tracks_correctos(self):
        resultado = validar_tracks(self.registros)

        self.assertEqual(resultado["tracks_revisados"], 2)
        self.assertEqual(resultado["errores"], 0)

    def test_bytes_vacios_permitidos(self):
        self.registros[0]["Bytes"] = ""

        resultado = validar_tracks(self.registros)

        self.assertEqual(resultado["bytes_vacios"], 1)

    def test_id_duplicado(self):
        self.registros[1]["TrackId"] = "1"

        with self.assertRaisesRegex(ValueError, "ID duplicado"):
            validar_tracks(self.registros)

    def test_id_invalido(self):
        self.registros[0]["TrackId"] = "0"

        with self.assertRaisesRegex(ValueError, "ID no positivo"):
            validar_tracks(self.registros)

    def test_duracion_invalida(self):
        for valor in ("0", "-100", "abc"):
            with self.subTest(valor=valor):
                self.registros[0]["Milliseconds"] = valor

                with self.assertRaisesRegex(
                    ValueError, "duracion invalida"
                ):
                    validar_tracks(self.registros)

    def test_precio_invalido(self):
        for valor in ("abc", "-1.99", "NaN", "Infinity"):
            with self.subTest(valor=valor):
                self.registros[0]["UnitPrice"] = valor

                with self.assertRaisesRegex(
                    ValueError, "precio invalido"
                ):
                    validar_tracks(self.registros)

    def test_bytes_invalidos(self):
        for valor in ("abc", "-500"):
            with self.subTest(valor=valor):
                self.registros[0]["Bytes"] = valor

                with self.assertRaisesRegex(
                    ValueError, "Bytes invalido"
                ):
                    validar_tracks(self.registros)

    def test_validar_desde_snapshot(self):
        encabezados = list(self.registros[0].keys())

        snapshot = {
            "tables": {
                TABLE_NAMES["Track"]: {
                    "header": encabezados,
                    "rows": [
                        [registro[col] for col in encabezados]
                        for registro in self.registros
                    ]
                }
            }
        }

        resultado = validar_tracks_snapshot(snapshot)

        self.assertEqual(resultado["tracks_revisados"], 2)


if __name__ == "__main__":
    unittest.main()
