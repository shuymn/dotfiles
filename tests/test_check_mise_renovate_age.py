from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).resolve().parents[1] / "scripts/check-mise-renovate-age.py"


def run_config_check(config: dict[str, object]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "renovate.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECKER), "check-renovate-config", str(config_path)],
            check=False,
            capture_output=True,
            text=True,
        )


class CheckRenovateConfigTests(unittest.TestCase):
    def test_accepts_reconciler_owned_mise_lock_configuration(self) -> None:
        result = run_config_check(
            {
                "platformAutomerge": True,
                "packageRules": [
                    {
                        "matchManagers": ["mise"],
                        "lockFileMaintenance": {"enabled": False},
                        "skipArtifactsUpdate": True,
                    }
                ],
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_missing_mise_lock_file_maintenance_setting(self) -> None:
        result = run_config_check(
            {
                "platformAutomerge": True,
                "packageRules": [
                    {
                        "matchManagers": ["mise"],
                        "skipArtifactsUpdate": True,
                    }
                ],
            }
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("lockFileMaintenance.enabled=false", result.stderr)


if __name__ == "__main__":
    unittest.main()
