"""Offline regression tests for the daily delisting transition."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import recheck


class RecheckTests(unittest.TestCase):
    def run_check(self, prior_g2, *, g2_errors=(), g3_errors=(), probe_ok=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "curators").mkdir()
            entry_file = root / "curators" / "fixture.json"
            entry_file.write_text('{"name":"fixture"}', encoding="utf-8")
            (root / "registry.json").write_text(
                '{"down_after_failed_checks":3}', encoding="utf-8"
            )
            state = root / "state" / "checks.jsonl"
            state.parent.mkdir()
            original_log = "".join(
                json.dumps({"name": "fixture", "g2": passed}) + "\n"
                for passed in prior_g2
            )
            state.write_text(original_log, encoding="utf-8")
            with (
                patch.object(recheck.R, "ROOT", root),
                patch.object(recheck, "STATE", state),
                patch.object(recheck, "probe", return_value=probe_ok),
                patch.object(
                    recheck.R,
                    "live_check",
                    return_value=(list(g2_errors), list(g3_errors), {}),
                ) as check,
            ):
                recheck.main()
                if not probe_ok:
                    check.assert_not_called()
                    self.assertEqual(state.read_text(encoding="utf-8"), original_log)
            records = list(map(json.loads, state.read_text(encoding="utf-8").splitlines()))
            entry = json.loads(entry_file.read_text(encoding="utf-8"))
            return records, entry.get("delist_history", [])

    def test_third_consecutive_g2_failure_delists(self):
        rows, delists = self.run_check([False, False], g2_errors=["bad schema"])
        self.assertFalse(rows[-1]["g2"])
        self.assertEqual([item["reason"] for item in delists], ["down"])

    def test_passing_g2_after_failures_does_not_delist(self):
        rows, delists = self.run_check([False] * 38)
        self.assertTrue(rows[-1]["g2"])
        self.assertEqual(delists, [])

    def test_previous_pass_breaks_failure_streak(self):
        _, delists = self.run_check([False, False, True, False], g2_errors=["bad schema"])
        self.assertEqual(delists, [])

    def test_g3_can_still_delist_stale_issue(self):
        rows, delists = self.run_check([], g3_errors=["older than 14 days"])
        self.assertTrue(rows[-1]["g2"])
        self.assertFalse(rows[-1]["g3"])
        self.assertEqual([item["reason"] for item in delists], ["stale"])

    def test_global_probe_failure_skips_all_checks(self):
        rows, delists = self.run_check([False, False], probe_ok=False)
        self.assertEqual(len(rows), 2)
        self.assertEqual(delists, [])


if __name__ == "__main__":
    unittest.main()
