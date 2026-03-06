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

MODULE_PATH = ARTIFACT_ROOT / "decompose-plan" / "scripts" / "dep_graph_gen.py"
SPEC = importlib.util.spec_from_file_location("dep_graph_gen", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ParseTasksWithDepsTests(unittest.TestCase):
    def test_no_dependencies_all_roots(self) -> None:
        plan = textwrap.dedent("""\
            # Plan
            ### Task 1: A
            - **Dependencies**: none
            ### Task 2: B
            - **Dependencies**: None
        """)
        tasks = MODULE.parse_tasks_with_deps(plan)
        self.assertEqual(tasks, [(1, ()), (2, ())])

    def test_linear_chain(self) -> None:
        plan = textwrap.dedent("""\
            # Plan
            ### Task 1: A
            - **Dependencies**: none
            ### Task 2: B
            - **Dependencies**: T1
            ### Task 3: C
            - **Dependencies**: T2
        """)
        tasks = MODULE.parse_tasks_with_deps(plan)
        self.assertEqual(tasks, [(1, ()), (2, ("T1",)), (3, ("T2",))])

    def test_diamond_dependencies(self) -> None:
        plan = textwrap.dedent("""\
            # Plan
            ### Task 1: Root
            - **Dependencies**: none
            ### Task 2: Left
            - **Dependencies**: T1
            ### Task 3: Right
            - **Dependencies**: T1
            ### Task 4: Join
            - **Dependencies**: T2, T3
        """)
        tasks = MODULE.parse_tasks_with_deps(plan)
        self.assertEqual(
            tasks,
            [(1, ()), (2, ("T1",)), (3, ("T1",)), (4, ("T2", "T3"))],
        )

    def test_empty_and_dash_normalized(self) -> None:
        plan = textwrap.dedent("""\
            # Plan
            ### Task 1: A
            - **Dependencies**: -
            ### Task 2: B
            - **Dependencies**: n/a
        """)
        tasks = MODULE.parse_tasks_with_deps(plan)
        self.assertEqual(tasks, [(1, ()), (2, ())])


class GenerateDepGraphTests(unittest.TestCase):
    def test_all_roots(self) -> None:
        graph = MODULE.generate_dep_graph([(1, ()), (2, ())])
        self.assertIn("Roots (no dependencies): T1, T2", graph)

    def test_linear_chain(self) -> None:
        graph = MODULE.generate_dep_graph([(1, ()), (2, ("T1",)), (3, ("T2",))])
        self.assertIn("Roots (no dependencies): T1", graph)
        self.assertIn("- T2: T1", graph)
        self.assertIn("- T3: T2", graph)

    def test_diamond(self) -> None:
        graph = MODULE.generate_dep_graph(
            [(1, ()), (2, ("T1",)), (3, ("T1",)), (4, ("T2", "T3"))]
        )
        self.assertIn("Roots (no dependencies): T1", graph)
        self.assertIn("- T4: T2, T3", graph)


class PatchPlanTests(unittest.TestCase):
    def test_insert_before_first_task(self) -> None:
        plan = textwrap.dedent("""\
            # Plan

            ### Task 1: A
            - **Dependencies**: none
        """)
        graph = "## Task Dependency Graph\n\nRoots (no dependencies): T1"
        result = MODULE.patch_plan(plan, graph)
        self.assertIn("## Task Dependency Graph", result)
        task_pos = result.index("### Task 1")
        graph_pos = result.index("## Task Dependency Graph")
        self.assertLess(graph_pos, task_pos)

    def test_replace_existing_graph_section(self) -> None:
        plan = textwrap.dedent("""\
            # Plan

            ## Task Dependency Graph

            Roots (no dependencies): T1

            - T2: T1

            ### Task 1: A
            - **Dependencies**: none
        """)
        new_graph = "## Task Dependency Graph\n\nRoots (no dependencies): T1, T2"
        result = MODULE.patch_plan(plan, new_graph)
        self.assertIn("Roots (no dependencies): T1, T2", result)
        self.assertEqual(result.count("## Task Dependency Graph"), 1)
        self.assertNotIn("- T2: T1", result)

    def test_append_when_no_tasks(self) -> None:
        plan = "# Plan\n\nSome content."
        graph = "## Task Dependency Graph\n\nRoots (no dependencies): (none)"
        result = MODULE.patch_plan(plan, graph)
        self.assertIn("## Task Dependency Graph", result)


class CLITests(unittest.TestCase):
    def test_cli_updates_plan_and_emits_structured_pass(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        plan_path = temp_dir / "plan.md"
        plan_path.write_text(
            textwrap.dedent("""\
                # Plan

                ### Task 1: A
                - **Dependencies**: none
                ### Task 2: B
                - **Dependencies**: T1
            """),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["dep_graph_gen.py", str(plan_path)])
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("status=PASS", output)
        self.assertIn("code=GRAPH_GENERATED", output)
        self.assertIn("signal.task_count=2", output)
        self.assertIn("signal.root_count=1", output)

        result = plan_path.read_text(encoding="utf-8")
        self.assertIn("## Task Dependency Graph", result)
        self.assertIn("- T2: T1", result)

    def test_cli_emits_structured_fail_for_missing_file(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["dep_graph_gen.py", "/nonexistent/plan.md"])
        self.assertEqual(rc, 1)
        output = buf.getvalue()
        self.assertIn("status=FAIL", output)
        self.assertIn("code=PLAN_FILE_NOT_FOUND", output)
        self.assertIn("fix.1=FIX_PLAN_FILE_PATH", output)

    def test_cli_emits_structured_fail_for_no_tasks(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        plan_path = temp_dir / "plan.md"
        plan_path.write_text("# Empty plan\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MODULE.main(["dep_graph_gen.py", str(plan_path)])
        self.assertEqual(rc, 1)
        output = buf.getvalue()
        self.assertIn("status=FAIL", output)
        self.assertIn("code=NO_TASKS_FOUND", output)
        self.assertIn("fix.1=FIX_ADD_TASK_HEADERS", output)


if __name__ == "__main__":
    unittest.main()
