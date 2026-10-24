"""Comprueba configuracion de API sin iniciar servidores ni enviar peticiones."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PrefectAPITests(unittest.TestCase):
    def test_existing_api_is_preserved_without_starting_a_server(self):
        code = '''
import os
from unittest.mock import patch
from prefect.client.orchestration import get_client
from prefect.settings import PREFECT_API_URL
import staging_flow
expected = os.environ["PREFECT_API_URL"]
assert PREFECT_API_URL.value() == expected
with patch("prefect.server.api.server.SubprocessASGIServer.start", side_effect=AssertionError("No se permite otro servidor")) as start, \\
     patch("httpx.Client.send", side_effect=AssertionError("La prueba no envia HTTP")) as send:
    with get_client(sync_client=True) as client:
        assert str(client.api_url).rstrip("/") == expected.rstrip("/")
    start.assert_not_called()
    send.assert_not_called()
'''
        env = dict(os.environ, PREFECT_API_URL="http://127.0.0.1:65534/api",
                   PYTHONDONTWRITEBYTECODE="1", PREFECT_SERVER_ANALYTICS_ENABLED="false",
                   PREFECT_HOME=str(ROOT / "local/prefect"))
        env["PYTHONPATH"] = str(ROOT / "scripts")
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
