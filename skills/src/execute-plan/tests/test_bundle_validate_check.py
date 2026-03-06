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

MODULE_PATH = ARTIFACT_ROOT / "execute-plan" / "scripts" / "bundle_validate_check.py"
SPEC = importlib.util.spec_from_file_location("bundle_validate_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_ALL_KEYS = (
    "Alignment Verdict",
    "Forward Fidelity",
    "Reverse Fidelity",
    "Non-Goal Guard",
    "Behavioral Lock Guard",
    "Temporal Completeness Guard",
    "Quality Gate Guard",
    "Integration Coverage Guard",
    "Risk Classification Guard",
    "Trace Pack",
    "Compose Pack",
    "Updated At",
)


def _make_checkpoint(extra: dict[str, str] | None = None) -> str:
    kv = {k: "PASS" for k in _ALL_KEYS}
    kv["Trace Pack"] = "docs/plans/topic/plan.trace.md"
    kv["Compose Pack"] = "docs/plans/topic/plan.compose.md"
    kv["Updated At"] = "2026-01-01"
    if extra:
        kv.update(extra)
    lines = "\n".join(f"- **{k}**: {v}" for k, v in kv.items())
    return f"## Checkpoint Summary\n\n{lines}\n"


class ParseKvTests(unittest.TestCase):
    def test_parses_bold_kv(self) -> None:
        text = "- **Key One**: value1\n- **Key Two**: value2\n"
        kv = MODULE._parse_kv(text)
        self.assertEqual(kv["Key One"], "value1")
        self.assertEqual(kv["Key Two"], "value2")


class IntegrationTests(unittest.TestCase):
    def _run(self, plan_content: str, extra_files: dict[str, str] | None = None) -> tuple[int, str]:
        tmp_dir = Path(tempfile.mkdtemp())
        plan_path = tmp_dir / "plan.md"
        plan_path.write_text(textwrap.dedent(plan_content), encoding="utf-8")
        if extra_files:
            for rel, content in extra_files.items():
                (tmp_dir / rel).write_text(content, encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["bundle_validate_check.py", str(plan_path)])
        return rc, buf.getvalue()

    def _full_valid_plan(self, tmp_dir: Path | None = None) -> tuple[str, dict[str, str]]:
        checkpoint = _make_checkpoint()
        plan = f"# Plan\n\n{checkpoint}\n"
        sidecars = {
            "docs/plans/topic/plan.trace.md": "# trace\n",
            "docs/plans/topic/plan.compose.md": "# compose\n",
        }
        return plan, sidecars

    def test_valid_bundle_pass(self) -> None:
        tmp_dir = Path(tempfile.mkdtemp())
        checkpoint = _make_checkpoint()
        plan = f"# Plan\n\n{checkpoint}\n"
        plan_path = tmp_dir / "plan.md"
        plan_path.write_text(plan, encoding="utf-8")
        trace_path = tmp_dir / "docs" / "plans" / "topic" / "plan.trace.md"
        trace_path.parent.mkdir(parents=True)
        trace_path.write_text("# trace\n", encoding="utf-8")
        compose_path = tmp_dir / "docs" / "plans" / "topic" / "plan.compose.md"
        compose_path.write_text("# compose\n", encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["bundle_validate_check.py", str(plan_path)])
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", buf.getvalue())

    def test_missing_checkpoint_section_fail(self) -> None:
        rc, out = self._run("# Plan\n\nNo checkpoint here.\n")
        self.assertEqual(rc, 1)
        self.assertIn("NO_CHECKPOINT_SUMMARY", out)

    def test_missing_key_fail(self) -> None:
        kv_lines = "\n".join(
            f"- **{k}**: PASS"
            for k in _ALL_KEYS
            if k != "Alignment Verdict"
        )
        plan = f"# Plan\n\n## Checkpoint Summary\n\n{kv_lines}\n"
        rc, out = self._run(plan)
        self.assertEqual(rc, 1)
        self.assertIn("Alignment Verdict", out)

    def test_alignment_verdict_not_pass_fail(self) -> None:
        checkpoint = _make_checkpoint({"Alignment Verdict": "FAIL"})
        plan = f"# Plan\n\n{checkpoint}\n"
        rc, out = self._run(plan)
        self.assertEqual(rc, 1)
        self.assertIn("Alignment Verdict", out)

    def test_file_not_found(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["bundle_validate_check.py", "/nonexistent/plan.md"])
        self.assertEqual(rc, 1)
        self.assertIn("PLAN_FILE_NOT_FOUND", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
