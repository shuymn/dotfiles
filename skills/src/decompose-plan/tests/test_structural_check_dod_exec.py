import importlib.util
import os
import subprocess
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

SCRIPT_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "structural-check.sh"


class DoDRunExecCheckTests(unittest.TestCase):
    def write_file(self, root: Path, relative_path: str, content: str) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def run_check(
        self, design_content: str, plan_content: str
    ) -> subprocess.CompletedProcess[str]:
        temp_dir = Path(tempfile.mkdtemp())
        design_path = self.write_file(temp_dir, "design.md", design_content)
        plan_path = self.write_file(temp_dir, "plan.md", plan_content)
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), str(design_path), str(plan_path)],
            capture_output=True,
            text=True,
            check=False,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": os.environ.get("HOME", "/tmp"),
                "LLM_CHECK_MODE": "full",
            },
        )

    def test_valid_dod_run_commands_pass(self) -> None:
        design = """\
            # Design
            ## Goals
            - GOAL1: placeholder
            ## Acceptance Criteria
            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC1 | Ubiquitous | behavioral | placeholder | placeholder | `echo test` |
            """
        plan = """\
            # Plan
            ### Task 1: Test task
            - **Dependencies**: none
            - **DoD**:
              - Run: `echo hello`
              - Run: `true`
            """
        result = self.run_check(design, plan)
        self.assertIn("check.9.id=DoD-Run-Exec", result.stdout)
        self.assertIn("check.9.status=PASS", result.stdout)

    def test_invalid_dod_run_command_fails(self) -> None:
        design = """\
            # Design
            ## Goals
            - GOAL1: placeholder
            """
        plan = """\
            # Plan
            ### Task 1: Test task
            - **Dependencies**: none
            - **DoD**:
              - Run: `nonexistent_command_xyz_12345 --flag`
            """
        result = self.run_check(design, plan)
        self.assertIn("check.9.id=DoD-Run-Exec", result.stdout)
        self.assertIn("check.9.status=FAIL", result.stdout)
        self.assertIn("nonexistent_command_xyz_12345", result.stdout)

    def test_quality_gates_section_excluded(self) -> None:
        design = """\
            # Design
            ## Goals
            - GOAL1: placeholder
            """
        plan = """\
            # Plan
            ## Quality Gates
            | Category | Command |
            |----------|---------|
            | test | `nonexistent_qgate_cmd_99999` |

            ## Tasks
            ### Task 1: Test task
            - **Dependencies**: none
            - **DoD**:
              - Run: `echo ok`
            """
        result = self.run_check(design, plan)
        self.assertIn("check.9.id=DoD-Run-Exec", result.stdout)
        self.assertIn("check.9.status=PASS", result.stdout)

    def test_no_dod_run_lines_passes(self) -> None:
        design = """\
            # Design
            ## Goals
            - GOAL1: placeholder
            """
        plan = """\
            # Plan
            ### Task 1: Test task
            - **Dependencies**: none
            - **DoD**:
              - All tests pass
            """
        result = self.run_check(design, plan)
        self.assertIn("check.9.id=DoD-Run-Exec", result.stdout)
        self.assertIn("check.9.status=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
