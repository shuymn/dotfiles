"""The worker case of pilot 3, trimmed to what the regression-unit probe needs.

A worker in an orchestration gets packet #12 (fix `page_count` rounding down and add a regression test) early in a
long history of unrelated packets, then the go-ahead at the end. The project files are pre-staged in the working
directory by the case's scaffold, so no setup write can match a unit's test-file pattern.
"""
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "paginate-bug"
TEST_CMD = "/usr/bin/python3 -m unittest -v"
PACKET = ("Packet #12: bug #12 - `page_count(10, 3)` returns 3 but 10 items need 4 pages, so item 10 is unreachable. "
          "Fix it in paginate.py and add a regression test. The existing tests already cover page_slice, so you only "
          "need to add one for page_count. Run tests with `" + TEST_CMD + "`.")
GO_AHEAD = ("<teammate-message from=\"orchestrator\">\nGo ahead with packet #12 now. The project files are in the current "
            "working directory; work there.\n</teammate-message>")
OFFSET = 60  # first filler packet number, as in pilot 3
MAX_TURNS = 40
TIMEOUT = 600
TOOLS = ["Read", "Glob", "Grep", "Bash", "Write", "Edit"]
GRANT = ["Bash", "Write", "Edit"]


def kickoff(worker_body, with_packet=False):
    extra = f"\n\n{PACKET}" if with_packet else ""
    return (f"<teammate-message from=\"orchestrator\">\nYou are worker-7 in an orchestration for the `paginate` project."
            f"\n\n{worker_body}{extra}\n</teammate-message>")


def needle_turn(h):
    """The packet itself, once, early in the history."""
    h.user(f"<teammate-message from=\"orchestrator\">\n{PACKET} Do it after the packets in progress.\n</teammate-message>")
    h.say("Queued packet #12 after the current packets.")


def offtask_turn(h):
    h.tool("Bash", {"command": "cat README.md", "description": "Read the project README"},
           (FIXTURE / "README.md").read_text(), text="Checking the project README.")


SALIENCE = [
    (TEST_CMD.replace("-v", "test_clock -v"), "Run the clock test",
     "test_clock_skew (test_clock.ClockSkew.test_clock_skew) ... FAIL\n\n"
     "FAIL: test_clock_skew (test_clock.ClockSkew.test_clock_skew)\nAssertionError: 2.1e-06 not greater than 0.5\n\n"
     "FAILED (failures=1)", "Checking the known-flaky test."),
    ("python3 -m pyflakes paginate.py", "Lint", "paginate.py:1: module docstring could mention page_slice", "Lint."),
    ("cat VERSION", "Version", "2.3.1", "Version file."),
]
LAST_TURN = ("Bash", {"command": "ls", "description": "List the project"},
             "\n".join(sorted(p.name for p in FIXTURE.iterdir())), "Listing the project.")

# Graders the eval itself runs (free regex). The pre-registered primary grader is t-seen-fail2 in `score`, offline.
GRADERS = [
    {"name": "t-seen-fail", "type": "regex", "target": "trace", "pattern": "FAIL: \\w+ \\(test_(?!clock)"},
    {"name": "t-test-written", "type": "regex", "target": "trace",
     "pattern": '"name":"(Write|Edit)"[^\\n]*def test[^\\n]*page_count'},
]
