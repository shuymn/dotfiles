import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "_shared" / "scripts" / "split_check.py"
SPEC = importlib.util.spec_from_file_location("split_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

WRAPPER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "split-check.sh"


class SplitCheckTests(unittest.TestCase):
    maxDiff = None

    def write_file(self, root: Path, relative_path: str, content: str) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def single_design(self) -> str:
        return """
        # Topic - Design

        ## Decomposition Strategy

        - Split Decision: single
        - Decision Basis: One owned boundary; verification stays unified.
        - Root Scope: Single CLI boundary.

        ### Boundary Inventory

        | Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
        |----------|----------------------|------------------------------|----------------------|-----------------|------------|
        | CLI Runtime | REQ01; AC01 | cli-smoke | none | no | none |

        ## Acceptance Criteria

        | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
        |-------|-----------|---------------|----------------------|---------------------|----------------------|
        | AC01 | Ubiquitous | behavioral | The CLI shall execute the sync path. | CLI smoke returns success. | `make list` |
        """

    def single_but_should_split(self) -> str:
        return """
        # Topic - Design

        ## Decomposition Strategy

        - Split Decision: single
        - Decision Basis: Placeholder rationale.
        - Root Scope: API and worker boundaries.

        ### Boundary Inventory

        | Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
        |----------|----------------------|------------------------------|----------------------|-----------------|------------|
        | Public API | REQ01; AC01 | api-contract | none | yes | none |
        | Worker | REQ02; AC02 | integration-job | none | yes | Public API |

        ## Acceptance Criteria

        | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
        |-------|-----------|---------------|----------------------|---------------------|----------------------|
        | AC01 | Ubiquitous | api-contract | The API shall accept jobs. | Contract test passes. | `make list` |
        | AC02 | Ubiquitous | behavioral | The worker shall process jobs. | Worker smoke passes. | `make list` |
        """

    def root_sub_design(self) -> tuple[str, dict[str, str]]:
        design = """
        # Topic - Design

        ## Decomposition Strategy

        - Split Decision: root-sub
        - Decision Basis: Two owned boundaries with distinct verification surfaces.
        - Root Scope: Shared constraints and integration-only responsibilities.

        ### Boundary Inventory

        | Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
        |----------|----------------------|------------------------------|----------------------|-----------------|------------|
        | Public API | REQ-API; AC-API | api-contract | none | yes | none |
        | Worker | REQ-WORKER; AC-WORKER | job-integration | none | yes | Public API |
        | Integration | Integration-only | end-to-end | none | no | Public API, Worker |

        ### Sub-Doc Index

        | Sub ID | File | Owned Boundary | Owns Requirements/AC |
        |--------|------|----------------|----------------------|
        | SUB-API | docs/plans/topic/api-design.md | Public API | REQ-API; AC-API |
        | SUB-WORKER | docs/plans/topic/worker-design.md | Worker | REQ-WORKER; AC-WORKER |

        ### Root Coverage

        | Root Requirement/AC | Covered By (Sub ID or Integration) | Notes |
        |---------------------|------------------------------------|-------|
        | ROOT-AC-01 | Integration | end-to-end |

        ## Acceptance Criteria

        | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
        |-------|-----------|---------------|----------------------|---------------------|----------------------|
        | ROOT-AC-01 | Event-Driven | behavioral | When the API accepts a job, the system shall complete the job through the worker. | End-to-end flow passes. | `make list` |
        """
        subdocs = {
            "docs/plans/topic/api-design.md": """
            # Topic - API Sub-Design

            ## Sub-Doc Metadata

            - Sub ID: SUB-API
            - Root Design: `docs/plans/topic/design.md`
            - Owned Boundary: Public API

            ## Local Requirements

            - REQ-API: Accept job submission.

            ## Local Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC-API | Ubiquitous | api-contract | The API shall validate and enqueue jobs. | API contract passes. | `make list` |
            """,
            "docs/plans/topic/worker-design.md": """
            # Topic - Worker Sub-Design

            ## Sub-Doc Metadata

            - Sub ID: SUB-WORKER
            - Root Design: `docs/plans/topic/design.md`
            - Owned Boundary: Worker

            ## Local Requirements

            - REQ-WORKER: Process enqueued jobs.

            ## Local Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC-WORKER | Ubiquitous | behavioral | The worker shall process queued jobs. | Worker integration passes. | `make list` |
            """,
        }
        return design, subdocs

    def root_sub_with_one_effective_subdoc(self) -> tuple[str, dict[str, str]]:
        design, subdocs = self.root_sub_design()
        subdocs["docs/plans/topic/worker-design.md"] = """
        # Topic - Worker Sub-Design

        ## Sub-Doc Metadata

        - Sub ID: SUB-WORKER
        - Root Design: `docs/plans/topic/design.md`
        - Owned Boundary: Worker

        ## Local Requirements

        - REQ-WORKER: Process enqueued jobs.

        ## Local Acceptance Criteria

        | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
        |-------|-----------|---------------|----------------------|---------------------|----------------------|
        """
        return design, subdocs

    def advisory_root_sub_design(self) -> tuple[str, dict[str, str]]:
        design = """
        # Topic - Design

        ## Decomposition Strategy

        - Split Decision: root-sub
        - Decision Basis: Distinct API and worker boundaries.
        - Root Scope: Shared coordination and integration behavior.

        ### Boundary Inventory

        | Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
        |----------|----------------------|------------------------------|----------------------|-----------------|------------|
        | Public API | REQ-API; AC-API-* | api-contract | none | yes | Worker |
        | Worker | REQ-WORKER; AC-WORKER | job-integration | none | yes | Public API |

        ### Sub-Doc Index

        | Sub ID | File | Owned Boundary | Owns Requirements/AC |
        |--------|------|----------------|----------------------|
        | SUB-API | docs/plans/topic/api-design.md | Public API | REQ-API; AC-API-* |
        | SUB-WORKER | docs/plans/topic/worker-design.md | Worker | REQ-WORKER; AC-WORKER |

        ### Root Coverage

        | Root Requirement/AC | Covered By (Sub ID or Integration) | Notes |
        |---------------------|------------------------------------|-------|
        | ROOT-AC-01 | Integration | coordination |

        ## Acceptance Criteria

        | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
        |-------|-----------|---------------|----------------------|---------------------|----------------------|
        | ROOT-AC-01 | Event-Driven | behavioral | When the API schedules work, the system shall complete the worker flow. | End-to-end passes. | `make list` |
        | ROOT-AC-02 | Event-Driven | behavioral | When retries occur, the integrated flow shall remain observable. | End-to-end passes. | `make list` |
        | ROOT-AC-03 | Event-Driven | behavioral | When jobs fail, integration alerts shall trigger. | End-to-end passes. | `make list` |
        | ROOT-AC-04 | Event-Driven | behavioral | When jobs succeed, integration telemetry shall emit. | End-to-end passes. | `make list` |
        """
        subdocs = {
            "docs/plans/topic/api-design.md": """
            # Topic - API Sub-Design

            ## Sub-Doc Metadata

            - Sub ID: SUB-API
            - Root Design: `docs/plans/topic/design.md`
            - Owned Boundary: Public API

            ## Local Requirements

            - REQ-API: Accept jobs.

            ## Local Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC-API-01 | Ubiquitous | api-contract | The API shall validate jobs. | API contract passes. | `make list` |
            | AC-API-02 | Ubiquitous | api-contract | The API shall persist jobs. | API contract passes. | `make list` |
            | AC-API-03 | Ubiquitous | api-contract | The API shall expose retry metadata. | API contract passes. | `make list` |
            """,
            "docs/plans/topic/worker-design.md": """
            # Topic - Worker Sub-Design

            ## Sub-Doc Metadata

            - Sub ID: SUB-WORKER
            - Root Design: `docs/plans/topic/design.md`
            - Owned Boundary: Worker

            ## Local Requirements

            - REQ-WORKER: Process jobs.

            ## Local Acceptance Criteria

            | AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
            |-------|-----------|---------------|----------------------|---------------------|----------------------|
            | AC-WORKER | Ubiquitous | behavioral | The worker shall complete queued jobs. | Worker integration passes. | `make list` |
            """,
        }
        return design, subdocs

    def materialize(self, design_text: str, subdocs: dict[str, str] | None = None) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        design_path = self.write_file(temp_dir, "docs/plans/topic/design.md", design_text)
        for relative_path, content in (subdocs or {}).items():
            self.write_file(temp_dir, relative_path, content)
        return design_path

    def run_check(self, design_text: str, subdocs: dict[str, str] | None = None):
        design_path = self.materialize(design_text, subdocs)
        data = MODULE.parse_design_doc(design_path)
        return MODULE.analyze_design_doc(data)

    def test_valid_single_passes(self):
        result = self.run_check(self.single_design())
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.signals["owned_boundary_count"], "1")
        self.assertEqual(result.advisories, [])

    def test_single_blocks_when_root_sub_is_required(self):
        result = self.run_check(self.single_but_should_split())
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("Split Decision: single" in blocker for blocker in result.blockers))

    def test_valid_root_sub_passes(self):
        design, subdocs = self.root_sub_design()
        result = self.run_check(design, subdocs)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.signals["effective_subdoc_count"], "2")
        self.assertEqual(result.advisories, [])

    def test_root_sub_blocks_when_only_one_subdoc_is_effective(self):
        design, subdocs = self.root_sub_with_one_effective_subdoc()
        result = self.run_check(design, subdocs)
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("effective sub-docs" in blocker for blocker in result.blockers))

    def test_root_sub_can_emit_advisories_without_failing(self):
        design, subdocs = self.advisory_root_sub_design()
        result = self.run_check(design, subdocs)
        self.assertEqual(result.status, "PASS")
        self.assertGreaterEqual(len(result.advisories), 2)
        self.assertTrue(any("Root integration AC count" in advisory for advisory in result.advisories))

    def test_design_doc_wrapper_returns_pass_with_advisories(self):
        design, subdocs = self.advisory_root_sub_design()
        design_path = self.materialize(design, subdocs)
        completed = subprocess.run(
            [str(WRAPPER_PATH), str(design_path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=design_path.parents[3],
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("status=PASS", completed.stdout)
        self.assertIn("advisory.count=2", completed.stdout)


if __name__ == "__main__":
    unittest.main()
