import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "build_skills.py"
SPEC = importlib.util.spec_from_file_location("build_skills", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SOURCE_ROOT = PROJECT_ROOT / "src"


def snapshot_tree(root: Path) -> dict[str, tuple[str, int]]:
    snapshot: dict[str, tuple[str, int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"{relative}/"] = ("dir", 0)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[relative] = (digest, path.stat().st_mode & 0o777)
    return snapshot


def build_to_temp_dir() -> Path:
    artifact_root = Path(tempfile.mkdtemp()) / "artifacts"
    MODULE.build_skills(SOURCE_ROOT, artifact_root)
    return artifact_root


def test_source_skills_have_no_parent_traversal_helper_refs() -> None:
    for skill_root in sorted(SOURCE_ROOT.iterdir()):
        if skill_root.name in {"common", "tests"} or not skill_root.is_dir():
            continue
        assert not list(skill_root.rglob("scripts/lib"))
        for path in sorted(skill_root.rglob("*")):
            if not path.is_file() or path.suffix not in {".md", ".py", ".sh", ".txt"}:
                continue
            contents = path.read_text(encoding="utf-8")
            assert "../../common/scripts/" not in contents, path.as_posix()
            assert "../_shared" not in contents, path.as_posix()
            assert "../../_shared" not in contents, path.as_posix()
    assert (
        SOURCE_ROOT / "common" / "scripts" / "lib" / "llm-check-output.sh"
    ).is_file()
    assert (SOURCE_ROOT / "common" / "scripts" / "lib" / "path-display.sh").is_file()


def test_source_markdown_uses_explicit_skill_root_for_runtime_refs() -> None:
    for skill_root in sorted(SOURCE_ROOT.iterdir()):
        if skill_root.name in {"common", "tests"} or not skill_root.is_dir():
            continue
        MODULE.validate_explicit_skill_root_paths(skill_root)


def test_build_outputs_standalone_artifacts() -> None:
    artifact_root = build_to_temp_dir()

    assert (artifact_root / ".dotfiles-managed-skills.json").is_file()
    assert not (artifact_root / "_shared").exists()
    assert not list(artifact_root.rglob("tests"))
    assert not list(artifact_root.rglob("__pycache__"))
    assert (artifact_root / "design-doc" / "scripts" / "split_check.py").is_file()
    assert not (artifact_root / "design-doc" / "scripts" / "split-check.sh").exists()
    assert (artifact_root / "setup-ralph" / "scripts" / "gate-check.sh").is_file()
    assert not (
        artifact_root / "design-doc" / "scripts" / "llm-check-output.sh"
    ).exists()
    assert not (artifact_root / "design-doc" / "scripts" / "path-display.sh").exists()
    assert (
        artifact_root / "design-doc" / "scripts" / "lib" / "llm-check-output.sh"
    ).is_file()
    assert (
        artifact_root / "design-doc" / "scripts" / "lib" / "path-display.sh"
    ).is_file()
    assert not (artifact_root / "design-doc" / "skill.json").exists()


def test_build_is_idempotent() -> None:
    artifact_root = build_to_temp_dir()
    first_snapshot = snapshot_tree(artifact_root)

    MODULE.build_skills(SOURCE_ROOT, artifact_root)
    second_snapshot = snapshot_tree(artifact_root)

    assert first_snapshot == second_snapshot


def test_build_entrypoint_runs_from_artifact() -> None:
    artifact_root = build_to_temp_dir()
    design_path = artifact_root / "sample-design.md"
    design_path.write_text(
        textwrap.dedent(
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
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(artifact_root / "design-doc" / "scripts" / "split_check.py"),
            str(design_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=artifact_root,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "status=PASS" in completed.stdout


def test_built_shell_scripts_are_executable() -> None:
    artifact_root = build_to_temp_dir()
    shell_scripts = sorted(
        path
        for path in artifact_root.rglob("*.sh")
        if path.name in {"digest-stamp.sh", "gate-check.sh"}
    )

    assert shell_scripts
    for path in shell_scripts:
        assert os.access(path, os.X_OK), path.as_posix()
