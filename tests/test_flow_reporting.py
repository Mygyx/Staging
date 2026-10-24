"""Comprueba la separacion entre transaccion y evidencia; sin servidor ni BD."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import staging_flow
from staging_core import ValidationError


class FlowReportingTests(unittest.TestCase):
    def test_failure_after_commit_is_not_described_as_a_rollback(self):
        with patch.object(staging_flow, "validate_existing", side_effect=ValidationError("test mismatch")):
            with self.assertRaisesRegex(RuntimeError, "Los datos confirmados no se revierten"):
                staging_flow.validate_final.fn({}, {"committed": True})

    def test_validate_only_failure_keeps_original_validation_error(self):
        with patch.object(staging_flow, "validate_existing", side_effect=ValidationError("test mismatch")):
            with self.assertRaises(ValidationError):
                staging_flow.validate_final.fn({}, None)

    def test_evidence_distinguishes_precommit_and_postcommit_verification(self):
        with tempfile.TemporaryDirectory(prefix="chinook-flow-report-") as directory:
            with patch.object(staging_flow, "ROOT", Path(directory)), \
                 patch.object(staging_flow, "flow_run", SimpleNamespace(id="unit-test")), \
                 patch.object(staging_flow, "get_run_logger", return_value=Mock()), \
                 patch.object(staging_flow, "validate_existing", return_value={"phase": "read-only"}):
                target = staging_flow.validate_final.fn({}, {"committed": True, "phase": "validated-before-commit"})
            report = json.loads(Path(target).read_text(encoding="utf-8"))
            self.assertTrue(report["load_committed"])
            self.assertEqual(report["transactional_validation"]["phase"], "validated-before-commit")
            self.assertEqual(report["phase"], "read-only")
            self.assertEqual(list(Path(directory).rglob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
