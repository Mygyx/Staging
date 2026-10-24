import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from provision_postgres import guard_target
from staging_core import SafetyError, Settings


class ProvisionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.loader = Settings("localhost", 5433, "chinook_staging", "public", "chinook_stg_loader", "test")
        self.reader = Settings("localhost", 5433, "chinook_staging", "public", "chinook_stg_reader", "test")

    def test_unknown_existing_database_is_never_adopted(self):
        report = {"server_version_num": 170004, "databases": [{"name": "chinook_staging", "owner": "someone_else", "marked_for_this_project": False}]}
        with self.assertRaises(SafetyError):
            guard_target(report, self.loader, self.reader)

    def test_instance_with_the_dw_is_rejected(self):
        report = {"server_version_num": 170004, "databases": [{"name": "chinook_dw"}]}
        with self.assertRaisesRegex(SafetyError, "separacion"):
            guard_target(report, self.loader, self.reader)

    def test_postgresql_12_is_not_used_as_fallback(self):
        with self.assertRaises(SafetyError):
            guard_target({"server_version_num": 120022, "databases": []}, self.loader, self.reader)


if __name__ == "__main__":
    unittest.main()
