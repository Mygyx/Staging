"""Comprueba el SQL contra todos los CSV con un decodificador independiente."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from profile_sources import build_profile, read_source, row_digest
from generate_sql import literal

TOKEN = re.compile(r"\s*(NULL|UNISTR\('(?:''|[^'])*'\)|'(?:''|[^'])*'|[0-9]+)\s*(,|$)")
INSERT = re.compile(r"INSERT INTO (STG_\w+|ETL_SOURCE_FILE) \((.*?)\) VALUES \((.*)\);")


def decode_token(token):
    if token == "NULL":
        return ""
    if token.isdecimal():
        return int(token)
    unistr = token.startswith("UNISTR(")
    quoted = token[7:-1] if unistr else token
    value = quoted[1:-1].replace("''", "'")
    if not unistr:
        return value
    result, index = [], 0
    while index < len(value):
        if value[index] != "\\":
            result.append(value[index])
            index += 1
        elif value[index:index+2] == "\\\\":
            result.append("\\")
            index += 2
        else:
            result.append(chr(int(value[index+1:index+5], 16)))
            index += 5
    return "".join(result).encode("utf-16-le", "surrogatepass").decode("utf-16-le")


def decode_values(payload):
    values, position = [], 0
    while position < len(payload):
        match = TOKEN.match(payload, position)
        if match is None:
            raise AssertionError(f"SQL no reconocido en posicion {position}")
        values.append(decode_token(match.group(1)))
        position = match.end()
    return values


class FidelityTests(unittest.TestCase):
    def test_every_generated_value_matches_original_csv(self):
        generated = {}
        sql = (ROOT / "sql" / "02_load_data.sql").read_text(encoding="ascii")
        for line in sql.splitlines():
            if not line.startswith("INSERT INTO "):
                continue
            match = INSERT.fullmatch(line)
            self.assertIsNotNone(match)
            table, columns, payload = match.groups()
            if table == "ETL_SOURCE_FILE":
                continue
            generated.setdefault(table, []).append((columns.split(", "), decode_values(payload)))
        profile = build_profile()
        self.assertEqual(set(generated), {s["table"] for s in profile["sources"]})
        total = 0
        for source in profile["sources"]:
            header, rows, _ = read_source(ROOT / "data" / "raw" / source["file"])
            inserts = generated[source["table"]]
            self.assertEqual(len(inserts), len(rows))
            for number, (original, (columns, decoded)) in enumerate(zip(rows, inserts), 1):
                self.assertEqual(columns, header + ["CSV_ROW_NUMBER"])
                self.assertEqual(decoded, original + [number], (source["file"], number))
            total += len(rows)
        self.assertEqual(total, 15607)

    def test_manifest_matches_original_bytes(self):
        manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(build_profile(), manifest)

    def test_escaped_characters_survive_sql(self):
        values = ["", "NULL", "0012", "1.00", "  espacios  ", "O'Brien & Sons",
                  "Luís", "90’s Music", "a,b", 'a"b', "línea\nsegunda\r\ntercera",
                  "C:\\música\\0061", "\\abcd", "😀𝄞", "e\u0301", "é"]
        for value in values:
            with self.subTest(value=value):
                encoded = literal(value)
                encoded.encode("ascii")
                self.assertEqual(decode_token(encoded), value)

    def test_hash_does_not_confuse_column_boundaries_or_empty_fields(self):
        self.assertNotEqual(row_digest(["ab", "c"]), row_digest(["a", "bc"]))
        self.assertNotEqual(row_digest(["", "x"]), row_digest(["x", ""]))
        self.assertNotEqual(row_digest(["é"]), row_digest(["e\u0301"]))
        self.assertNotEqual(row_digest(["x"]), row_digest(["x "]))

    def test_load_is_one_transaction_and_never_erases_data(self):
        load = (ROOT / "sql" / "02_load_data.sql").read_text(encoding="ascii")
        self.assertNotRegex(load, r"(?im)^\s*(COMMIT|TRUNCATE|DELETE|DROP)\b")
        install = (ROOT / "sql" / "00_install.sql").read_text(encoding="ascii")
        self.assertLess(install.index("@@03_validate_data.sql"), install.index("COMMIT;"))


if __name__ == "__main__":
    unittest.main()
