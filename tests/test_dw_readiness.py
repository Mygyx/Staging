import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# pyrefly: ignore[missing-import]
import check_dw_readiness as validador




class TestDWReadiness(unittest.TestCase):

    def setUp(self):
        self.facturas = [{
            "InvoiceId": "1",
            "InvoiceDate": "2026-10-15 00:00:00",
            "Total": "3.97"
        }]

        self.lineas = [
            {
                "InvoiceLineId": "1",
                "InvoiceId": "1",
                "Quantity": "2",
                "UnitPrice": "0.99"
            },
            {
                "InvoiceLineId": "2",
                "InvoiceId": "1",
                "Quantity": "1",
                "UnitPrice": "1.99"
            }
        ]

    def ejecutar(self):
        def datos_simulados(nombre):
            return (
                self.facturas
                if nombre == "Invoice"
                else self.lineas
            )

        salida = io.StringIO()

        with patch.object(
            validador,
            "obtener_registros",
            side_effect=datos_simulados
        ), redirect_stdout(salida):

            try:
                validador.verificar_ventas()
                codigo = 0
            except SystemExit as error:
                codigo = error.code

        return codigo, salida.getvalue()

    def test_factura_correcta(self):
        codigo, resultado = self.ejecutar()

        self.assertEqual(codigo, 0)
        self.assertIn("Errores encontrados: 0", resultado)

    def test_total_incorrecto(self):
        self.facturas[0]["Total"] = "10.00"

        codigo, resultado = self.ejecutar()

        self.assertEqual(codigo, 1)
        self.assertIn("calculado 3.97", resultado)

    def test_precio_no_numerico(self):
        self.lineas[0]["UnitPrice"] = "abc"

        codigo, resultado = self.ejecutar()

        self.assertEqual(codigo, 1)
        self.assertIn("ERROR", resultado)

    def test_cantidad_negativa(self):
        self.lineas[0]["Quantity"] = "-2"

        codigo, resultado = self.ejecutar()

        self.assertEqual(codigo, 1)
        self.assertIn("Cantidad o precio inválido", resultado)

    def test_fecha_invalida(self):
        self.facturas[0]["InvoiceDate"] = "2026-99-99"

        codigo, resultado = self.ejecutar()

        self.assertEqual(codigo, 1)
        self.assertIn("Factura 1", resultado)

    def test_factura_inexistente(self):
        self.lineas[0]["InvoiceId"] = "999"

        codigo, resultado = self.ejecutar()

        self.assertEqual(codigo, 1)
        self.assertIn("factura inexistente", resultado)


if __name__ == "__main__":
    unittest.main()
