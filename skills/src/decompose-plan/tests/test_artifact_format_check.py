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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "artifact_format_check.py"
SPEC = importlib.util.spec_from_file_location("artifact_format_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TableStructureTests(unittest.TestCase):
    def test_valid_table_no_issues(self) -> None:
        text = (
            "| A | B | C |\n"
            "|---|---|---|\n"
            "| 1 | 2 | 3 |\n"
        )
        issues = MODULE._check_table_structure(text)
        self.assertEqual(issues, [])

    def test_missing_separator_flagged(self) -> None:
        text = (
            "| A | B |\n"
            "| 1 | 2 |\n"  # No separator
            "| 3 | 4 |\n"
        )
        issues = MODULE._check_table_structure(text)
        self.assertTrue(any("separator" in i for i in issues))

    def test_column_count_mismatch_flagged(self) -> None:
        text = (
            "| A | B | C |\n"
            "|---|---|---|\n"
            "| 1 | 2 |\n"  # Only 2 columns
        )
        issues = MODULE._check_table_structure(text)
        self.assertTrue(any("columns" in i for i in issues))


class RequiredSectionsTests(unittest.TestCase):
    def test_plan_with_checkpoint_summary(self) -> None:
        text = "## Checkpoint Summary\n\n- **Alignment Verdict**: PASS\n"
        missing = MODULE._check_required_sections(text, "plan")
        # Should be missing Task Dependency Graph
        self.assertIn("Task Dependency Graph", missing)

    def test_plan_all_sections_present(self) -> None:
        text = "## Checkpoint Summary\n\n...\n\n## Task Dependency Graph\n\n...\n"
        missing = MODULE._check_required_sections(text, "plan")
        self.assertEqual(missing, [])

    def test_design_missing_acceptance_criteria(self) -> None:
        text = "## Goals\n\n## Decomposition Strategy\n\n"
        missing = MODULE._check_required_sections(text, "design")
        self.assertIn("Acceptance Criteria", missing)


class IDFormatTests(unittest.TestCase):
    def test_valid_id_no_issue(self) -> None:
        text = (
            "| AC ID | Description |\n"
            "|-------|-------------|\n"
            "| AC01  | Does X      |\n"
        )
        issues = MODULE._check_id_format(text)
        self.assertEqual(issues, [])

    def test_single_digit_id_flagged(self) -> None:
        text = (
            "| AC ID | Description |\n"
            "|-------|-------------|\n"
            "| AC1   | Does X      |\n"
        )
        issues = MODULE._check_id_format(text)
        self.assertTrue(any("AC1" in i for i in issues))


class IntegrationTests(unittest.TestCase):
    def _run(self, content: str, artifact_type: str) -> tuple[int, str]:
        tmp = Path(tempfile.mkdtemp()) / "artifact.md"
        tmp.write_text(textwrap.dedent(content), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main([
                "artifact_format_check.py", str(tmp), "--type", artifact_type
            ])
        return rc, buf.getvalue()

    def test_valid_adversarial_pass(self) -> None:
        content = """\
            # Report

            - **Overall Verdict**: PASS

            ## Attack Summary

            | # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
            |---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
            | 1 | Input    | Empty values | yes       | t.py      | pytest  | 0         | DEFENDED | ok |
        """
        rc, out = self._run(content, "adversarial")
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)

    def test_missing_overall_verdict_fail(self) -> None:
        content = """\
            # Report

            ## Attack Summary

            | # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
            |---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
        """
        rc, out = self._run(content, "adversarial")
        self.assertEqual(rc, 1)
        self.assertIn("Overall Verdict", out)

    def test_table_column_mismatch_fail(self) -> None:
        content = """\
            ## Checkpoint Summary

            ## Task Dependency Graph

            | A | B | C |
            |---|---|---|
            | 1 | 2 |
        """
        rc, out = self._run(content, "plan")
        self.assertEqual(rc, 1)
        self.assertIn("columns", out)

    def test_empty_file_fail(self) -> None:
        tmp = Path(tempfile.mkdtemp()) / "empty.md"
        tmp.write_text("", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["artifact_format_check.py", str(tmp), "--type", "plan"])
        self.assertEqual(rc, 1)
        self.assertIn("ARTIFACT_FILE_EMPTY", buf.getvalue())

    def test_file_not_found(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main([
                "artifact_format_check.py", "/nonexistent/a.md", "--type", "plan"
            ])
        self.assertEqual(rc, 1)
        self.assertIn("ARTIFACT_FILE_NOT_FOUND", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
