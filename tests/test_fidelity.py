"""Pruebas reales de archivos y parser; nunca modifican los CSV originales."""
import csv
import hashlib
import json
import re
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from profile_sources import HEADERS, TABLE_NAMES, build_profile, read_source, row_digest
from staging_core import (EXPECTED_CONTROLS, ValidationError, load_and_validate,
                          record_controls, snapshot_sources, validate_snapshot)


class FidelityTests(unittest.TestCase):
    def test_all_eleven_original_file_hashes_are_unchanged(self):
        reference = json.loads((ROOT / "tests/source_hashes.json").read_text())
        self.assertEqual(set(reference), {f"{name}.csv" for name in HEADERS})
        for name, expected in reference.items():
            self.assertEqual(hashlib.sha256((ROOT / "data/raw" / name).read_bytes()).hexdigest(), expected, name)

    def test_manifest_and_all_source_controls_match(self):
        profile = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(build_profile(), profile)
        snapshot = snapshot_sources()
        self.assertEqual(record_controls(snapshot["tables"]), EXPECTED_CONTROLS)
        self.assertTrue(all(isinstance(value, str) for table in snapshot["tables"].values()
                            for row in table["rows"] for value in row))

    def test_memory_change_is_rejected_before_opening_a_connection(self):
        snapshot = snapshot_sources()
        snapshot["tables"]["stg_artist"]["rows"][0][1] = "Changed in memory"
        # Este cambio conserva conteos, vacios y todos los controles monetarios.
        self.assertEqual(record_controls(snapshot["tables"]), EXPECTED_CONTROLS)
        with patch("staging_core.connect") as connection:
            with self.assertRaisesRegex(ValidationError, "CSV original"):
                load_and_validate(snapshot)
        connection.assert_not_called()

    def test_snapshot_cannot_relabel_the_original_source_hash(self):
        snapshot = snapshot_sources()
        snapshot["profile"]["sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "manifiesto"):
            validate_snapshot(snapshot)

    def test_changed_monetary_controls_are_rejected(self):
        cases = [("stg_invoice_line", "UnitPrice", Decimal("0.01")),
                 ("stg_invoice_line", "Quantity", Decimal("1")),
                 ("stg_invoice", "Total", Decimal("0.01"))]
        for table, column, increment in cases:
            with self.subTest(table=table, column=column):
                snapshot = snapshot_sources()
                data = snapshot["tables"][table]
                index = data["header"].index(column)
                data["rows"][0][index] = str(Decimal(data["rows"][0][index]) + increment)
                with self.assertRaisesRegex(ValidationError, "controles"):
                    validate_snapshot(snapshot)

    def test_numeric_text_change_is_rejected_without_numeric_inference(self):
        snapshot = snapshot_sources()
        data = snapshot["tables"]["stg_track"]
        index = data["header"].index("Milliseconds")
        data["rows"][0][index] = "0" + data["rows"][0][index]
        self.assertEqual(record_controls(snapshot["tables"]), EXPECTED_CONTROLS)
        with self.assertRaisesRegex(ValidationError, "CSV original"):
            validate_snapshot(snapshot)

    def test_csv_special_values_survive_without_inference_or_normalization(self):
        values = ["", "NULL", "0017", "0.99", "  espacios  ", "O'Brien & Sons",
                  "Luís", "90’s Music", "a,b", 'a"b', "línea\nsegunda\r\ntercera",
                  "C:\\música\\0061", "😀𝄞", "e\u0301", "é"]
        rows = [[str(i), value] for i, value in enumerate(values, 1)]
        with tempfile.TemporaryDirectory(prefix="chinook-csv-fixture-") as directory:
            path = Path(directory) / "Artist.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["ArtistId", "Name"])
                writer.writerows(rows)
            header, loaded, _ = read_source(path)
            self.assertEqual(header, ["ArtistId", "Name"])
            self.assertEqual(loaded, rows)

    def test_malformed_csv_is_rejected(self):
        cases = [(b"bad,header\r\n1,x\r\n", ValueError),
                 (b"ArtistId,Name\r\n1,x,extra\r\n", ValueError),
                 (b"ArtistId,Name\r\n1,\xff\r\n", UnicodeDecodeError),
                 (b"ArtistId,Name\r\n1,\x00\r\n", ValueError),
                 (b'ArtistId,Name\r\n1,"unterminated', csv.Error)]
        with tempfile.TemporaryDirectory(prefix="chinook-csv-invalid-") as directory:
            path = Path(directory) / "Artist.csv"
            for raw, error in cases:
                with self.subTest(error=error.__name__, raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(error):
                        read_source(path)

    def test_hash_preserves_boundaries_empty_strings_spaces_and_unicode(self):
        for left, right in [(["ab", "c"], ["a", "bc"]), (["", "x"], ["x", ""]),
                            (["é"], ["e\u0301"]), (["x"], ["x "]), ([""], ["NULL"])]:
            self.assertNotEqual(row_digest(left), row_digest(right))

    def test_ddl_has_the_complete_original_text_columns(self):
        ddl = (ROOT / "sql/create_staging.sql").read_text(encoding="utf-8")
        definitions = dict(re.findall(r"CREATE TABLE public\.(\w+)\s*\((.*?)\);", ddl, re.DOTALL))
        self.assertEqual(set(definitions), set(TABLE_NAMES.values()) | {"etl_source_file"})
        for source, table in TABLE_NAMES.items():
            definition = definitions[table]
            self.assertRegex(definition, r'"CSV_ROW_NUMBER"\s+INTEGER\s+PRIMARY KEY')
            found = re.findall(r'"([A-Za-z0-9_]+)"\s+TEXT', definition)
            self.assertEqual(found, HEADERS[source].split(","))
        self.assertNotRegex(ddl, r"(?i)\b(VARCHAR|VARCHAR2|NUMBER|DECIMAL|DATE|FOREIGN|TRUNCATE|DROP)\b")


if __name__ == "__main__":
    unittest.main()
