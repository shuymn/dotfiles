import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SOURCE_ROOT = Path(__file__).resolve().parents[2]
BUILD_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "build_skills.py"
BUILD_SPEC = importlib.util.spec_from_file_location("build_skills", BUILD_MODULE_PATH)
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
BUILD_MODULE = importlib.util.module_from_spec(BUILD_SPEC)
sys.modules[BUILD_SPEC.name] = BUILD_MODULE
BUILD_SPEC.loader.exec_module(BUILD_MODULE)

ARTIFACT_ROOT = Path(tempfile.mkdtemp()) / "artifacts"
BUILD_MODULE.build_skills(SOURCE_ROOT, ARTIFACT_ROOT)

MODULE_PATH = ARTIFACT_ROOT / "design-doc" / "scripts" / "verification_cmd_check.py"
SPEC = importlib.util.spec_from_file_location("verification_cmd_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ParseAcRowsTests(unittest.TestCase):
    def test_parses_standard_ac_table(self) -> None:
        text = textwrap.dedent("""\
            ## Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC01  | Ubiquitous | behavioral   | System does X        | Verify X works      | pytest tests/        |
        """)
        rows = MODULE.parse_ac_rows(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["AC ID"], "AC01")

    def test_returns_empty_when_no_section(self) -> None:
        rows = MODULE.parse_ac_rows("# Design\n\nNo AC table here.\n")
        self.assertEqual(rows, [])


class CheckRowTests(unittest.TestCase):
    def test_tbd_at_plan_returns_tbd(self) -> None:
        row = {"AC ID": "AC01", "Verification Command": "TBD-at-plan"}
        status, _ = MODULE.check_row(row)
        self.assertEqual(status, "TBD")

    def test_empty_command_returns_fail(self) -> None:
        row = {"AC ID": "AC01", "Verification Command": ""}
        status, msg = MODULE.check_row(row)
        self.assertEqual(status, "FAIL")
        self.assertIn("AC01", msg)

    def test_dash_command_returns_fail(self) -> None:
        row = {"AC ID": "AC02", "Verification Command": "-"}
        status, _ = MODULE.check_row(row)
        self.assertEqual(status, "FAIL")

    def test_resolvable_command_returns_pass(self) -> None:
        row = {"AC ID": "AC01", "Verification Command": "python --version"}
        with patch("shutil.which", return_value="/usr/bin/python"):
            status, _ = MODULE.check_row(row)
        self.assertEqual(status, "PASS")

    def test_unresolvable_command_returns_fail(self) -> None:
        row = {"AC ID": "AC01", "Verification Command": "nonexistent-tool --check"}
        with patch("shutil.which", return_value=None):
            status, msg = MODULE.check_row(row)
        self.assertEqual(status, "FAIL")
        self.assertIn("nonexistent-tool", msg)


class IntegrationTests(unittest.TestCase):
    def _run(self, content: str) -> tuple[int, str]:
        tmp = Path(tempfile.mkdtemp()) / "design.md"
        tmp.write_text(textwrap.dedent(content), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["verification_cmd_check.py", str(tmp)])
        return rc, buf.getvalue()

    def test_all_commands_valid_pass(self) -> None:
        design = """\
            ## Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC01  | Ubiquitous | behavioral   | Does X               | Check X             | python -m pytest     |
        """
        with patch("shutil.which", return_value="/usr/bin/python"):
            rc, out = self._run(design)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)

    def test_empty_command_fail(self) -> None:
        design = """\
            ## Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC01  | Ubiquitous | behavioral   | Does X               | Check X             |                      |
        """
        rc, out = self._run(design)
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", out)
        self.assertIn("signal.failures=1", out)

    def test_tbd_advisory_still_pass(self) -> None:
        design = """\
            ## Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC01  | Ubiquitous | behavioral   | Does X               | Check X             | TBD-at-plan          |
        """
        rc, out = self._run(design)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)
        self.assertIn("signal.advisories=1", out)

    def test_no_ac_table_skip(self) -> None:
        rc, out = self._run("# Design\n\nNo tables here.\n")
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)

    def test_file_not_found(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["verification_cmd_check.py", "/nonexistent/design.md"])
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", buf.getvalue())
        self.assertIn("DESIGN_FILE_NOT_FOUND", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
