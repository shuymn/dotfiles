package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func runDepGraphGenCmd(args ...string) (int, map[string]any) {
	var buf bytes.Buffer
	rc := runDepGraphGen(&buf, args)
	var result map[string]any
	if line := strings.TrimSpace(buf.String()); line != "" {
		if err := json.Unmarshal([]byte(line), &result); err != nil {
			return rc, map[string]any{"_raw": line, "_err": err.Error()}
		}
	}
	return rc, result
}

// --- Unit tests: parseTasksWithDeps ---

func TestDGParseTasksWithDeps_AllRoots(t *testing.T) {
	plan := "# Plan\n### Task 1: A\n- **Dependencies**: none\n### Task 2: B\n- **Dependencies**: None\n"
	tasks := parseTasksWithDeps(plan)
	if len(tasks) != 2 {
		t.Fatalf("expected 2 tasks, got %d", len(tasks))
	}
	if tasks[0].id != 1 || len(tasks[0].deps) != 0 {
		t.Errorf("task[0]: expected {1, []}, got {%d, %v}", tasks[0].id, tasks[0].deps)
	}
	if tasks[1].id != 2 || len(tasks[1].deps) != 0 {
		t.Errorf("task[1]: expected {2, []}, got {%d, %v}", tasks[1].id, tasks[1].deps)
	}
}

func TestDGParseTasksWithDeps_LinearChain(t *testing.T) {
	plan := "### Task 1: A\n- **Dependencies**: none\n### Task 2: B\n- **Dependencies**: T1\n### Task 3: C\n- **Dependencies**: T2\n"
	tasks := parseTasksWithDeps(plan)
	if len(tasks) != 3 {
		t.Fatalf("expected 3 tasks, got %d", len(tasks))
	}
	if len(tasks[1].deps) != 1 || tasks[1].deps[0] != "T1" {
		t.Errorf("task[1].deps: expected [T1], got %v", tasks[1].deps)
	}
	if len(tasks[2].deps) != 1 || tasks[2].deps[0] != "T2" {
		t.Errorf("task[2].deps: expected [T2], got %v", tasks[2].deps)
	}
}

func TestDGParseTasksWithDeps_Diamond(t *testing.T) {
	plan := "### Task 1: Root\n- **Dependencies**: none\n" +
		"### Task 2: Left\n- **Dependencies**: T1\n" +
		"### Task 3: Right\n- **Dependencies**: T1\n" +
		"### Task 4: Join\n- **Dependencies**: T2, T3\n"
	tasks := parseTasksWithDeps(plan)
	if len(tasks) != 4 {
		t.Fatalf("expected 4 tasks, got %d", len(tasks))
	}
	if len(tasks[3].deps) != 2 {
		t.Errorf("task[3].deps: expected 2 deps, got %v", tasks[3].deps)
	}
}

func TestDGParseTasksWithDeps_NoneTokens(t *testing.T) {
	plan := "### Task 1: A\n- **Dependencies**: -\n### Task 2: B\n- **Dependencies**: n/a\n"
	tasks := parseTasksWithDeps(plan)
	if len(tasks) != 2 {
		t.Fatalf("expected 2 tasks, got %d", len(tasks))
	}
	if len(tasks[0].deps) != 0 {
		t.Errorf("task[0]: expected no deps, got %v", tasks[0].deps)
	}
	if len(tasks[1].deps) != 0 {
		t.Errorf("task[1]: expected no deps, got %v", tasks[1].deps)
	}
}

// --- Unit tests: generateDepGraph ---

func TestDGGenerateDepGraph_AllRoots(t *testing.T) {
	graph := generateDepGraph([]task{{1, nil}, {2, nil}})
	if !strings.Contains(graph, "Roots (no dependencies): T1, T2") {
		t.Errorf("expected roots T1, T2 in graph, got:\n%s", graph)
	}
}

func TestDGGenerateDepGraph_LinearChain(t *testing.T) {
	graph := generateDepGraph([]task{{1, nil}, {2, []string{"T1"}}, {3, []string{"T2"}}})
	if !strings.Contains(graph, "Roots (no dependencies): T1") {
		t.Errorf("expected root T1 in graph, got:\n%s", graph)
	}
	if !strings.Contains(graph, "- T2: T1") {
		t.Errorf("expected '- T2: T1' in graph, got:\n%s", graph)
	}
	if !strings.Contains(graph, "- T3: T2") {
		t.Errorf("expected '- T3: T2' in graph, got:\n%s", graph)
	}
}

func TestDGGenerateDepGraph_Diamond(t *testing.T) {
	graph := generateDepGraph([]task{
		{1, nil},
		{2, []string{"T1"}},
		{3, []string{"T1"}},
		{4, []string{"T2", "T3"}},
	})
	if !strings.Contains(graph, "Roots (no dependencies): T1") {
		t.Errorf("expected root T1, got:\n%s", graph)
	}
	if !strings.Contains(graph, "- T4: T2, T3") {
		t.Errorf("expected '- T4: T2, T3', got:\n%s", graph)
	}
}

// --- Unit tests: patchPlan ---

func TestDGPatchPlan_InsertBeforeFirstTask(t *testing.T) {
	plan := "# Plan\n\n### Task 1: A\n- **Dependencies**: none\n"
	graph := "## Task Dependency Graph\n\nRoots (no dependencies): T1"
	result := patchPlan(plan, graph)

	if !strings.Contains(result, "## Task Dependency Graph") {
		t.Error("expected graph section in result")
	}
	taskPos := strings.Index(result, "### Task 1")
	graphPos := strings.Index(result, "## Task Dependency Graph")
	if graphPos >= taskPos {
		t.Errorf("expected graph before task, graph=%d task=%d", graphPos, taskPos)
	}
}

func TestDGPatchPlan_ReplaceExistingSection(t *testing.T) {
	plan := "# Plan\n\n## Task Dependency Graph\n\nRoots (no dependencies): T1\n\n- T2: T1\n\n### Task 1: A\n- **Dependencies**: none\n"
	newGraph := "## Task Dependency Graph\n\nRoots (no dependencies): T1, T2"
	result := patchPlan(plan, newGraph)

	if !strings.Contains(result, "Roots (no dependencies): T1, T2") {
		t.Errorf("expected updated roots, got:\n%s", result)
	}
	if strings.Count(result, "## Task Dependency Graph") != 1 {
		t.Errorf("expected exactly one graph section, got:\n%s", result)
	}
	if strings.Contains(result, "- T2: T1") {
		t.Errorf("expected old dep line removed, got:\n%s", result)
	}
}

func TestDGPatchPlan_AppendWhenNoTasks(t *testing.T) {
	plan := "# Plan\n\nSome content."
	graph := "## Task Dependency Graph\n\nRoots (no dependencies): (none)"
	result := patchPlan(plan, graph)
	if !strings.Contains(result, "## Task Dependency Graph") {
		t.Errorf("expected graph appended, got:\n%s", result)
	}
}

// --- Integration tests: runDepGraphGen ---

func TestDepGraphGen_SuccessUpdatesFile(t *testing.T) {
	p := writeTempPlan(t, "# Plan\n\n### Task 1: A\n- **Dependencies**: none\n### Task 2: B\n- **Dependencies**: T1\n")
	rc, out := runDepGraphGenCmd(p)
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "GRAPH_GENERATED" {
		t.Errorf("expected code=GRAPH_GENERATED, got %v", out["code"])
	}
	taskCount, _ := out["signal.task_count"].(float64)
	if taskCount != 2 {
		t.Errorf("expected signal.task_count=2, got %v", out["signal.task_count"])
	}
	rootCount, _ := out["signal.root_count"].(float64)
	if rootCount != 1 {
		t.Errorf("expected signal.root_count=1, got %v", out["signal.root_count"])
	}

	content, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	result := string(content)
	if !strings.Contains(result, "## Task Dependency Graph") {
		t.Error("expected graph section written to file")
	}
	if !strings.Contains(result, "- T2: T1") {
		t.Error("expected '- T2: T1' in updated file")
	}
}

func TestDepGraphGen_FileNotFound(t *testing.T) {
	rc, out := runDepGraphGenCmd("/nonexistent/plan.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Errorf("expected code=PLAN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestDepGraphGen_NoTasks(t *testing.T) {
	p := writeTempPlan(t, "# Empty plan\n")
	rc, out := runDepGraphGenCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "NO_TASKS_FOUND" {
		t.Errorf("expected code=NO_TASKS_FOUND, got %v", out["code"])
	}
}

func TestDepGraphGen_InvalidArgCount(t *testing.T) {
	rc, out := runDepGraphGenCmd()
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "INVALID_ARGUMENT_COUNT" {
		t.Errorf("expected code=INVALID_ARGUMENT_COUNT, got %v", out["code"])
	}
}

func TestDepGraphGen_Help(t *testing.T) {
	rc, _ := runDepGraphGenCmd("--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}
