"""Pruebas reales de archivos y parser; nunca modifican los CSV originales."""
import csv
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from profile_sources import HEADERS, TABLE_NAMES, build_profile, read_source, row_digest
from staging_core import EXPECTED_CONTROLS, record_controls, snapshot_sources


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
