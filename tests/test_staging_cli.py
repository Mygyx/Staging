"""Comprueba que Run prepara el servicio y solo las opciones explícitas cargan.

Intercepta Prefect, HTTP, navegador y PostgreSQL: no inicia servidores ni flujos.
"""
import contextlib
import io
import os
import runpy
import sys
import tempfile
import unittest
import urllib.error
import webbrowser
from pathlib import Path
from unittest.mock import patch

from prefect.flows import Flow

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class StagingCLITests(unittest.TestCase):
    def invoke(self, arguments=(), *, offline=False, browser_error=False, api_url="http://127.0.0.1:65534/api"):
        calls = []

        def run(flow, *args, **kwargs):
            calls.append(("run", flow.name, kwargs))

        def serve(flow, *args, **kwargs):
            self.assertEqual(Path.cwd(), ROOT)
            calls.append(("serve", flow.name, kwargs))

        with patch.object(Flow, "__call__", run), \
             patch.object(Flow, "serve", serve), \
             patch("urllib.request.urlopen") as health, \
             patch("webbrowser.open") as browser, \
             patch("psycopg.connect", side_effect=AssertionError("No se permiten conexiones a PostgreSQL")), \
             patch("httpx.Client.send", side_effect=AssertionError("No se permiten peticiones de Prefect")), \
             patch.object(sys, "argv", [str(ROOT / "scripts/staging_flow.py"), *arguments]), \
             patch.dict(os.environ, {"PREFECT_API_URL": api_url or ""}), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if api_url is None:
                os.environ.pop("PREFECT_API_URL", None)
            health.return_value.__enter__.return_value.read.return_value = b"true"
            if offline:
                health.side_effect = urllib.error.URLError("offline")
            if browser_error:
                browser.side_effect = webbrowser.Error("sin navegador")
            code = 0
            try:
                runpy.run_path(str(ROOT / "scripts/staging_flow.py"), run_name="__main__")
            except SystemExit as error:
                code = error.code
            return calls, code, browser.call_args_list, health.call_args_list

    def test_run_del_editor_sirve_staging_sin_ejecutar_la_carga(self):
        calls, code, browser, health = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("serve", "Chinook Staging ETL", {"name": "chinook-staging-manual", "limit": 1})])
        self.assertEqual(browser[0].args, ("http://127.0.0.1:65534",))
        self.assertEqual(health[0].args, ("http://127.0.0.1:65534/api/health",))

    def test_serve_explicito_solo_prepara_el_deployment(self):
        calls, code, _, _ = self.invoke(["--serve"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("serve", "Chinook Staging ETL", {"name": "chinook-staging-manual", "limit": 1})])

    def test_editor_sin_variable_de_api_usa_el_servidor_local_4201(self):
        calls, code, browser, health = self.invoke(api_url=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls[0][0], "serve")
        self.assertEqual(health[0].args, ("http://127.0.0.1:4201/api/health",))
        self.assertEqual(browser[0].args, ("http://127.0.0.1:4201",))

    def test_serve_usa_la_carpeta_del_proyecto_desde_otro_directorio(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory(prefix="staging-cli-") as directory:
            try:
                os.chdir(directory)
                calls, code, _, _ = self.invoke()
                self.assertEqual(code, 0)
                self.assertEqual(calls[0][0], "serve")
                self.assertEqual(Path.cwd(), Path(directory))
            finally:
                os.chdir(previous)

    def test_run_once_solo_inicia_la_carga_de_staging(self):
        calls, code, browser, _ = self.invoke(["--run-once"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("run", "Chinook Staging ETL", {"validate_only": False})])
        self.assertFalse(browser)

    def test_validate_only_se_conserva_y_no_arranca_un_servicio(self):
        calls, code, browser, _ = self.invoke(["--validate-only"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("run", "Chinook Staging ETL", {"validate_only": True})])
        self.assertFalse(browser)

    def test_opciones_contradictorias_no_ejecutan_ni_sirven(self):
        for arguments in (["--serve", "--run-once"], ["--serve", "--validate-only"], ["--run-once", "--validate-only"]):
            with self.subTest(arguments=arguments):
                calls, code, browser, health = self.invoke(arguments)
                self.assertEqual(code, 2)
                self.assertFalse(calls or browser or health)

    def test_api_apagada_no_abre_el_navegador_ni_ejecuta_el_etl(self):
        calls, code, browser, _ = self.invoke(offline=True)
        self.assertEqual(code, 2)
        self.assertFalse(calls or browser)

    def test_fallo_del_navegador_no_impide_servir_el_deployment(self):
        calls, code, _, _ = self.invoke(browser_error=True)
        self.assertEqual(code, 0)
        self.assertEqual(calls[0][0], "serve")

    def test_help_no_consulta_la_api_ni_arranca_nada(self):
        calls, code, browser, health = self.invoke(["--help"])
        self.assertEqual(code, 0)
        self.assertFalse(calls or browser or health)


if __name__ == "__main__":
    unittest.main()
