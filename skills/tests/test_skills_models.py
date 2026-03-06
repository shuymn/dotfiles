import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

COMMON_LIB_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "common" / "scripts" / "lib"
)
if str(COMMON_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_LIB_DIR))

from skills_models import (  # noqa: E402
    BoundaryInventoryRowModel,
    GranularityCardValuesModel,
    ManagedSkillsManifestModel,
    TableFragmentModel,
)


def test_table_fragment_rejects_mismatched_row_width() -> None:
    with pytest.raises(ValidationError):
        TableFragmentModel.model_validate(
            {
                "kind": "table",
                "headers": ["A", "B"],
                "rows": [["1"]],
            }
        )


def test_manifest_rejects_empty_skill_name() -> None:
    with pytest.raises(ValidationError):
        ManagedSkillsManifestModel.model_validate(
            {
                "version": 1,
                "source_root": ".",
                "skills": ["valid-skill", ""],
            }
        )


def test_boundary_inventory_requires_yes_or_no_parallel_stream() -> None:
    with pytest.raises(ValidationError):
        BoundaryInventoryRowModel.model_validate(
            {
                "boundary": "API",
                "owns_requirements_ac": "AC01",
                "primary_verification_surface": "pytest",
                "temp_lifecycle_group": "none",
                "parallel_stream": "maybe",
                "depends_on": "none",
            }
        )


def test_granularity_cards_reject_invalid_card() -> None:
    with pytest.raises(ValidationError):
        GranularityCardValuesModel.model_validate(
            {
                "objective": 4,
                "surface": 1,
                "verification": 1,
                "rollback": 1,
            }
        )
