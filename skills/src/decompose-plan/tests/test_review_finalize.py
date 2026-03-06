import importlib.util
import sys
import tempfile
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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "review_finalize.py"
SPEC = importlib.util.spec_from_file_location("review_finalize", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildRecommendationTests(unittest.TestCase):
    def test_pass_row_recommendation_is_dash(self) -> None:
        self.assertEqual(MODULE.build_recommendation(issues=[]), "-")

    def test_aggregate_recommendation_uses_top_non_ceiling_axes(self) -> None:
        recommendation = MODULE.build_recommendation(
            issues=[],
            axis_scores={
                "Objective": 5,
                "Surface": 3,
                "Verification": 3,
                "Rollback": 1,
            },
            high_axes=[],
            aggregate_exceeded=True,
        )

        self.assertEqual(
            recommendation,
            "Split independently releasable outcomes so this task owns one objective. "
            "Separate unrelated boundaries or top-level path families into different tasks.",
        )

    def test_axis_ceiling_recommendation_uses_axis_template(self) -> None:
        recommendation = MODULE.build_recommendation(
            issues=[],
            axis_scores={
                "Objective": 8,
                "Surface": 1,
                "Verification": 1,
                "Rollback": 1,
            },
            high_axes=["Objective"],
            aggregate_exceeded=False,
        )

        self.assertEqual(
            recommendation,
            "Split independently releasable outcomes so this task owns one objective.",
        )

    def test_invalid_card_recommendation_names_invalid_axes(self) -> None:
        recommendation = MODULE.build_recommendation(
            issues=["invalid objective card `4`", "invalid verification card `9`"],
        )

        self.assertEqual(
            recommendation,
            "Replace invalid objective, verification card values with allowed cards (1, 2, 3, 5, 8) and keep one evidence sentence.",
        )


class ComputeMachineRowsTests(unittest.TestCase):
    def make_row(
        self,
        task: str,
        objective: str,
        surface: str,
        verification: str,
        rollback: str,
        evidence: str = "evidence",
    ) -> dict[str, str]:
        return {
            "task": task,
            "Objective": objective,
            "Surface": surface,
            "Verification": verification,
            "Rollback": rollback,
            "Evidence": evidence,
        }

    def test_missing_row_recommends_adding_one(self) -> None:
        machine_rows, _blockers = MODULE.compute_machine_rows(["Task 1"], [], [])

        self.assertEqual(machine_rows[0].trigger, "missing draft row")
        self.assertEqual(
            machine_rows[0].recommendation,
            "Add one granularity poker row for this task with all four axis cards and one evidence sentence.",
        )

    def test_duplicate_row_recommends_merging_to_one_row(self) -> None:
        machine_rows, _blockers = MODULE.compute_machine_rows(
            ["Task 1"],
            [
                self.make_row("Task 1", "2", "2", "2", "2"),
                self.make_row("Task 1", "2", "2", "2", "2", evidence="duplicate"),
            ],
            [],
        )

        self.assertIn("duplicate draft row", machine_rows[0].trigger)
        self.assertEqual(
            machine_rows[0].recommendation,
            "Keep exactly one granularity poker row for this task and merge duplicate evidence into that row.",
        )

    def test_unknown_task_row_recommends_delete_or_rename(self) -> None:
        machine_rows, _blockers = MODULE.compute_machine_rows(
            ["Task 1"],
            [self.make_row("Task 99", "2", "2", "2", "2")],
            [],
        )

        self.assertEqual(machine_rows[-1].task, "Task 99")
        self.assertEqual(machine_rows[-1].trigger, "unknown task in draft")
        self.assertEqual(
            machine_rows[-1].recommendation,
            "Delete this row or rename it to an existing Task ID from plan.md.",
        )


class RenderFinalReportTests(unittest.TestCase):
    def test_render_final_report_includes_recommendation_column(self) -> None:
        report = MODULE.render_final_report(
            title="Topic - Plan Review",
            digest_stamp="- **Source Digest**: `abc`",
            summary_map=dict.fromkeys(MODULE.SUMMARY_FIELDS, "PASS"),
            structural_ok=True,
            structural_evidence="ok",
            machine_rows=[
                MODULE.MachineRow(
                    task="Task 1",
                    total="8",
                    verdict="PASS",
                    trigger="within machine limit",
                    recommendation="-",
                )
            ],
            findings_body="- None.",
            blocking_body="- None.",
            improvements_body="- None.",
            proceed="yes",
            reason="ok",
        )

        self.assertIn("| Task | Total | Verdict | Trigger | Recommendation |", report)
        self.assertIn("| Task 1 | 8 | PASS | within machine limit | - |", report)
        self.assertIn("- Proceed to `execute-plan`: yes", report)


if __name__ == "__main__":
    unittest.main()
