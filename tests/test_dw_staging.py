
"""Pruebas de lectura de Staging con conexión simulada."""

import io
import sys
import unittest

from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_dw_staging as adaptador

from check_dw_readiness import verificar_ventas
from staging_core import Settings


class TestLecturaStaging(unittest.TestCase):

    def setUp(self):
        self.settings = Settings(
            host="servidor-de-prueba",
            port=5433,
            database="chinook_staging",
            schema="public",
            user="lector",
            password="clave-ficticia"
        )

        self.facturas = [
            (
                "1", "2", "2026-10-15 00:00:00",
                "", "", "", "", "", "3.97"
            )
        ]

        self.lineas = [
            ("1", "1", "10", "0.99", "2"),
            ("2", "1", "11", "1.99", "1")
        ]

    def crear_conexion_falsa(self):
        conexion = MagicMock()

        conexion.execute.side_effect = [
            SimpleNamespace(fetchall=lambda: self.facturas),
            SimpleNamespace(fetchall=lambda: self.lineas)
        ]

        contexto = MagicMock()
        contexto.__enter__.return_value = conexion

        return conexion, contexto

    def test_lectura_en_solo_lectura(self):
        conexion, contexto = self.crear_conexion_falsa()

        with patch.object(
            adaptador,
            "connect",
            return_value=contexto
        ) as conectar:

            datos = adaptador.leer_ventas_staging(
                self.settings
            )

        conectar.assert_called_once_with(
            self.settings,
            read_only=True
        )

        conexion.transaction.assert_called_once_with()

        consultas = [
            llamada.args[0]
            for llamada in conexion.execute.call_args_list
        ]

        self.assertEqual(len(consultas), 2)
        self.assertTrue(
            all(consulta.startswith("SELECT ") for consulta in consultas)
        )

        self.assertIn('"stg_invoice"', consultas[0])
        self.assertIn('"stg_invoice_line"', consultas[1])

        self.assertEqual(
            datos["Invoice"][0]["InvoiceId"],
            "1"
        )

    def test_ventas_leidas_son_validas(self):
        _, contexto = self.crear_conexion_falsa()

        with patch.object(
            adaptador,
            "connect",
            return_value=contexto
        ):
            registros = adaptador.leer_ventas_staging(
                self.settings
            )

        salida = io.StringIO()

        with redirect_stdout(salida):
            verificar_ventas(registros)

        self.assertIn(
            "Errores encontrados: 0",
            salida.getvalue()
        )

        self.assertIn(
            "Ventas calculadas: 3.97",
            salida.getvalue()
        )

    def test_error_de_lectura(self):
        conexion = MagicMock()
        conexion.execute.side_effect = RuntimeError(
            "lectura fallida"
        )

        contexto = MagicMock()
        contexto.__enter__.return_value = conexion

        with patch.object(
            adaptador,
            "connect",
            return_value=contexto
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "lectura fallida"
            ):
                adaptador.leer_ventas_staging(
                    self.settings
                )


if __name__ == "__main__":
    unittest.main()
