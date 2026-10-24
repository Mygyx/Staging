"""Pruebas reales opcionales en el esquema dedicado, sin borrar datos."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ENABLED = os.environ.get("RUN_ORACLE_INTEGRATION") == "1"


@unittest.skipUnless(ENABLED, "Defina RUN_ORACLE_INTEGRATION=1 y las variables Oracle")
class OracleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import staging_core
        cls.core = staging_core
        cls.snapshot = staging_core.snapshot_sources()
        staging_core.prepare_tables(cls.snapshot)

    def existing_rows(self):
        with self.core.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM STG_ALBUM")
            return cursor.fetchone()[0]

    def test_rollback_when_validation_fails_after_loading_all_tables(self):
        if self.existing_rows():
            self.skipTest("Requiere tablas vacias; ya existe la carga final")
        with patch.object(self.core, "verify_connection", side_effect=ValueError("Fallo de validacion provocado")):
            with self.assertRaisesRegex(ValueError, "Fallo de validacion provocado"):
                self.core.load_and_validate(self.snapshot, log=lambda message: None)
        with self.core.connect() as connection, connection.cursor() as cursor:
            tables = list(self.snapshot["tables"]) + ["STG_SOURCE_FILE"]
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                self.assertEqual(cursor.fetchone()[0], 0, table)

    def test_validation_detects_changed_accent(self):
        if not self.existing_rows():
            self.skipTest("Requiere la carga final")
        with self.core.connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE STG_CUSTOMER SET FirstName = :1 WHERE CSV_ROW_NUMBER = 1", ["Luis"])
                with self.assertRaisesRegex(ValueError, "Contenido distinto en STG_CUSTOMER"):
                    self.core.verify_connection(connection, self.snapshot)
            finally:
                connection.rollback()
        self.assertEqual(self.core.validate_existing(self.snapshot)["total_rows"], 15607)

    def test_second_load_is_rejected_without_changing_original_data(self):
        if not self.existing_rows():
            self.skipTest("Requiere la carga final")
        with self.assertRaisesRegex(ValueError, "contiene datos"):
            self.core.load_and_validate(self.snapshot, log=lambda message: None)
        self.assertEqual(self.core.validate_existing(self.snapshot)["total_rows"], 15607)

    def test_concurrent_load_is_blocked_before_inserts(self):
        import oracledb
        with self.core.connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("LOCK TABLE STG_ALBUM IN EXCLUSIVE MODE NOWAIT")
                with self.assertRaises(oracledb.DatabaseError) as raised:
                    self.core.load_and_validate(self.snapshot, log=lambda message: None)
                self.assertEqual(raised.exception.args[0].code, 54)
            finally:
                connection.rollback()


if __name__ == "__main__":
    unittest.main()
