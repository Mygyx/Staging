"""Integracion optativa: solo esquemas unicos y expresamente autorizados de pruebas.

Nunca borra ni corrompe tablas de public. Requiere una base marcada del proyecto.
"""
import os
import json
import hashlib
import sys
import tempfile
import unittest
import uuid
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import staging_core as core
from profile_sources import TABLE_NAMES
from staging_contract import verify_reader

ENABLED = os.environ.get("RUN_PG_INTEGRATION") == "1"
AUTHORIZED = os.environ.get("STG_TEST_SCHEMA_AUTHORIZED") == "1"


@unittest.skipUnless(ENABLED and AUTHORIZED,
                    "Pendiente: requiere RUN_PG_INTEGRATION=1, STG_TEST_SCHEMA_AUTHORIZED=1 y credenciales PostgreSQL")
class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = core.Settings.from_env()
        cls.snapshot = core.snapshot_sources()
        with core.connect(cls.loader) as connection, connection.transaction():
            core.check_environment(connection, cls.loader)
        if cls.loader.schema != "public":
            raise core.SafetyError("Las pruebas esperan la configuracion normal public y crean sus propios esquemas aislados.")
        cls.public_before = cls.public_fingerprint()

    @classmethod
    def public_fingerprint(cls):
        records = {}
        with core.connect(cls.loader, read_only=True) as connection, connection.transaction():
            for table in list(TABLE_NAMES.values()) + [core.CATALOG]:
                order = "source_file" if table == core.CATALOG else "CSV_ROW_NUMBER"
                records[table] = connection.execute(sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                    sql.Identifier("public", table), sql.Identifier(order))).fetchall()
        return hashlib.sha256(json.dumps(records, ensure_ascii=True, sort_keys=True).encode()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        if cls.public_fingerprint() != cls.public_before:
            raise AssertionError("Las pruebas modificaron public; la ejecucion no se acepta.")

    def setUp(self):
        self.schema = "stg_test_" + uuid.uuid4().hex[:20]
        self.token = "chinook_staging_etl:test:" + uuid.uuid4().hex
        self.settings = replace(self.loader, schema=self.schema)
        with core.connect(self.loader) as connection, connection.transaction():
            if connection.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (self.schema,)).fetchone():
                self.fail("El nombre aleatorio ya existe; no se adopta el esquema.")
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
            connection.execute(sql.SQL("COMMENT ON SCHEMA {} IS {}").format(sql.Identifier(self.schema), sql.Literal(self.token)))
        self.addCleanup(self.cleanup_owned_schema)

    def cleanup_owned_schema(self):
        if not self.schema.startswith("stg_test_") or self.schema == "public":
            raise core.SafetyError("Se rechazo la limpieza de un esquema no aislado.")
        with core.connect(self.loader) as connection, connection.transaction():
            marker = connection.execute("SELECT obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname=%s",
                                        (self.schema,)).fetchone()
            if marker is None:
                return
            if marker[0] != self.token:
                raise core.SafetyError("La propiedad del esquema de pruebas cambio; no se elimina.")
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))

    def load(self, **kwargs):
        return core.load_and_validate(self.snapshot, self.settings, log=kwargs.get("log", lambda message: None))

    def dump(self):
        result = {}
        with core.connect(self.settings, read_only=True) as connection, connection.transaction():
            for table in list(TABLE_NAMES.values()) + [core.CATALOG]:
                order = "source_file" if table == core.CATALOG else "CSV_ROW_NUMBER"
                result[table] = connection.execute(sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                    sql.Identifier(self.schema, table), sql.Identifier(order))).fetchall()
        return result

    def previous_photo(self):
        self.load()
        with core.connect(self.settings) as connection, connection.transaction():
            connection.execute(sql.SQL('UPDATE {} SET "Name"=%s WHERE "CSV_ROW_NUMBER"=1').format(
                sql.Identifier(self.schema, "stg_artist")), ("Previous test snapshot",))
        return self.dump()

    def test_first_load_and_actual_structure(self):
        result = self.load()
        self.assertTrue(result["committed"])
        self.assertEqual(result["controls"], core.EXPECTED_CONTROLS)
        self.assertTrue(result["catalog_matches_manifest"])
        with core.connect(self.settings, read_only=True) as connection, connection.transaction():
            core.check_table_shapes(connection, self.snapshot["profile"], self.settings)

    def test_second_full_refresh_does_not_duplicate(self):
        self.load()
        before = self.dump()
        self.load()
        self.assertEqual(self.dump(), before)

    def test_failed_validation_restores_previous_photo_not_empty_tables(self):
        previous = self.previous_photo()
        with patch.object(core, "verify_connection", side_effect=core.ValidationError("Deliberate test failure")):
            with self.assertRaises(core.ValidationError):
                self.load()
        self.assertEqual(self.dump(), previous)

    def test_error_during_load_restores_previous_photo(self):
        previous = self.previous_photo()
        def fail_after_first_table(message):
            raise RuntimeError("Deliberate insertion failure")
        with self.assertRaisesRegex(RuntimeError, "Deliberate insertion failure"):
            self.load(log=fail_after_first_table)
        self.assertEqual(self.dump(), previous)

    def duplicate_ordinal_insert(self):
        insert = core.insert_snapshot
        def duplicate(connection, snapshot, settings, log):
            result = insert(connection, snapshot, settings, log)
            # INSERT real sobre nuestra tabla de pruebas: la PK 1 ya existe.
            connection.execute(sql.SQL('INSERT INTO {} ("CSV_ROW_NUMBER") VALUES (%s)').format(
                sql.Identifier(settings.schema, "stg_artist")), (1,))
            return result
        return duplicate

    def test_real_sql_insert_error_restores_previous_photo(self):
        previous = self.previous_photo()
        with patch.object(core, "insert_snapshot", side_effect=self.duplicate_ordinal_insert()):
            with self.assertRaises(psycopg.errors.UniqueViolation) as raised:
                self.load()
        self.assertEqual(raised.exception.sqlstate, "23505")
        self.assertEqual(self.dump(), previous)

    def test_memory_change_during_load_is_rejected_before_commit(self):
        previous = self.previous_photo()
        snapshot = deepcopy(self.snapshot)
        insert = core.insert_snapshot
        def change_memory(connection, loaded, settings, log):
            result = insert(connection, loaded, settings, log)
            loaded["tables"]["stg_artist"]["rows"][0][1] = "Changed after insertion"
            return result
        with patch.object(core, "insert_snapshot", side_effect=change_memory):
            with self.assertRaisesRegex(core.ValidationError, "CSV original"):
                core.load_and_validate(snapshot, self.settings, log=lambda message: None)
        self.assertEqual(self.dump(), previous)

    def test_corrupted_price_is_detected_and_rolled_back(self):
        previous = self.previous_photo()
        insert = core.insert_snapshot
        def corrupted(connection, snapshot, settings, log):
            result = insert(connection, snapshot, settings, log)
            connection.execute(sql.SQL('UPDATE {} SET "UnitPrice"=%s WHERE "CSV_ROW_NUMBER"=1').format(
                sql.Identifier(self.schema, "stg_invoice_line")), ("0.00",))
            return result
        with patch.object(core, "insert_snapshot", side_effect=corrupted):
            with self.assertRaisesRegex(core.ValidationError, "Contenido u ordinal distinto"):
                self.load()
        self.assertEqual(self.dump(), previous)

    def test_corrupted_test_value_is_detected_before_commit(self):
        previous = self.previous_photo()
        insert = core.insert_snapshot
        def corrupted(connection, snapshot, settings, log):
            result = insert(connection, snapshot, settings, log)
            connection.execute(sql.SQL('UPDATE {} SET "FirstName"=%s WHERE "CSV_ROW_NUMBER"=1').format(
                sql.Identifier(self.schema, "stg_customer")), ("Luis",))
            return result
        with patch.object(core, "insert_snapshot", side_effect=corrupted):
            with self.assertRaisesRegex(core.ValidationError, "Contenido u ordinal distinto"):
                self.load()
        self.assertEqual(self.dump(), previous)

    def customer_value(self, column, number):
        with core.connect(self.settings, read_only=True) as connection, connection.transaction():
            return connection.execute(sql.SQL('SELECT {} FROM {} WHERE "CSV_ROW_NUMBER"=%s').format(
                sql.Identifier(column), sql.Identifier(self.schema, "stg_customer")), (number,)).fetchone()[0]

    def test_empty_strings_are_not_null(self):
        self.load()
        self.assertEqual(self.customer_value("Company", 2), "")
        with core.connect(self.settings, read_only=True) as connection, connection.transaction():
            for source in self.snapshot["profile"]["sources"]:
                for column in source["columns"]:
                    count = connection.execute(sql.SQL("SELECT count(*) FROM {} WHERE {} IS NULL").format(
                        sql.Identifier(self.schema, source["table"]), sql.Identifier(column["name"]))).fetchone()[0]
                    self.assertEqual(count, 0)

    def test_unicode_survives(self):
        self.load()
        self.assertEqual(self.customer_value("FirstName", 1), "Luís")

    def test_trailing_spaces_survive(self):
        self.load()
        expected = self.snapshot["tables"]["stg_customer"]["rows"][53][5]
        self.assertTrue(expected.endswith(" "))
        self.assertEqual(self.customer_value("City", 54), expected)

    def test_leading_zeros_survive(self):
        self.load()
        data = self.snapshot["tables"]["stg_customer"]
        index = data["header"].index("PostalCode")
        found = 0
        for number, row in enumerate(data["rows"], 1):
            if row[index].isdigit() and row[index].startswith("0"):
                self.assertEqual(self.customer_value("PostalCode", number), row[index])
                found += 1
        self.assertEqual(found, 3)

    def test_unexpected_column_type_is_rejected_without_refresh(self):
        self.load()
        with core.connect(self.settings) as connection, connection.transaction():
            connection.execute(sql.SQL('ALTER TABLE {} ALTER COLUMN "Title" TYPE VARCHAR(95)').format(
                sql.Identifier(self.schema, "stg_album")))
        before = self.dump()
        with self.assertRaisesRegex(core.ValidationError, "Estructura inesperada"):
            self.load()
        self.assertEqual(self.dump(), before)

    def test_concurrent_refresh_is_rejected_without_data_changes(self):
        self.load()
        before = self.dump()
        with core.connect(self.settings) as connection, connection.transaction():
            core.acquire_refresh_lock(connection, self.settings)
            with self.assertRaises(core.ConcurrentRefreshError):
                self.load()
        self.assertEqual(self.dump(), before)

    def test_repeatable_read_retains_previous_snapshot_during_refresh(self):
        previous = self.previous_photo()
        query = sql.SQL('SELECT "Name" FROM {} WHERE "CSV_ROW_NUMBER"=1').format(sql.Identifier(self.schema, "stg_artist"))
        with core.connect(self.settings, read_only=True) as connection, connection.transaction():
            old = connection.execute(query).fetchone()[0]
            self.load()
            self.assertEqual(connection.execute(query).fetchone()[0], old)
        with core.connect(self.settings, read_only=True) as connection, connection.transaction():
            self.assertEqual(connection.execute(query).fetchone()[0], self.snapshot["tables"]["stg_artist"]["rows"][0][1])

    def test_prefect_flow_completes_using_only_the_isolated_schema(self):
        import staging_flow
        with tempfile.TemporaryDirectory(prefix="chinook-prefect-evidence-") as directory:
            with patch.object(core.Settings, "from_env", return_value=self.settings), \
                 patch.object(staging_flow, "ROOT", Path(directory)):
                target = staging_flow.staging_etl()
            report = json.loads(Path(target).read_text(encoding="utf-8"))
            self.assertTrue(report["load_committed"])
            self.assertEqual(report["schema"], self.schema)
            self.assertEqual(report["controls"], core.EXPECTED_CONTROLS)

    def test_prefect_task_and_flow_fail_on_real_sql_error(self):
        import staging_flow
        previous = self.previous_photo()
        observed = []
        def capture_failure(task, task_run, state):
            observed.append({"task_name": task_run.name, "task_state": state.name,
                             "task_run_id": str(task_run.id), "flow_run_id": str(task_run.flow_run_id)})
        failing_task = staging_flow.ingest.with_options(on_failure=[capture_failure])
        with tempfile.TemporaryDirectory(prefix="chinook-prefect-failure-") as directory:
            with patch.object(core.Settings, "from_env", return_value=self.settings), \
                 patch.object(staging_flow, "ROOT", Path(directory)), \
                 patch.object(staging_flow, "ingest", failing_task), \
                 patch.object(core, "insert_snapshot", side_effect=self.duplicate_ordinal_insert()):
                state = staging_flow.staging_etl(return_state=True)
            self.assertTrue(state.is_failed())
            with self.assertRaises(psycopg.errors.UniqueViolation) as raised:
                state.result()
            self.assertEqual(raised.exception.sqlstate, "23505")
            self.assertEqual(list(Path(directory).rglob("run-*.json")), [])
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["task_state"], "Failed")
        self.assertEqual(observed[0]["flow_run_id"], str(state.state_details.flow_run_id))
        self.assertEqual(self.dump(), previous)
        print("\nPREFECT_EXPECTED_FAILURE " + json.dumps({
            **observed[0], "flow_state": state.name, "sqlstate": "23505",
            "schema": self.schema, "rollback_matches_previous": True}), flush=True)

    def reader_settings(self):
        try:
            reader = replace(core.Settings.from_env(ROOT / ".env.reader", use_environment=False), schema=self.schema)
        except core.ConfigurationError:
            self.skipTest("Pendiente: credenciales del lector en .env.reader")
        if reader.user == self.loader.user:
            self.fail("El lector debe ser un usuario distinto del cargador.")
        with core.connect(self.settings) as connection, connection.transaction():
            connection.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(self.schema), sql.Identifier(reader.user)))
            for table in TABLE_NAMES.values():
                connection.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
                    sql.Identifier(self.schema, table), sql.Identifier(reader.user)))
        return reader

    def test_reader_can_query_all_source_values(self):
        self.load()
        report = verify_reader(self.reader_settings(), self.snapshot)
        self.assertTrue(report["source_tables_read_only"])
        self.assertEqual(report["reader_permission_scope"]["source_tables_checked"], list(TABLE_NAMES.values()))
        self.assertIsInstance(report["database_temp_privilege"], bool)
        self.assertIn("session-local", report["temp_policy"])
        self.assertEqual(report["controls"], core.EXPECTED_CONTROLS)

    def test_reader_cannot_insert_update_or_delete(self):
        self.load()
        reader = self.reader_settings()
        before = self.dump()
        statements = [sql.SQL('UPDATE {} SET "Name"=%s WHERE "CSV_ROW_NUMBER"=1'),
                      sql.SQL('DELETE FROM {} WHERE "Name"=%s'),
                      sql.SQL('INSERT INTO {} ("CSV_ROW_NUMBER","ArtistId","Name") VALUES (99999,\'test\',%s)')]
        with core.connect(reader) as connection:
            for statement in statements:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        connection.execute(statement.format(sql.Identifier(self.schema, "stg_artist")), ("test-write",))
        self.assertEqual(self.dump(), before)

    def test_reader_verifier_rejects_column_update_granted_in_test_schema(self):
        self.load()
        reader = self.reader_settings()
        relation = sql.Identifier(self.schema, "stg_artist")
        with core.connect(self.settings) as connection, connection.transaction():
            connection.execute(sql.SQL("GRANT UPDATE ({}) ON {} TO {}").format(
                sql.Identifier("Name"), relation, sql.Identifier(reader.user)))
            table_grant, column_grant = connection.execute("SELECT "
                "has_table_privilege(%s,%s,'UPDATE'),has_any_column_privilege(%s,%s,'UPDATE')",
                (reader.user, relation.as_string(), reader.user, relation.as_string())).fetchone()
        self.assertFalse(table_grant)
        self.assertTrue(column_grant)
        before = self.dump()
        with self.assertRaisesRegex(core.SafetyError, "UPDATE.*columna"):
            verify_reader(reader, self.snapshot)
        self.assertEqual(self.dump(), before)


if __name__ == "__main__":
    unittest.main()
