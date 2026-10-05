from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from scripts.mise_update_policy import (
    Hold,
    Release,
    UpdatePolicyError,
    parse_timestamp,
    releases_from_metadata,
    render_pull_request,
    replace_version,
    select_update,
    validated_changes,
)

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)


def released(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


class SelectUpdateTests(unittest.TestCase):
    def select(self, current: str, releases: list[Release]):
        return select_update("tool", current, releases, now=NOW, minimum_age=DAY)

    def test_picks_newest_release_past_minimum_age_in_same_major(self) -> None:
        decision = self.select(
            "1.2.0",
            [
                Release("1.2.1", released(10)),
                Release("1.3.0", released(3)),
                Release("1.4.0", released(0.5)),
                Release("2.0.0", released(20)),
            ],
        )

        self.assertEqual(decision.target, Release("1.3.0", released(3)))
        self.assertEqual(
            decision.holds,
            (
                Hold("2.0.0", "major update"),
                Hold("1.4.0", "released less than the minimum age ago"),
            ),
        )

    def test_never_selects_releases_without_timestamps(self) -> None:
        decision = self.select("1.2.0", [Release("1.2.1", None)])

        self.assertIsNone(decision.target)
        self.assertEqual(decision.holds, (Hold("1.2.1", "no release timestamp"),))

    def test_ignores_prereleases_and_older_versions(self) -> None:
        decision = self.select(
            "1.2.0",
            [
                Release("1.3.0rc1", released(5)),
                Release("1.1.9", released(5)),
                Release("1.2.0", released(9)),
            ],
        )

        self.assertIsNone(decision.target)
        self.assertEqual(decision.holds, ())

    def test_keeps_the_configured_v_prefix_style(self) -> None:
        with_prefix = self.select("v0.9.0", [Release("0.9.3", released(2))])
        without_prefix = self.select("0.9.0", [Release("v0.9.3", released(2))])

        self.assertEqual(with_prefix.target.version, "v0.9.3")
        self.assertEqual(without_prefix.target.version, "0.9.3")

    def test_reports_unsupported_current_versions(self) -> None:
        decision = self.select("latest", [Release("1.0.0", released(2))])

        self.assertIsNone(decision.target)
        self.assertEqual(decision.holds, (Hold("latest", "unsupported version format"),))


class MetadataTests(unittest.TestCase):
    def test_date_only_timestamps_count_from_the_end_of_the_day(self) -> None:
        self.assertEqual(parse_timestamp("2026-09-21"), datetime(2026, 9, 22, tzinfo=UTC))

    def test_offsets_are_normalized_to_utc(self) -> None:
        self.assertEqual(
            parse_timestamp("2026-10-01T07:41:27+03:00"), datetime(2026, 10, 1, 4, 41, 27, tzinfo=UTC)
        )

    def test_skips_prereleases_and_malformed_entries(self) -> None:
        releases = releases_from_metadata(
            [
                {"version": "1.0.0", "created_at": "2026-10-01T00:00:00Z"},
                {"version": "1.1.0", "created_at": "2026-10-02T00:00:00Z", "prerelease": True},
                {"created_at": "2026-10-02T00:00:00Z"},
                {"version": "1.0.1", "created_at": "not a date"},
            ]
        )

        self.assertEqual(
            releases,
            [Release("1.0.0", datetime(2026, 10, 1, tzinfo=UTC)), Release("1.0.1", None)],
        )


CONFIG = """\
[settings]
go = "1.0.0"

[tools]
# runtimes
go = "1.27.1"
"github:k1LoW/git-wt" = "v0.29.3" # pinned helper

[tasks.lint]
run = "go vet"
"""


class ReplaceVersionTests(unittest.TestCase):
    def test_replaces_only_the_matching_tools_entry(self) -> None:
        updated = replace_version(CONFIG, "go", "1.27.1", "1.27.2")

        self.assertEqual(updated, CONFIG.replace('go = "1.27.1"', 'go = "1.27.2"'))

    def test_handles_quoted_keys_and_trailing_comments(self) -> None:
        updated = replace_version(CONFIG, "github:k1LoW/git-wt", "v0.29.3", "v0.30.0")

        self.assertIn('"github:k1LoW/git-wt" = "v0.30.0" # pinned helper', updated)

    def test_rejects_missing_entries(self) -> None:
        with self.assertRaisesRegex(UpdatePolicyError, "found 0"):
            replace_version(CONFIG, "go", "1.26.0", "1.27.2")


class PullRequestTests(unittest.TestCase):
    def test_accepts_forward_updates_within_a_major_line(self) -> None:
        head = CONFIG.replace('go = "1.27.1"', 'go = "1.28.0"')

        self.assertEqual(validated_changes(CONFIG, head), [("go", "1.27.1", "1.28.0")])

    def test_rejects_downgrades_major_updates_and_non_numeric_versions(self) -> None:
        for version in ("1.27.0", "2.0.0", "1.28.0-evil"):
            with self.subTest(version=version), self.assertRaises(UpdatePolicyError):
                validated_changes(CONFIG, CONFIG.replace('go = "1.27.1"', f'go = "{version}"'))

    def test_title_names_up_to_three_tools(self) -> None:
        changes = [(name, "1.0.0", "1.0.1") for name in ("a", "b", "c", "d", "e")]

        title, body = render_pull_request(changes, run_url="https://example.com/run")

        self.assertEqual(title, "Update mise tools: a, b, c and 2 more")
        self.assertIn("[workflow run](https://example.com/run)", body)


if __name__ == "__main__":
    unittest.main()
