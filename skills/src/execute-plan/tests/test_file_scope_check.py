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

MODULE_PATH = ARTIFACT_ROOT / "execute-plan" / "scripts" / "file_scope_check.py"
SPEC = importlib.util.spec_from_file_location("file_scope_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExtractTaskBlockTests(unittest.TestCase):
    def test_extracts_correct_block(self) -> None:
        plan = textwrap.dedent("""\
            # Plan
            ### Task 1: First
            - **Goal**: Do A
            ### Task 2: Second
            - **Goal**: Do B
        """)
        block = MODULE.extract_task_block(plan, 1)
        self.assertIn("Do A", block)
        self.assertNotIn("Do B", block)

    def test_missing_task_returns_empty(self) -> None:
        plan = "# Plan\n### Task 1: Only\n- **Goal**: X\n"
        block = MODULE.extract_task_block(plan, 99)
        self.assertEqual(block, "")


class ParseAllowedFilesTests(unittest.TestCase):
    def test_parses_backtick_patterns(self) -> None:
        block = textwrap.dedent("""\
            ### Task 1: Test
            - **Allowed Files**:
              - `src/**/*.py`
              - `tests/**/*.py`
            - **Goal**: test
        """)
        patterns = MODULE.parse_allowed_files(block)
        self.assertEqual(patterns, ["src/**/*.py", "tests/**/*.py"])

    def test_empty_when_no_allowed_files(self) -> None:
        block = "### Task 1: Test\n- **Goal**: test\n"
        patterns = MODULE.parse_allowed_files(block)
        self.assertEqual(patterns, [])


class ParseExceptionFilesTests(unittest.TestCase):
    def test_parses_exceptions_with_rationale(self) -> None:
        block = textwrap.dedent("""\
            ### Task 1: Test
            - **Exception Files**:
              - `config.json` (shared config)
              - `pyproject.toml` (dependency update)
        """)
        exceptions = MODULE.parse_exception_files(block)
        self.assertEqual(len(exceptions), 2)
        self.assertEqual(exceptions[0], ("config.json", "shared config"))
        self.assertEqual(exceptions[1], ("pyproject.toml", "dependency update"))


class MatchFileTests(unittest.TestCase):
    def test_file_matches_allowed(self) -> None:
        result = MODULE.match_file(
            "src/foo.py", ["src/**/*.py"], []
        )
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.pattern, "src/**/*.py")

    def test_file_matches_exception(self) -> None:
        result = MODULE.match_file(
            "config.json", ["src/**/*.py"], [("config.json", "shared")]
        )
        self.assertEqual(result.status, "OK (exception)")
        self.assertIn("EXCEPTION", result.pattern)

    def test_file_no_match_scope_deviation(self) -> None:
        result = MODULE.match_file(
            "README.md", ["src/**/*.py"], []
        )
        self.assertEqual(result.status, "SCOPE_DEVIATION")
        self.assertEqual(result.pattern, "NONE")

    def test_allowed_takes_precedence_over_exception(self) -> None:
        result = MODULE.match_file(
            "src/foo.py", ["src/**/*.py"], [("src/foo.py", "also excepted")]
        )
        self.assertEqual(result.status, "OK")


class IntegrationTests(unittest.TestCase):
    def run_main(
        self, plan_content: str, task_id: int, stdin_lines: list[str]
    ) -> tuple[int, str]:
        temp_dir = Path(tempfile.mkdtemp())
        plan_path = temp_dir / "plan.md"
        plan_path.write_text(
            textwrap.dedent(plan_content).strip() + "\n", encoding="utf-8"
        )

        stdin_text = "\n".join(stdin_lines) + "\n" if stdin_lines else ""
        buf = io.StringIO()
        with patch("sys.stdin", io.StringIO(stdin_text)), redirect_stdout(buf):
            rc = MODULE.main(
                ["file_scope_check.py", str(plan_path), "--task", str(task_id)]
            )
        return rc, buf.getvalue()

    def test_all_files_within_scope_pass(self) -> None:
        plan = """\
            # Plan
            ### Task 1: Test
            - **Allowed Files**:
              - `src/**/*.py`
              - `tests/**/*.py`
            - **Goal**: test
        """
        rc, output = self.run_main(plan, 1, ["src/foo.py", "tests/test_bar.py"])
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", output)
        self.assertIn("code=ALL_FILES_IN_SCOPE", output)
        self.assertIn("signal.ok=2", output)
        self.assertIn("signal.deviation=0", output)

    def test_exception_file_ok(self) -> None:
        plan = """\
            # Plan
            ### Task 1: Test
            - **Allowed Files**:
              - `src/**/*.py`
            - **Exception Files**:
              - `config.json` (shared config)
            - **Goal**: test
        """
        rc, output = self.run_main(plan, 1, ["src/foo.py", "config.json"])
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", output)
        self.assertIn("signal.exception=1", output)

    def test_scope_deviation_fail(self) -> None:
        plan = """\
            # Plan
            ### Task 1: Test
            - **Allowed Files**:
              - `src/**/*.py`
            - **Goal**: test
        """
        rc, output = self.run_main(plan, 1, ["src/foo.py", "README.md"])
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", output)
        self.assertIn("code=SCOPE_DEVIATION_DETECTED", output)
        self.assertIn("signal.deviation=1", output)
        self.assertIn("README.md", output)
        self.assertIn("fix.1=FIX_ADD_TO_ALLOWED_OR_EXCEPTION_FILES", output)

    def test_no_allowed_files_skips(self) -> None:
        plan = """\
            # Plan
            ### Task 1: Test
            - **Goal**: test
        """
        rc, output = self.run_main(plan, 1, ["src/foo.py"])
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", output)
        self.assertIn("code=NO_ALLOWED_FILES", output)

    def test_task_not_found_emits_structured_fail(self) -> None:
        plan = """\
            # Plan
            ### Task 1: Test
            - **Goal**: test
        """
        rc, output = self.run_main(plan, 99, ["src/foo.py"])
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", output)
        self.assertIn("code=TASK_NOT_FOUND", output)
        self.assertIn("fix.1=FIX_CHECK_TASK_ID", output)

    def test_output_contains_per_file_entries(self) -> None:
        plan = """\
            # Plan
            ### Task 1: Test
            - **Allowed Files**:
              - `src/**/*.py`
            - **Goal**: test
        """
        rc, output = self.run_main(plan, 1, ["src/foo.py"])
        self.assertEqual(rc, 0)
        self.assertIn("file.1=src/foo.py|pattern=src/**/*.py|status=OK", output)


if __name__ == "__main__":
    unittest.main()
