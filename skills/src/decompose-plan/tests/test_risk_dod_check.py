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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "risk_dod_check.py"
SPEC = importlib.util.spec_from_file_location("risk_dod_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_DOD_CRITICAL = "Adversarial verification required (minimum 3 probes)."
_DOD_SENSITIVE_1 = "Heightened dod-recheck scrutiny applies."
_DOD_SENSITIVE_2 = (
    "Adversarial verification required"
    " (minimum 2 probes: Category 1 + most relevant 1 category)."
)
_DOD_STANDARD_IMPL = "Adversarial verification required (1 probe: most relevant category)."


def _make_design(tier: str) -> str:
    if tier == "Critical":
        rationale = "Defect Impact: breach / Blast Radius: all"
    elif tier == "Sensitive":
        rationale = "Defect Impact: corruption / Blast Radius: services"
    else:
        rationale = "Not Critical: low risk / Not Sensitive: visible failure"
    return textwrap.dedent(f"""\
        # Design

        ## Risk Classification

        | Area | Risk Tier | Change Rationale |
        |------|-----------|-----------------|
        | Core | {tier}    | {rationale}     |
    """)


def _make_plan(dod_lines: str, files: str = "") -> str:
    file_line = files if files else "src/foo.py"
    return (
        "# Plan\n"
        "\n"
        "### Task 01: Do something\n"
        "- **Goal**: Implement X\n"
        f"- **Allowed Files**:\n  - `{file_line}`\n"
        "- **RED**: test fails\n"
        "- **GREEN**: implement\n"
        "- **REFACTOR**: cleanup\n"
        "- **DoD**:\n"
        "  - All tests pass\n"
        f"  {dod_lines}\n"
    )


class ParseMaxRiskTierTests(unittest.TestCase):
    def test_critical(self) -> None:
        design = _make_design("Critical")
        self.assertEqual(MODULE.parse_max_risk_tier(design), "Critical")

    def test_sensitive(self) -> None:
        design = _make_design("Sensitive")
        self.assertEqual(MODULE.parse_max_risk_tier(design), "Sensitive")

    def test_standard(self) -> None:
        design = _make_design("Standard")
        self.assertEqual(MODULE.parse_max_risk_tier(design), "Standard")

    def test_no_section_defaults_standard(self) -> None:
        self.assertEqual(MODULE.parse_max_risk_tier("# Design\n\nNo risk.\n"), "Standard")

    def test_critical_beats_sensitive(self) -> None:
        design = textwrap.dedent("""\
            ## Risk Classification

            | Area | Risk Tier | Change Rationale |
            |------|-----------|-----------------|
            | A    | Sensitive | Defect Impact: x / Blast Radius: y |
            | B    | Critical  | Defect Impact: x / Blast Radius: y |
        """)
        self.assertEqual(MODULE.parse_max_risk_tier(design), "Critical")


class CheckTaskTests(unittest.TestCase):
    def test_critical_with_annotation_pass(self) -> None:
        body = f"### Task 01\n- **DoD**:\n  - {_DOD_CRITICAL}\n"
        issues = MODULE.check_task(1, body, "Critical")
        self.assertEqual(issues, [])

    def test_critical_missing_annotation_fail(self) -> None:
        body = "### Task 01\n- **DoD**:\n  - All tests pass\n"
        issues = MODULE.check_task(1, body, "Critical")
        self.assertEqual(len(issues), 1)
        self.assertIn("Critical", issues[0])

    def test_sensitive_requires_both_annotations(self) -> None:
        body = f"### Task 01\n- **DoD**:\n  - {_DOD_SENSITIVE_1}\n"
        issues = MODULE.check_task(1, body, "Sensitive")
        # Missing Sensitive_2
        self.assertEqual(len(issues), 1)

    def test_sensitive_with_both_pass(self) -> None:
        body = f"### Task 01\n- **DoD**:\n  - {_DOD_SENSITIVE_1}\n  - {_DOD_SENSITIVE_2}\n"
        issues = MODULE.check_task(1, body, "Sensitive")
        self.assertEqual(issues, [])

    def test_standard_impl_file_needs_annotation(self) -> None:
        body = (
            "### Task 01\n"
            "- **Allowed Files**:\n  - `src/main.py`\n"
            "- **DoD**:\n  - All tests pass\n"
        )
        issues = MODULE.check_task(1, body, "Standard")
        self.assertEqual(len(issues), 1)
        self.assertIn("Standard+impl", issues[0])

    def test_standard_test_file_only_no_annotation_needed(self) -> None:
        body = (
            "### Task 01\n"
            "- **Allowed Files**:\n  - `tests/test_foo.py`\n"
            "- **DoD**:\n  - All tests pass\n"
        )
        issues = MODULE.check_task(1, body, "Standard")
        self.assertEqual(issues, [])


class IntegrationTests(unittest.TestCase):
    def _run(self, plan_text: str, design_text: str) -> tuple[int, str]:
        tmp = Path(tempfile.mkdtemp())
        plan_path = tmp / "plan.md"
        design_path = tmp / "design.md"
        plan_path.write_text(plan_text, encoding="utf-8")
        design_path.write_text(design_text, encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["risk_dod_check.py", str(plan_path), str(design_path)])
        return rc, buf.getvalue()

    def test_critical_design_with_annotation_pass(self) -> None:
        plan = _make_plan(f"- {_DOD_CRITICAL}")
        design = _make_design("Critical")
        rc, out = self._run(plan, design)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)

    def test_critical_design_missing_annotation_fail(self) -> None:
        plan = _make_plan("- Run quality gates")
        design = _make_design("Critical")
        rc, out = self._run(plan, design)
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", out)

    def test_standard_impl_file_with_annotation_pass(self) -> None:
        plan = _make_plan(f"- {_DOD_STANDARD_IMPL}", files="src/impl.py")
        design = _make_design("Standard")
        rc, out = self._run(plan, design)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)

    def test_no_tasks_skip(self) -> None:
        rc, out = self._run("# Plan\n\nNo tasks.\n", _make_design("Standard"))
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)


if __name__ == "__main__":
    unittest.main()
