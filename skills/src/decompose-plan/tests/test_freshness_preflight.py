import hashlib
import importlib.util
import io
import sys
import tempfile
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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "freshness_preflight.py"
SPEC = importlib.util.spec_from_file_location("freshness_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _make_review_artifact(source_artifact: str, source_digest: str) -> str:
    return (
        f"- **Mode**: design-review\n"
        f"- **Source Artifact**: {source_artifact}\n"
        f"- **Source Digest**: {source_digest}\n"
        f"- **Reviewed At**: 2026-01-01T00:00:00Z\n"
        f"- **Overall Verdict**: PASS\n"
    )


class CheckArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def test_fresh_artifact_pass(self) -> None:
        source_content = b"# Design\n"
        source_path = self.tmp / "design.md"
        source_path.write_bytes(source_content)
        digest = _sha256(source_content)

        review = self.tmp / "design.review.md"
        review.write_text(
            _make_review_artifact("design.md", digest), encoding="utf-8"
        )

        status, name, issue = MODULE.check_artifact(review, self.tmp)
        self.assertEqual(status, "PASS")
        self.assertEqual(name, "design.review.md")

    def test_stale_artifact_stale(self) -> None:
        source_path = self.tmp / "design.md"
        source_path.write_bytes(b"# Design v1\n")
        stale_digest = _sha256(b"# Design old\n")

        review = self.tmp / "design.review.md"
        review.write_text(
            _make_review_artifact("design.md", stale_digest), encoding="utf-8"
        )

        status, name, issue = MODULE.check_artifact(review, self.tmp)
        self.assertEqual(status, "STALE")
        self.assertIn("mismatch", issue)

    def test_no_digest_skip(self) -> None:
        review = self.tmp / "design.review.md"
        review.write_text("# Review\n\n- **Overall Verdict**: PASS\n", encoding="utf-8")

        status, name, _ = MODULE.check_artifact(review, self.tmp)
        self.assertEqual(status, "SKIP")

    def test_source_not_found_skip(self) -> None:
        review = self.tmp / "design.review.md"
        review.write_text(
            _make_review_artifact("nonexistent.md", "a" * 64), encoding="utf-8"
        )

        status, name, issue = MODULE.check_artifact(review, self.tmp)
        self.assertEqual(status, "SKIP")
        self.assertIn("not found", issue)


class IntegrationTests(unittest.TestCase):
    def _run(self, topic_dir: Path | None = None) -> tuple[int, str]:
        target = str(topic_dir) if topic_dir else "/nonexistent/topic"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["freshness_preflight.py", target])
        return rc, buf.getvalue()

    def test_no_artifact_files_skip(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        rc, out = self._run(tmp)
        self.assertEqual(rc, 0)
        self.assertIn("status=SKIP", out)
        self.assertIn("NO_REVIEW_ARTIFACTS", out)

    def test_all_fresh_pass(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        source_content = b"# Design\n"
        source_path = tmp / "design.md"
        source_path.write_bytes(source_content)
        digest = _sha256(source_content)

        review = tmp / "design.review.md"
        review.write_text(
            _make_review_artifact("design.md", digest), encoding="utf-8"
        )

        rc, out = self._run(tmp)
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)
        self.assertIn("signal.stale=0", out)

    def test_stale_artifact_fail(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        source_path = tmp / "design.md"
        source_path.write_bytes(b"# Current content\n")
        stale_digest = _sha256(b"# Old content\n")

        review = tmp / "design.review.md"
        review.write_text(
            _make_review_artifact("design.md", stale_digest), encoding="utf-8"
        )

        rc, out = self._run(tmp)
        self.assertEqual(rc, 1)
        self.assertIn("status=FAIL", out)
        self.assertIn("signal.stale=1", out)
        self.assertIn("STALE_REVIEW_ARTIFACTS", out)

    def test_topic_dir_not_found(self) -> None:
        rc, out = self._run()
        self.assertEqual(rc, 1)
        self.assertIn("TOPIC_DIR_NOT_FOUND", out)


if __name__ == "__main__":
    unittest.main()
