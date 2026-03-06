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

MODULE_PATH = (
    ARTIFACT_ROOT / "adversarial-verify" / "scripts" / "adversarial_coverage_check.py"
)
SPEC = importlib.util.spec_from_file_location("adversarial_coverage_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_ATTACK_VECTORS_MD = textwrap.dedent("""\
    # Attack Vectors

    ## 1. Input Boundary Attacks

    Target: Input validation.

    - **Empty/null values** [required]: Pass empty strings.
    - **Injection** [required]: SQL injection, command injection.
    - **Type coercion**: Wrong type inputs.

    ## 2. Error Handling Attacks

    Target: Failure paths.

    - **Invalid state transitions** [required]: Call methods in wrong order.
    - **Retry storms**: Unbounded retries.
""")

_ATTACK_SUMMARY_ALL_COVERED = textwrap.dedent("""\
    ## Attack Summary

    | # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
    |---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
    | 1 | Input Boundary Attacks | Empty/null values | yes | t.py | pytest | 0 | DEFENDED | ok |
    | 2 | Input Boundary Attacks | Injection | yes | t.py | pytest | 0 | DEFENDED | ok |
""")

_ATTACK_SUMMARY_MISSING_INJECTION = textwrap.dedent("""\
    ## Attack Summary

    | # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
    |---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
    | 1 | Input Boundary Attacks | Empty/null values | yes | t.py | pytest | 0 | DEFENDED | ok |
""")


class ParseAttackVectorsTests(unittest.TestCase):
    def test_parses_categories_and_required_tags(self) -> None:
        cats = MODULE.parse_attack_vectors(_ATTACK_VECTORS_MD)
        # Category keys strip the number prefix (group(2) of "## N. Name")
        self.assertIn("Input Boundary Attacks", cats)
        vectors = cats["Input Boundary Attacks"]
        req_names = [name for name, req in vectors if req]
        self.assertIn("Empty/null values", req_names)
        self.assertIn("Injection", req_names)
        # Type coercion is not required
        non_req = [name for name, req in vectors if not req]
        self.assertIn("Type coercion", non_req)

    def test_parses_error_handling_category(self) -> None:
        cats = MODULE.parse_attack_vectors(_ATTACK_VECTORS_MD)
        self.assertIn("Error Handling Attacks", cats)


class CheckCoverageTests(unittest.TestCase):
    def _make_rows(self, vectors: list[str], category: str) -> list[dict[str, str]]:
        return [
            {
                "Category": category,
                "Attack Vector": v,
                "Result": "DEFENDED",
                "Evidence": "ok",
            }
            for v in vectors
        ]

    def test_all_required_covered_pass(self) -> None:
        attack_vectors = MODULE.parse_attack_vectors(_ATTACK_VECTORS_MD)
        selected = ["Input Boundary Attacks"]
        rows = self._make_rows(
            ["Empty/null values", "Injection"], "Input Boundary Attacks"
        )
        issues = MODULE.check_coverage(selected, attack_vectors, rows, "Critical")
        self.assertEqual(issues, [])

    def test_missing_required_vector_fail(self) -> None:
        attack_vectors = MODULE.parse_attack_vectors(_ATTACK_VECTORS_MD)
        selected = ["Input Boundary Attacks"]
        rows = self._make_rows(["Empty/null values"], "Input Boundary Attacks")
        issues = MODULE.check_coverage(selected, attack_vectors, rows, "Critical")
        self.assertEqual(len(issues), 1)
        self.assertIn("Injection", issues[0])

    def test_na_documented_counts_as_covered(self) -> None:
        attack_vectors = MODULE.parse_attack_vectors(_ATTACK_VECTORS_MD)
        selected = ["Input Boundary Attacks"]
        rows = [
            {
                "Category": "Input Boundary Attacks",
                "Attack Vector": "Empty/null values",
                "Result": "DEFENDED",
                "Evidence": "ok",
            },
            {
                "Category": "Input Boundary Attacks",
                "Attack Vector": "Injection",
                "Result": "N/A",
                "Evidence": "not applicable: no external input",
            },
        ]
        issues = MODULE.check_coverage(selected, attack_vectors, rows, "Critical")
        self.assertEqual(issues, [])

    def test_standard_tier_no_obligation(self) -> None:
        attack_vectors = MODULE.parse_attack_vectors(_ATTACK_VECTORS_MD)
        issues = MODULE.check_coverage(["Input Boundary Attacks"], attack_vectors, [], "Standard")
        self.assertEqual(issues, [])


class IntegrationTests(unittest.TestCase):
    def _run(self, report: str, vectors: str, tier: str) -> tuple[int, str]:
        tmp = Path(tempfile.mkdtemp())
        report_path = tmp / "report.adversarial.md"
        vectors_path = tmp / "attack-vectors.md"
        report_path.write_text(textwrap.dedent(report), encoding="utf-8")
        vectors_path.write_text(vectors, encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main([
                "adversarial_coverage_check.py",
                str(report_path),
                str(vectors_path),
                "--tier", tier,
            ])
        return rc, buf.getvalue()

    def test_standard_tier_skip(self) -> None:
        rc, out = self._run("# Report\n", _ATTACK_VECTORS_MD, "Standard")
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)

    def test_all_covered_pass(self) -> None:
        rc, out = self._run(_ATTACK_SUMMARY_ALL_COVERED, _ATTACK_VECTORS_MD, "Critical")
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)

    def test_missing_vector_fail(self) -> None:
        rc, out = self._run(_ATTACK_SUMMARY_MISSING_INJECTION, _ATTACK_VECTORS_MD, "Critical")
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", out)
        self.assertIn("Injection", out)

    def test_file_not_found(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main([
                "adversarial_coverage_check.py",
                "/nonexistent/report.md",
                "/nonexistent/vectors.md",
                "--tier", "Critical",
            ])
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
