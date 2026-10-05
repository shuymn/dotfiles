import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/dot_local/private_bin/executable_capsule-mise-drift"


class CapsuleMiseDriftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        jq = shutil.which("jq")
        self.assertIsNotNone(jq, "jq is required")
        (self.bin / "jq").symlink_to(jq)
        self.env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.root),
            "MOCK_RECORDS": json.dumps([{"version": "1.27.1"}]),
            "MOCK_VERSION": "go version go1.26.0 darwin/arm64",
            "MOCK_LOG": str(self.root / "mise.log"),
        }
        self.mock("mise", 'printf "%s\\n" "$MISE_OFFLINE" "$@" > "$MOCK_LOG"\n'
                  'printf "%s\\n" "$MOCK_RECORDS"\nexit "${MOCK_MISE_EXIT:-0}"')
        for tool in ("go", "bun", "node", "python3", "rustc", "php"):
            self.mock(tool, 'printf "%s\\n" "$MOCK_VERSION"\nexit "${MOCK_RUNTIME_EXIT:-0}"')

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_helper(self, tool="go"):
        return subprocess.run(["/bin/sh", str(SCRIPT), tool], env=self.env,
                              cwd=self.root, capture_output=True, text=True, timeout=5)

    def assert_hidden(self, tool="go"):
        result = self.run_helper(tool)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_drift_is_project_scoped_and_offline(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "1.27.1\n")
        self.assertEqual((self.root / "mise.log").read_text().splitlines(),
                         ["1", "ls", "--local", "--current", "go", "--json"])

    def test_agreement_and_drift_for_each_runtime(self):
        outputs = {
            "go": "go version go1.27.1 darwin/arm64",
            "node": "v1.27.1", "bun": "1.27.1", "python": "Python 1.27.1",
            "rust": "rustc 1.27.1 (build hash)", "php": "PHP 1.27.1 (cli)",
        }
        for tool, output in outputs.items():
            with self.subTest(tool=tool):
                self.env["MOCK_VERSION"] = output
                self.assert_hidden(tool)
                self.env["MOCK_RECORDS"] = json.dumps([{"version": "1.28.0"}])
                result = self.run_helper(tool)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "1.28.0\n")
                self.env["MOCK_RECORDS"] = json.dumps([{"version": "1.27.1"}])

    def test_missing_or_unresolved_project_version_is_hidden(self):
        for records in ([], [{"version": "latest"}], [{"version": "nightly"}],
                        [{"version": None}], [{"requested_version": "1.27"}]):
            with self.subTest(records=records):
                self.env["MOCK_RECORDS"] = json.dumps(records)
                self.assert_hidden()

    def test_query_failure_and_invalid_json_are_hidden(self):
        self.env["MOCK_MISE_EXIT"] = "1"
        self.assert_hidden()
        self.env["MOCK_MISE_EXIT"] = "0"
        self.env["MOCK_RECORDS"] = "not JSON"
        self.assert_hidden()

    def test_failed_or_missing_runtime_is_hidden(self):
        self.env["MOCK_RUNTIME_EXIT"] = "1"
        self.assert_hidden()
        self.env["MOCK_RUNTIME_EXIT"] = "0"
        (self.bin / "go").unlink()
        self.assert_hidden()

    def test_primary_requested_version_is_used(self):
        self.env["MOCK_RECORDS"] = json.dumps([{"version": "1.27.1"}, {"version": "1.26.0"}])
        self.assertEqual(self.run_helper().stdout, "1.27.1\n")

    def test_prerelease_difference_is_drift(self):
        self.env["MOCK_VERSION"] = "rustc 1.27.1-nightly (build hash)"
        self.assertEqual(self.run_helper("rust").stdout, "1.27.1\n")

    def test_unsupported_tool_is_hidden_without_query(self):
        self.assert_hidden("unknown")
        self.assertFalse((self.root / "mise.log").exists())


if __name__ == "__main__":
    unittest.main()
