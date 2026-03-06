import importlib.util
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
BUILD_SPEC.loader.exec_module(BUILD_MODULE)

ARTIFACT_ROOT = Path(tempfile.mkdtemp()) / "artifacts"
BUILD_MODULE.build_skills(SOURCE_ROOT, ARTIFACT_ROOT)

CLI_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "split_check.py"


class SplitCheckGateTests(unittest.TestCase):
    def write_file(self, root: Path, relative_path: str, content: str) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def run_wrapper(self, design_content: str) -> subprocess.CompletedProcess[str]:
        temp_dir = Path(tempfile.mkdtemp())
        design_path = self.write_file(
            temp_dir, "docs/plans/topic/design.md", design_content
        )
        return subprocess.run(
            [sys.executable, str(CLI_PATH), str(design_path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=temp_dir,
        )

    def test_gate_wrapper_fails_for_blocking_single_design(self):
        completed = self.run_wrapper(
            """
            # Topic - Design

            ## Decomposition Strategy

            - Split Decision: single
            - Decision Basis: Placeholder.
            - Root Scope: API and worker.

            ### Boundary Inventory

            | Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
            |----------|----------------------|------------------------------|----------------------|-----------------|------------|
            | Public API | REQ01; AC01 | api-contract | none | yes | none |
            | Worker | REQ02; AC02 | worker-integration | none | yes | Public API |

            ## Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC01 | Ubiquitous | behavioral | The API shall accept work. | Contract passes. | `make list` |
            | AC02 | Ubiquitous | behavioral | The worker shall process work. | Integration passes. | `make list` |
            """
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("status=FAIL", completed.stdout)
        self.assertIn("blocker.count=1", completed.stdout)

    def test_gate_wrapper_passes_for_single_boundary_design(self):
        completed = self.run_wrapper(
            """
            # Topic - Design

            ## Decomposition Strategy

            - Split Decision: single
            - Decision Basis: One owned boundary.
            - Root Scope: Single runtime boundary.

            ### Boundary Inventory

            | Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
            |----------|----------------------|------------------------------|----------------------|-----------------|------------|
            | CLI Runtime | REQ01; AC01 | cli-smoke | none | no | none |

            ## Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC01 | Ubiquitous | behavioral | The CLI shall execute the sync path. | CLI smoke passes. | `make list` |
            """
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("status=PASS", completed.stdout)
        self.assertIn("blocker.count=0", completed.stdout)


if __name__ == "__main__":
    unittest.main()
