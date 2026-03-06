import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
BUILD_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "build_skills.py"
BUILD_SPEC = importlib.util.spec_from_file_location("build_skills", BUILD_MODULE_PATH)
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
BUILD_MODULE = importlib.util.module_from_spec(BUILD_SPEC)
sys.modules[BUILD_SPEC.name] = BUILD_MODULE
BUILD_SPEC.loader.exec_module(BUILD_MODULE)

ARTIFACT_ROOT = Path(tempfile.mkdtemp()) / "artifacts"
BUILD_MODULE.build_skills(SOURCE_ROOT, ARTIFACT_ROOT)

MODULE_PATH = ARTIFACT_ROOT / "design-doc" / "scripts" / "risk_format_check.py"
SPEC = importlib.util.spec_from_file_location("risk_format_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CheckRiskRowTests(unittest.TestCase):
    def test_critical_valid_format(self) -> None:
        row = {
            "Area": "Auth",
            "Risk Tier": "Critical",
            "Change Rationale": "Defect Impact: auth bypass / Blast Radius: all users",
        }
        ok, _ = MODULE.check_risk_row(row)
        self.assertTrue(ok)

    def test_critical_missing_format(self) -> None:
        row = {
            "Area": "Auth",
            "Risk Tier": "Critical",
            "Change Rationale": "Very important area",
        }
        ok, issue = MODULE.check_risk_row(row)
        self.assertFalse(ok)
        self.assertIn("Defect Impact", issue)

    def test_sensitive_valid_format(self) -> None:
        row = {
            "Area": "DB Schema",
            "Risk Tier": "Sensitive",
            "Change Rationale": "Defect Impact: silent corruption / Blast Radius: all services",
        }
        ok, _ = MODULE.check_risk_row(row)
        self.assertTrue(ok)

    def test_standard_valid_format(self) -> None:
        row = {
            "Area": "UI",
            "Risk Tier": "Standard",
            "Change Rationale": "Not Critical: UI only / Not Sensitive: locally visible failure",
        }
        ok, _ = MODULE.check_risk_row(row)
        self.assertTrue(ok)

    def test_standard_missing_format(self) -> None:
        row = {
            "Area": "UI",
            "Risk Tier": "Standard",
            "Change Rationale": "Low risk area",
        }
        ok, issue = MODULE.check_risk_row(row)
        self.assertFalse(ok)
        self.assertIn("Not Critical", issue)

    def test_unknown_tier_skipped(self) -> None:
        row = {"Area": "X", "Risk Tier": "Unknown", "Change Rationale": "irrelevant"}
        ok, _ = MODULE.check_risk_row(row)
        self.assertTrue(ok)


class IntegrationTests(unittest.TestCase):
    def _run(self, content: str) -> tuple[int, str]:
        tmp = Path(tempfile.mkdtemp()) / "design.md"
        tmp.write_text(textwrap.dedent(content), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["risk_format_check.py", str(tmp)])
        return rc, buf.getvalue()

    def test_valid_mixed_rows_pass(self) -> None:
        design = """\
            ## Risk Classification

            | Area | Risk Tier | Change Rationale |
            |------|-----------|-----------------|
            | Auth | Critical  | Defect Impact: breach / Blast Radius: all users |
            | UI   | Standard  | Not Critical: UI / Not Sensitive: visible locally |
        """
        rc, out = self._run(design)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)

    def test_missing_format_fail(self) -> None:
        design = """\
            ## Risk Classification

            | Area | Risk Tier | Change Rationale |
            |------|-----------|-----------------|
            | Auth | Critical  | Important area  |
        """
        rc, out = self._run(design)
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", out)
        self.assertIn("signal.failures=1", out)

    def test_no_section_skip(self) -> None:
        rc, out = self._run("# Design\n\nNo risk section.\n")
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)

    def test_empty_table_fail(self) -> None:
        design = """\
            ## Risk Classification

            No rows here.
        """
        rc, out = self._run(design)
        self.assertEqual(rc, 1)
        self.assertIn("RISK_TABLE_EMPTY", out)


if __name__ == "__main__":
    unittest.main()
