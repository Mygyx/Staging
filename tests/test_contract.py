import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from staging_contract import contract


class ContractTests(unittest.TestCase):
    def test_published_queries_preserve_source_columns_and_requested_names(self):
        profile = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        published = json.loads((ROOT / "contracts/staging_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(contract(profile), published)
        required = {"STG_ALBUM", "STG_ARTIST", "STG_CUSTOMER", "STG_EMPLOYEE", "STG_GENRE",
                    "STG_INVOICE", "STG_INVOICE_LINE", "STG_MEDIA_TYPE", "STG_PLAYLIST",
                    "STG_PLAYLIST_TRACK", "STG_TRACK"}
        self.assertEqual({source["table"] for source in published["sources"]}, required)
        self.assertEqual(sum(s["rows"] for s in published["sources"]), 15607)
        for source in published["sources"]:
            self.assertIn(f"FROM CHINOOK_STAGING.{source['table']}", source["query"])
            self.assertNotIn("SELECT *", source["query"])
            self.assertTrue(source["query"].endswith("ORDER BY CSV_ROW_NUMBER"))
            for column in source["columns"]:
                self.assertIn(f'{column} AS "{column}"', source["query"])


if __name__ == "__main__":
    unittest.main()
