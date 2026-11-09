
"""Pruebas de seguridad para archivos de configuracion."""

import subprocess
import unittest
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]


class TestSeguridadConfiguracion(unittest.TestCase):

    def test_plantillas_no_contienen_contrasenas_reales(self):
        plantillas = {
            ".env.example": "STG_PASSWORD",
            ".env.reader.example": "STG_PASSWORD",
            ".env.admin.example": "PGPASSWORD",
        }

        for archivo, variable in plantillas.items():
            with self.subTest(archivo=archivo):
                ruta = ROOT / archivo
                self.assertTrue(ruta.is_file())

                valores = dotenv_values(
                    ruta, interpolate=False
                )

                self.assertEqual(
                    valores.get(variable),
                    "CHANGE_ME",
                    f"{archivo} debe utilizar CHANGE_ME"
                )

    def test_roles_staging_no_son_superusuarios(self):
        plantillas = {
            ".env.example": "chinook_stg_loader",
            ".env.reader.example": "chinook_stg_reader",
        }

        for archivo, esperado in plantillas.items():
            with self.subTest(archivo=archivo):
                valores = dotenv_values(
                    ROOT / archivo,
                    interpolate=False
                )

                self.assertEqual(
                    valores.get("STG_USER"),
                    esperado
                )

    def test_archivos_privados_estan_ignorados_por_git(self):
        archivos = [
            ".env",
            ".env.reader",
            ".env.admin"
        ]

        for archivo in archivos:
            with self.subTest(archivo=archivo):
                resultado = subprocess.run(
                    ["git", "check-ignore", "-q", archivo],
                    cwd=ROOT,
                    check=False
                )

                self.assertEqual(
                    resultado.returncode,
                    0,
                    f"{archivo} no esta ignorado por Git"
                )


if __name__ == "__main__":
    unittest.main()
