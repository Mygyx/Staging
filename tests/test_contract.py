import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from staging_contract import contract, source_query


class ContractTests(unittest.TestCase):
    def test_contract_matches_requested_postgresql_interface(self):
        profile = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        published = json.loads((ROOT / "contracts/staging_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(contract(profile), published)
        required = {"stg_album", "stg_artist", "stg_customer", "stg_employee", "stg_genre",
                    "stg_invoice", "stg_invoice_line", "stg_media_type", "stg_playlist",
                    "stg_playlist_track", "stg_track"}
        self.assertEqual({source["table"] for source in published["sources"]}, required)
        self.assertEqual(published["engine"], "PostgreSQL")
        self.assertEqual(published["database"], "chinook_staging")
        self.assertEqual(published["schema"], "public")
        self.assertEqual(sum(s["rows"] for s in published["sources"]), 15607)
        for source in published["sources"]:
            self.assertIn(f'FROM "public"."{source["table"]}"', source["query"])
            self.assertNotIn("SELECT *", source["query"])
            self.assertTrue(source["query"].endswith('ORDER BY "CSV_ROW_NUMBER"'))
            projection = source["query"].split(" FROM ")[0]
            self.assertNotIn("CSV_ROW_NUMBER", projection)
            for column in source["columns"]:
                self.assertIn(f'"{column}"', projection)

    def test_query_uses_escaped_identifiers(self):
        query = source_query("Customer", 'schema"with_quote')
        self.assertIn('"schema""with_quote"."stg_customer"', query)
        with self.assertRaises(KeyError):
            source_query("Customer; DELETE")


if __name__ == "__main__":
    unittest.main()
