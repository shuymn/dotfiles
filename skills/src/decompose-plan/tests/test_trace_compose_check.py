import importlib.util
import sys
import tempfile
import textwrap
import unittest
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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "trace_compose_check.py"
SPEC = importlib.util.spec_from_file_location("trace_compose_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TraceXRefTests(unittest.TestCase):
    def test_all_atoms_match_pass(self) -> None:
        design_atoms = {"REQ1", "AC1", "GOAL1", "DEC1"}
        trace_atoms = {"REQ1", "AC1", "GOAL1", "DEC1"}
        status, _, _ = MODULE.check_trace_xref(design_atoms, trace_atoms)
        self.assertEqual(status, "PASS")

    def test_missing_forward_fail(self) -> None:
        design_atoms = {"REQ1", "AC1", "GOAL1"}
        trace_atoms = {"REQ1", "AC1"}
        status, _, evidence = MODULE.check_trace_xref(design_atoms, trace_atoms)
        self.assertEqual(status, "FAIL")
        self.assertIn("GOAL1", evidence)

    def test_orphan_reverse_fail(self) -> None:
        design_atoms = {"REQ1"}
        trace_atoms = {"REQ1", "REQ99"}
        status, _, evidence = MODULE.check_trace_xref(design_atoms, trace_atoms)
        self.assertEqual(status, "FAIL")
        self.assertIn("REQ99", evidence)


class ACOwnershipTests(unittest.TestCase):
    def test_all_acs_covered_pass(self) -> None:
        design_acs = {"AC1", "AC2"}
        rows = [
            {"AC ID": "AC1", "Owner Task": "Task 1", "Contributors": "-", "Has RED for AC": "yes"},
            {"AC ID": "AC2", "Owner Task": "Task 2", "Contributors": "-", "Has RED for AC": "yes"},
        ]
        status, _, _ = MODULE.check_ac_ownership(design_acs, rows)
        self.assertEqual(status, "PASS")

    def test_missing_ac_fail(self) -> None:
        design_acs = {"AC1", "AC2", "AC3"}
        rows = [
            {"AC ID": "AC1", "Owner Task": "Task 1", "Contributors": "-", "Has RED for AC": "yes"},
        ]
        status, _, evidence = MODULE.check_ac_ownership(design_acs, rows)
        self.assertEqual(status, "FAIL")
        self.assertIn("AC2", evidence)
        self.assertIn("AC3", evidence)

    def test_phantom_ac_fail(self) -> None:
        design_acs = {"AC1"}
        rows = [
            {"AC ID": "AC1", "Owner Task": "Task 1", "Contributors": "-", "Has RED for AC": "yes"},
            {"AC ID": "AC99", "Owner Task": "Task 2", "Contributors": "-", "Has RED for AC": "yes"},
        ]
        status, _, evidence = MODULE.check_ac_ownership(design_acs, rows)
        self.assertEqual(status, "FAIL")
        self.assertIn("AC99", evidence)

    def test_duplicate_owner_fail(self) -> None:
        design_acs = {"AC1"}
        rows = [
            {"AC ID": "AC1", "Owner Task": "Task 1", "Contributors": "-", "Has RED for AC": "yes"},
            {"AC ID": "AC1", "Owner Task": "Task 2", "Contributors": "-", "Has RED for AC": "yes"},
        ]
        status, _, evidence = MODULE.check_ac_ownership(design_acs, rows)
        self.assertEqual(status, "FAIL")
        self.assertIn("duplicate owner", evidence)


class TEMPTraceTests(unittest.TestCase):
    def test_all_temps_match_pass(self) -> None:
        status, _, _ = MODULE.check_temp_trace({"TEMP1", "TEMP2"}, {"TEMP1", "TEMP2"})
        self.assertEqual(status, "PASS")

    def test_missing_temp_fail(self) -> None:
        status, _, evidence = MODULE.check_temp_trace({"TEMP1", "TEMP2"}, {"TEMP1"})
        self.assertEqual(status, "FAIL")
        self.assertIn("TEMP2", evidence)

    def test_orphan_temp_fail(self) -> None:
        status, _, evidence = MODULE.check_temp_trace({"TEMP1"}, {"TEMP1", "TEMP99"})
        self.assertEqual(status, "FAIL")
        self.assertIn("TEMP99", evidence)

    def test_no_temps_pass(self) -> None:
        status, _, _ = MODULE.check_temp_trace(set(), set())
        self.assertEqual(status, "PASS")


class ParseTraceMatrixAtomsTests(unittest.TestCase):
    def test_parse_bullet_atoms(self) -> None:
        section = textwrap.dedent("""\
            - REQ1: Task 1, Task 2
            - AC1: Task 1
            - GOAL1: Task 3
            - DEC1: Task 2
        """)
        atoms = MODULE.parse_trace_matrix_atoms(section)
        self.assertEqual(atoms, {"REQ1", "AC1", "GOAL1", "DEC1"})


class ParseACOwnershipMapTests(unittest.TestCase):
    def test_parse_table(self) -> None:
        section = textwrap.dedent("""\
            | AC ID | Owner Task | Contributors | Has RED for AC |
            |-------|------------|-------------|----------------|
            | AC1 | Task 1 | - | yes |
            | AC2 | Task 2 | Task 1 | yes |
        """)
        rows = MODULE.parse_ac_ownership_map(section)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["AC ID"], "AC1")
        self.assertEqual(rows[1]["Owner Task"], "Task 2")


class ParseTempTraceIdsTests(unittest.TestCase):
    def test_parse_bullet_temps(self) -> None:
        section = textwrap.dedent("""\
            - TEMP1: introduced by Task 1, retired by Task 3
            - TEMP2: introduced by Task 2
        """)
        temps = MODULE.parse_temp_trace_ids(section)
        self.assertEqual(temps, {"TEMP1", "TEMP2"})

    def test_parse_table_temps(self) -> None:
        section = textwrap.dedent("""\
            | TEMP ID | Introduced By | Retired By |
            |---------|---------------|------------|
            | TEMP1 | Task 1 | Task 3 |
        """)
        temps = MODULE.parse_temp_trace_ids(section)
        self.assertEqual(temps, {"TEMP1"})


class IntegrationTests(unittest.TestCase):
    def run_main(
        self, design_content: str, trace_content: str
    ) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout

        temp_dir = Path(tempfile.mkdtemp())
        design_path = temp_dir / "design.md"
        trace_path = temp_dir / "plan.trace.md"
        design_path.write_text(
            textwrap.dedent(design_content).strip() + "\n", encoding="utf-8"
        )
        trace_path.write_text(
            textwrap.dedent(trace_content).strip() + "\n", encoding="utf-8"
        )

        import os
        old_mode = os.environ.get("LLM_CHECK_MODE")
        os.environ["LLM_CHECK_MODE"] = "full"
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = MODULE.main(
                    ["trace_compose_check.py", str(design_path), str(trace_path)]
                )
            return rc, buf.getvalue()
        finally:
            if old_mode is None:
                os.environ.pop("LLM_CHECK_MODE", None)
            else:
                os.environ["LLM_CHECK_MODE"] = old_mode

    def test_all_pass(self) -> None:
        design = """\
            # Design
            ## Goals
            - GOAL1: some goal
            ## Requirements
            - REQ1: some requirement
            ## Acceptance Criteria
            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC1 | Ubiquitous | behavioral | sentence | intent | `cmd` |
            ## Decision Log
            | ADR | Decision | Status |
            |-----|----------|--------|
            | ADR-0001 | decision | accepted |
            DEC1 maps to ADR-0001.
        """
        trace = """\
            # Trace Pack

            ## Design -> Task Trace Matrix

            - REQ1: Task 1
            - AC1: Task 1
            - GOAL1: Task 1
            - DEC1: Task 1

            ## AC Ownership Map

            | AC ID | Owner Task | Contributors | Has RED for AC |
            |-------|------------|-------------|----------------|
            | AC1 | Task 1 | - | yes |

            ## Temporary Mechanism Trace

            (none)
        """
        rc, output = self.run_main(design, trace)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", output)

    def test_missing_atoms_fails(self) -> None:
        design = """\
            # Design
            ## Goals
            - GOAL1: goal
            ## Requirements
            - REQ1: req
            - REQ2: req2
        """
        trace = """\
            # Trace Pack

            ## Design -> Task Trace Matrix

            - REQ1: Task 1
            - GOAL1: Task 1

            ## AC Ownership Map

            (empty)

            ## Temporary Mechanism Trace

            (none)
        """
        rc, output = self.run_main(design, trace)
        self.assertEqual(rc, 1)
        self.assertIn("check.1.status=FAIL", output)
        self.assertIn("REQ2", output)


class EarlyErrorTests(unittest.TestCase):
    def test_missing_args_emits_fix_code(self) -> None:
        import io
        import os
        from contextlib import redirect_stdout

        old_mode = os.environ.get("LLM_CHECK_MODE")
        os.environ["LLM_CHECK_MODE"] = "compact"
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = MODULE.main(["trace_compose_check.py"])
            self.assertEqual(rc, 1)
            output = buf.getvalue()
            self.assertIn("code=INVALID_ARGUMENT_COUNT", output)
            self.assertIn("fix.1=FIX_USE_TWO_ARGS", output)
        finally:
            if old_mode is None:
                os.environ.pop("LLM_CHECK_MODE", None)
            else:
                os.environ["LLM_CHECK_MODE"] = old_mode

    def test_missing_design_file_emits_fix_code(self) -> None:
        import io
        import os
        from contextlib import redirect_stdout

        temp_dir = Path(tempfile.mkdtemp())
        trace_path = temp_dir / "plan.trace.md"
        trace_path.write_text("# Trace\n", encoding="utf-8")

        old_mode = os.environ.get("LLM_CHECK_MODE")
        os.environ["LLM_CHECK_MODE"] = "compact"
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = MODULE.main([
                    "trace_compose_check.py",
                    str(temp_dir / "nonexistent.md"),
                    str(trace_path),
                ])
            self.assertEqual(rc, 1)
            output = buf.getvalue()
            self.assertIn("code=DESIGN_FILE_NOT_FOUND", output)
            self.assertIn("fix.1=FIX_DESIGN_FILE_PATH", output)
        finally:
            if old_mode is None:
                os.environ.pop("LLM_CHECK_MODE", None)
            else:
                os.environ["LLM_CHECK_MODE"] = old_mode


if __name__ == "__main__":
    unittest.main()
