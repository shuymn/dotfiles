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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "temp_lifecycle_check.py"
SPEC = importlib.util.spec_from_file_location("temp_lifecycle_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_VALID_COMPAT = textwrap.dedent("""\
    ## Compatibility & Sunset

    ### Temporary Mechanism Index

    | ID    | Mechanism     | Lifecycle Record | Status |
    |-------|---------------|-----------------|--------|
    | TEMP01 | Legacy adapter | in-doc | Active |

    ### Sunset Closure Checklist

    | ID    | Introduced for | Retirement Trigger      | Retirement Verification | Removal Scope |
    |-------|----------------|------------------------|------------------------|---------------|
    | TEMP01 | Shim for v1 API | New API stable in prod | All v1 traffic gone    | Remove adapter |
""")


class ExtractTempRowsTests(unittest.TestCase):
    def test_extracts_temp_id(self) -> None:
        section = textwrap.dedent("""\
            | ID    | Mechanism | Lifecycle Record | Status |
            |-------|-----------|-----------------|--------|
            | TEMP01 | foo       | in-doc          | Active |
        """)
        rows = MODULE._extract_temp_rows(section, MODULE._ID_COLS)
        self.assertIn("TEMP01", rows)

    def test_multiple_temps(self) -> None:
        section = textwrap.dedent("""\
            | ID    | Mechanism | Lifecycle Record | Status |
            |-------|-----------|-----------------|--------|
            | TEMP01 | foo      | in-doc          | Active |
            | TEMP02 | bar      | in-doc          | Active |
        """)
        rows = MODULE._extract_temp_rows(section, MODULE._ID_COLS)
        self.assertIn("TEMP01", rows)
        self.assertIn("TEMP02", rows)


class IntegrationTests(unittest.TestCase):
    def _run(self, content: str, base_dir: str = "") -> tuple[int, str]:
        tmp = Path(tempfile.mkdtemp())
        design_path = tmp / "design.md"
        design_path.write_text(textwrap.dedent(content), encoding="utf-8")
        args = ["temp_lifecycle_check.py", str(design_path)]
        if base_dir:
            args += ["--base-dir", base_dir]
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(args)
        return rc, buf.getvalue()

    def test_no_compat_section_skip(self) -> None:
        rc, out = self._run("# Design\n\nNo sunset section.\n")
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)

    def test_valid_lifecycle_pass(self) -> None:
        rc, out = self._run(_VALID_COMPAT)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)
        self.assertIn("signal.index_count=1", out)

    def test_missing_checklist_row_fail(self) -> None:
        content = textwrap.dedent("""\
            ## Compatibility & Sunset

            ### Temporary Mechanism Index

            | ID    | Mechanism | Lifecycle Record | Status |
            |-------|-----------|-----------------|--------|
            | TEMP01 | foo      | in-doc          | Active |

            ### Sunset Closure Checklist

            | ID    | Introduced for | Retirement Trigger | Retirement Verification | Removal Scope |
            |-------|----------------|--------------------|------------------------|---------------|
        """)
        rc, out = self._run(content)
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", out)
        self.assertIn("TEMP01", out)

    def test_empty_required_field_fail(self) -> None:
        content = textwrap.dedent("""\
            ## Compatibility & Sunset

            ### Temporary Mechanism Index

            | ID    | Mechanism | Lifecycle Record | Status |
            |-------|-----------|-----------------|--------|
            | TEMP01 | foo      | in-doc          | Active |

            ### Sunset Closure Checklist

            | ID    | Introduced for | Retirement Trigger | Retirement Verification | Removal Scope |
            |-------|----------------|--------------------|------------------------|---------------|
            | TEMP01 | shim          | -                  | All clear              | Remove module |
        """)
        rc, out = self._run(content)
        self.assertEqual(rc, 1)
        self.assertIn("Retirement Trigger", out)

    def test_no_temp_ids_skip(self) -> None:
        content = textwrap.dedent("""\
            ## Compatibility & Sunset

            No TEMPxx entries defined.
        """)
        rc, out = self._run(content)
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)

    def test_file_not_found(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["temp_lifecycle_check.py", "/nonexistent/design.md"])
        self.assertEqual(rc, 1)
        self.assertIn("DESIGN_FILE_NOT_FOUND", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
