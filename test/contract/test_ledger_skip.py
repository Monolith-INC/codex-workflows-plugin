import tempfile
import unittest
from pathlib import Path

from scripts.policy.ledger_skip import (
    disable_ledger_skip,
    enable_ledger_skip,
    is_ledger_skipped,
    skip_flag_path,
)


class TestLedgerSkip(unittest.TestCase):
    def test_enable_and_disable_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = str(Path(tmp) / "AI_Codex")
            Path(vault).mkdir()

            self.assertFalse(is_ledger_skipped(vault))
            path = enable_ledger_skip(vault, reason="test")
            self.assertTrue(path.is_file())
            self.assertTrue(is_ledger_skipped(vault))
            self.assertEqual(path, skip_flag_path(vault))
            self.assertTrue(disable_ledger_skip(vault))
            self.assertFalse(is_ledger_skipped(vault))
            self.assertFalse(disable_ledger_skip(vault))


if __name__ == "__main__":
    unittest.main()
