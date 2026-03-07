package cmd

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const depGraphGenToolName = "dep-graph-gen"

var (
	dgTaskHeaderRe = regexp.MustCompile(`^### Task (\d+)`)
	dgDepFieldRe   = regexp.MustCompile(`^-?\s*\*\*Dependencies\*\*:\s*(.*)`)
	dgTaskRefRe    = regexp.MustCompile(`T(\d+)`)
	dgSpaceRe      = regexp.MustCompile(`\s+`)
	dgFirstTaskRe  = regexp.MustCompile(`(?m)^### Task \d+`)
)

var dgNoneTokens = map[string]bool{
	"":     true,
	"-":    true,
	"none": true,
	"n/a":  true,
	"na":   true,
}

type task struct {
	id   int
	deps []string
}

// DepGraphGen returns the dep-graph-gen subcommand.
func DepGraphGen() *cli.Command {
	c := cli.NewCommand("dep-graph-gen", "Generate Task Dependency Graph section in plan.md")
	c.EnableDryRun()
	var planFile string
	c.StringArg(&planFile, "plan-file", "Plan file to rewrite")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runDepGraphGen(s.Stdout, planFile, s.DryRun))
	}
	return c
}

func runDepGraphGen(w io.Writer, planPath string, dryRun bool) int {
	data, err := os.ReadFile(planPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    depGraphGenToolName,
			Status:  "FAIL",
			Code:    "PLAN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Plan file not found: %s", planPath),
		}, slog.Any("fix", []string{"FIX_PLAN_FILE_PATH"}))
		return 1
	}

	text := string(data)
	tasks := parseTasksWithDeps(text)

	if len(tasks) == 0 {
		log.Emit(w, log.Result{
			Tool:    depGraphGenToolName,
			Status:  "FAIL",
			Code:    "NO_TASKS_FOUND",
			Summary: "No ### Task N headers found in plan file.",
		}, slog.Any("fix", []string{"FIX_ADD_TASK_HEADERS"}))
		return 1
	}

	graph := generateDepGraph(tasks)
	patched := patchPlan(text, graph)

	if !dryRun {
		if err := os.WriteFile(planPath, []byte(patched), 0644); err != nil {
			log.Emit(w, log.Result{
				Tool:    depGraphGenToolName,
				Status:  "FAIL",
				Code:    "PLAN_WRITE_FAILED",
				Summary: fmt.Sprintf("Failed to write plan file: %s", planPath),
			})
			return 1
		}
	}

	rootCount := 0
	depEdgeCount := 0
	for _, t := range tasks {
		if len(t.deps) == 0 {
			rootCount++
		}
		depEdgeCount += len(t.deps)
	}

	log.Emit(w, log.Result{
		Tool:    depGraphGenToolName,
		Status:  "PASS",
		Code:    "GRAPH_GENERATED",
		Summary: fmt.Sprintf("Generated dependency graph for %d tasks.", len(tasks)),
	},
		slog.Int("signal.task_count", len(tasks)),
		slog.Int("signal.root_count", rootCount),
		slog.Int("signal.dep_edge_count", depEdgeCount),
		slog.Bool("signal.dry_run", dryRun),
	)
	return 0
}

func parseTasksWithDeps(text string) []task {
	var tasks []task
	currentTask := -1

	for _, line := range strings.Split(text, "\n") {
		if m := dgTaskHeaderRe.FindStringSubmatch(line); m != nil {
			id, _ := strconv.Atoi(m[1])
			currentTask = id
			continue
		}
		if currentTask >= 0 {
			if m := dgDepFieldRe.FindStringSubmatch(line); m != nil {
				raw := strings.TrimSpace(m[1])
				deps := parseDepValue(raw)
				tasks = append(tasks, task{id: currentTask, deps: deps})
				currentTask = -1
			}
		}
	}

	if currentTask >= 0 {
		tasks = append(tasks, task{id: currentTask, deps: nil})
	}

	return tasks
}

func parseDepValue(value string) []string {
	normalized := dgSpaceRe.ReplaceAllString(strings.TrimSpace(strings.ToLower(value)), " ")
	if dgNoneTokens[normalized] {
		return nil
	}
	matches := dgTaskRefRe.FindAllStringSubmatch(value, -1)
	refs := make([]string, 0, len(matches))
	for _, m := range matches {
		refs = append(refs, "T"+m[1])
	}
	return refs
}

func generateDepGraph(tasks []task) string {
	var roots []int
	var hasDeps []task

	for _, t := range tasks {
		if len(t.deps) == 0 {
			roots = append(roots, t.id)
		} else {
			hasDeps = append(hasDeps, t)
		}
	}

	var lines []string
	lines = append(lines, "## Task Dependency Graph", "")

	if len(roots) > 0 {
		sort.Ints(roots)
		rootLabels := make([]string, len(roots))
		for i, r := range roots {
			rootLabels[i] = fmt.Sprintf("T%d", r)
		}
		lines = append(lines, "Roots (no dependencies): "+strings.Join(rootLabels, ", "))
	} else {
		lines = append(lines, "Roots (no dependencies): (none)")
	}

	if len(hasDeps) > 0 {
		sort.Slice(hasDeps, func(i, j int) bool { return hasDeps[i].id < hasDeps[j].id })
		lines = append(lines, "")
		for i := range hasDeps {
			sort.Slice(hasDeps[i].deps, func(a, b int) bool {
				na, _ := strconv.Atoi(hasDeps[i].deps[a][1:])
				nb, _ := strconv.Atoi(hasDeps[i].deps[b][1:])
				return na < nb
			})
			lines = append(lines, fmt.Sprintf("- T%d: %s", hasDeps[i].id, strings.Join(hasDeps[i].deps, ", ")))
		}
	}

	return strings.Join(lines, "\n")
}

// findGraphSection finds the byte range [start, end) of the existing
// ## Task Dependency Graph section. end points to the start of the next
// ## section header (if any), or len(text).
func findGraphSection(text string) (start, end int, found bool) {
	const header = "## Task Dependency Graph"

	hStart := -1
	if strings.HasPrefix(text, header+"\n") || text == header {
		hStart = 0
	} else {
		needle := "\n" + header
		idx := strings.Index(text, needle)
		if idx >= 0 {
			hStart = idx + 1
		}
	}

	if hStart < 0 {
		return 0, 0, false
	}

	rest := text[hStart:]
	firstNL := strings.Index(rest, "\n")
	if firstNL < 0 {
		return hStart, len(text), true
	}

	afterHeader := firstNL + 1
	nextSectionOffset := strings.Index(rest[afterHeader:], "\n## ")
	if nextSectionOffset < 0 {
		return hStart, len(text), true
	}

	// +1 to skip past the \n, landing on the ## of the next section
	return hStart, hStart + afterHeader + nextSectionOffset + 1, true
}

func patchPlan(text, graphSection string) string {
	// Replace existing section.
	if start, end, found := findGraphSection(text); found {
		after := strings.TrimLeft(text[end:], "\n")
		return text[:start] + graphSection + "\n\n" + after
	}

	// Insert before first ### Task N.
	loc := dgFirstTaskRe.FindStringIndex(text)
	if loc != nil {
		before := strings.TrimRight(text[:loc[0]], "\n")
		return before + "\n\n" + graphSection + "\n\n" + text[loc[0]:]
	}

	// Append to end.
	return strings.TrimRight(text, "\n") + "\n\n" + graphSection + "\n"
}
