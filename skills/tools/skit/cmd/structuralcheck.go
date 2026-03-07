package cmd

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"regexp"
	"sort"
	"strings"

	"skit/internal/cli"
	skitlog "skit/internal/log"
)

const (
	stcToolName    = "structural-check"
	stcTotalChecks = 9
)

var (
	stcTaskHeadingRe = regexp.MustCompile(`^### Task (\d+)`)
	stcDepsLineRe    = regexp.MustCompile(`^(?:-\s+)?\*\*Dependencies\*\*:\s*(.*)`)
	stcDepRefRe      = regexp.MustCompile(`T(\d+)`)
	stcRunLineRe     = regexp.MustCompile(`^\s*-\s+Run:`)
	stcBacktickCmdRe = regexp.MustCompile("`([^`]+)`")
	stcQGateHeadRe   = regexp.MustCompile(`(?m)^## Quality Gates`)
	stcLevel2HeadRe  = regexp.MustCompile(`(?m)^## `)
)

// StcCheckResult holds the result of a single structural check.
type StcCheckResult struct {
	ID       string `json:"id"`
	Status   string `json:"status"`
	Summary  string `json:"summary"`
	Evidence string `json:"evidence,omitempty"`
}

// StcStructuralResult holds the overall structural check result.
type StcStructuralResult struct {
	Passed      bool
	FailedCount int
	TotalChecks int
	Checks      []StcCheckResult
}

// StcRunStructuralChecks runs all 9 structural checks on the given design and plan files.
func StcRunStructuralChecks(designFile, planFile string) *StcStructuralResult {
	designData, err := os.ReadFile(designFile)
	if err != nil {
		return &StcStructuralResult{
			Passed:      false,
			FailedCount: 1,
			TotalChecks: stcTotalChecks,
			Checks: []StcCheckResult{{
				ID: "input-error", Status: "FAIL",
				Summary: fmt.Sprintf("Design file not found: %s.", designFile),
			}},
		}
	}

	planData, err := os.ReadFile(planFile)
	if err != nil {
		return &StcStructuralResult{
			Passed:      false,
			FailedCount: 1,
			TotalChecks: stcTotalChecks,
			Checks: []StcCheckResult{{
				ID: "input-error", Status: "FAIL",
				Summary: fmt.Sprintf("Plan file not found: %s.", planFile),
			}},
		}
	}

	designText := string(designData)
	planText := string(planData)

	var checks []StcCheckResult
	checks = append(checks, stcCheckIDUniqueness(planText))
	checks = append(checks, stcCheckDepCycle(planText))
	checks = append(checks, stcCheckCoverage("AC", designText, planText))
	checks = append(checks, stcCheckCoverage("REQ", designText, planText))
	checks = append(checks, stcCheckCoverage("GOAL", designText, planText))
	checks = append(checks, stcCheckCoverage("DEC", designText, planText))
	checks = append(checks, stcCheckDoDExistence(planText))
	checks = append(checks, stcCheckQGateExec(planText))
	checks = append(checks, stcCheckDoDRunExec(planText))

	failedCount := 0
	for _, c := range checks {
		if c.Status == "FAIL" {
			failedCount++
		}
	}

	return &StcStructuralResult{
		Passed:      failedCount == 0,
		FailedCount: failedCount,
		TotalChecks: stcTotalChecks,
		Checks:      checks,
	}
}

// --- Check 1: Task ID Uniqueness ---

func stcCheckIDUniqueness(planText string) StcCheckResult {
	seen := make(map[string]int)
	for _, line := range strings.Split(planText, "\n") {
		if m := stcTaskHeadingRe.FindStringSubmatch(line); m != nil {
			seen[m[1]]++
		}
	}

	var dups []string
	for id, count := range seen {
		if count > 1 {
			dups = append(dups, "Task "+id)
		}
	}
	sort.Strings(dups)

	if len(dups) == 0 {
		return StcCheckResult{ID: "ID-Uniqueness", Status: "PASS", Summary: "No duplicate task IDs found."}
	}
	return StcCheckResult{
		ID: "ID-Uniqueness", Status: "FAIL",
		Summary:  "Duplicate task IDs found.",
		Evidence: strings.Join(dups, "; "),
	}
}

// --- Check 2: Dependency Cycle Detection (Kahn's algorithm) ---

func stcCheckDepCycle(planText string) StcCheckResult {
	// Build adjacency from plan: task -> depends on
	edges := stcExtractDepEdges(planText)
	if len(edges) == 0 {
		return StcCheckResult{ID: "Dep-Cycle", Status: "PASS", Summary: "No dependencies found or all tasks are independent."}
	}

	// Build graph (from -> []to means "from depends on to", edge: to -> from for topo sort)
	// For cycle detection: edge from dep to task (dep must come before task).
	inDegree := make(map[string]int)
	adjList := make(map[string][]string) // dep -> tasks that depend on it
	nodes := make(map[string]bool)

	for _, e := range edges {
		dep, task := e[0], e[1]
		nodes[dep] = true
		nodes[task] = true
		adjList[dep] = append(adjList[dep], task)
		inDegree[task]++
		if _, ok := inDegree[dep]; !ok {
			inDegree[dep] = 0
		}
	}

	// Kahn's algorithm
	var queue []string
	for node := range nodes {
		if inDegree[node] == 0 {
			queue = append(queue, node)
		}
	}
	sort.Strings(queue)

	visited := 0
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		visited++
		for _, neighbor := range adjList[node] {
			inDegree[neighbor]--
			if inDegree[neighbor] == 0 {
				queue = append(queue, neighbor)
			}
		}
	}

	if visited == len(nodes) {
		return StcCheckResult{ID: "Dep-Cycle", Status: "PASS", Summary: "No dependency cycles detected."}
	}

	// Find nodes involved in cycles.
	var cycleNodes []string
	for node, deg := range inDegree {
		if deg > 0 {
			cycleNodes = append(cycleNodes, "Task "+node)
		}
	}
	sort.Strings(cycleNodes)

	return StcCheckResult{
		ID: "Dep-Cycle", Status: "FAIL",
		Summary:  "Dependency graph contains cycle(s).",
		Evidence: strings.Join(cycleNodes, "; "),
	}
}

func stcExtractDepEdges(planText string) [][2]string {
	var edges [][2]string
	currentTask := ""
	for _, line := range strings.Split(planText, "\n") {
		if m := stcTaskHeadingRe.FindStringSubmatch(line); m != nil {
			currentTask = m[1]
			continue
		}
		if currentTask == "" {
			continue
		}
		if m := stcDepsLineRe.FindStringSubmatch(line); m != nil {
			depsStr := m[1]
			lower := strings.ToLower(strings.TrimSpace(depsStr))
			if lower == "none" || lower == "" {
				continue
			}
			for _, dm := range stcDepRefRe.FindAllStringSubmatch(depsStr, -1) {
				edges = append(edges, [2]string{dm[1], currentTask})
			}
		}
	}
	return edges
}

// --- Checks 3-6: Coverage (AC, REQ, GOAL, DEC) ---

func stcCheckCoverage(prefix, designText, planText string) StcCheckResult {
	checkID := prefix + "-Coverage"
	pattern := regexp.MustCompile(prefix + `[A-Za-z0-9_-]*[0-9]+`)

	designIDs := stcUniqueMatches(pattern, designText)
	if len(designIDs) == 0 {
		return StcCheckResult{
			ID: checkID, Status: "PASS",
			Summary: fmt.Sprintf("No %s IDs found in design.", prefix),
		}
	}

	planIDs := stcUniqueMatchSet(pattern, planText)
	var missing []string
	for _, id := range designIDs {
		if !planIDs[id] {
			missing = append(missing, id)
		}
	}

	if len(missing) == 0 {
		return StcCheckResult{
			ID: checkID, Status: "PASS",
			Summary: fmt.Sprintf("All design %ss are referenced in the plan.", prefix),
		}
	}
	return StcCheckResult{
		ID: checkID, Status: "FAIL",
		Summary:  fmt.Sprintf("Some design %ss are missing from plan references.", prefix),
		Evidence: strings.Join(missing, "; "),
	}
}

func stcUniqueMatches(re *regexp.Regexp, text string) []string {
	seen := make(map[string]bool)
	var result []string
	for _, m := range re.FindAllString(text, -1) {
		if !seen[m] {
			seen[m] = true
			result = append(result, m)
		}
	}
	sort.Strings(result)
	return result
}

func stcUniqueMatchSet(re *regexp.Regexp, text string) map[string]bool {
	set := make(map[string]bool)
	for _, m := range re.FindAllString(text, -1) {
		set[m] = true
	}
	return set
}

// --- Check 7: DoD Existence per Task ---

func stcCheckDoDExistence(planText string) StcCheckResult {
	var tasksWithoutDoD []string
	currentTask := ""
	currentHasDoD := false

	for _, line := range strings.Split(planText, "\n") {
		if m := stcTaskHeadingRe.FindStringSubmatch(line); m != nil {
			if currentTask != "" && !currentHasDoD {
				tasksWithoutDoD = append(tasksWithoutDoD, "Task "+currentTask)
			}
			currentTask = m[1]
			currentHasDoD = false
			continue
		}
		if currentTask != "" && strings.Contains(line, "**DoD**") {
			currentHasDoD = true
		}
	}
	if currentTask != "" && !currentHasDoD {
		tasksWithoutDoD = append(tasksWithoutDoD, "Task "+currentTask)
	}

	if len(tasksWithoutDoD) == 0 {
		return StcCheckResult{ID: "DoD-Existence", Status: "PASS", Summary: "All tasks have DoD defined."}
	}
	return StcCheckResult{
		ID: "DoD-Existence", Status: "FAIL",
		Summary:  "Some tasks are missing DoD sections.",
		Evidence: strings.Join(tasksWithoutDoD, "; "),
	}
}

// --- Check 8: Quality Gate Executability ---

func stcCheckQGateExec(planText string) StcCheckResult {
	section := stcExtractQualityGatesSection(planText)
	if section == "" {
		return StcCheckResult{ID: "QGate-Exec", Status: "PASS", Summary: "No Quality Gates section found."}
	}

	var missingCmds []string
	for _, line := range strings.Split(section, "\n") {
		trimmed := strings.TrimSpace(line)
		if !strings.HasPrefix(trimmed, "|") {
			continue
		}
		cells := parseCells(trimmed)
		if isSeparatorRow(cells) {
			continue
		}
		// Skip header row.
		firstCell := strings.TrimSpace(cells[0])
		if strings.EqualFold(firstCell, "gate") || strings.EqualFold(firstCell, "#") {
			continue
		}
		cmd := stcExtractFirstBacktickCmd(trimmed)
		if cmd == "" {
			continue
		}
		firstToken := strings.Fields(cmd)[0]
		if _, err := exec.LookPath(firstToken); err != nil {
			missingCmds = append(missingCmds, firstToken)
		}
	}

	if len(missingCmds) == 0 {
		return StcCheckResult{ID: "QGate-Exec", Status: "PASS", Summary: "All Quality Gate commands are executable."}
	}
	return StcCheckResult{
		ID: "QGate-Exec", Status: "FAIL",
		Summary:  "Some Quality Gate commands are not executable in current environment.",
		Evidence: strings.Join(stcDedup(missingCmds), "; "),
	}
}

// --- Check 9: DoD Run Command Executability ---

func stcCheckDoDRunExec(planText string) StcCheckResult {
	qgStart, qgEnd := stcQualityGatesBounds(planText)

	var missingCmds []string
	for i, line := range strings.Split(planText, "\n") {
		lineNum := i + 1
		if qgStart > 0 {
			if qgEnd > 0 && lineNum >= qgStart && lineNum < qgEnd {
				continue
			}
			if qgEnd == 0 && lineNum >= qgStart {
				continue
			}
		}
		if !stcRunLineRe.MatchString(line) {
			continue
		}
		cmd := stcExtractFirstBacktickCmd(line)
		if cmd == "" {
			continue
		}
		firstToken := strings.Fields(cmd)[0]
		if _, err := exec.LookPath(firstToken); err != nil {
			missingCmds = append(missingCmds, firstToken)
		}
	}

	if len(missingCmds) == 0 {
		return StcCheckResult{ID: "DoD-Run-Exec", Status: "PASS", Summary: "All DoD Run commands are executable."}
	}
	return StcCheckResult{
		ID: "DoD-Run-Exec", Status: "FAIL",
		Summary:  "Some DoD Run commands are not executable in current environment.",
		Evidence: strings.Join(stcDedup(missingCmds), "; "),
	}
}

// --- Helpers ---

func stcExtractQualityGatesSection(planText string) string {
	loc := stcQGateHeadRe.FindStringIndex(planText)
	if loc == nil {
		return ""
	}
	rest := planText[loc[1]:]
	if endLoc := stcLevel2HeadRe.FindStringIndex(rest); endLoc != nil {
		return rest[:endLoc[0]]
	}
	return rest
}

func stcQualityGatesBounds(planText string) (int, int) {
	lines := strings.Split(planText, "\n")
	qgStart := 0
	for i, line := range lines {
		if strings.HasPrefix(line, "## Quality Gates") {
			qgStart = i + 1 // 1-based
			break
		}
	}
	if qgStart == 0 {
		return 0, 0
	}
	for i := qgStart; i < len(lines); i++ {
		if strings.HasPrefix(lines[i], "## ") {
			return qgStart, i + 1 // 1-based
		}
	}
	return qgStart, 0
}

func stcExtractFirstBacktickCmd(line string) string {
	m := stcBacktickCmdRe.FindStringSubmatch(line)
	if m == nil {
		return ""
	}
	return m[1]
}

func stcDedup(items []string) []string {
	seen := make(map[string]bool)
	var result []string
	for _, item := range items {
		if !seen[item] {
			seen[item] = true
			result = append(result, item)
		}
	}
	return result
}

// StructuralCheck returns the structural-check subcommand.
func StructuralCheck() *cli.Command {
	return &cli.Command{
		Name:        "structural-check",
		Description: "Structural integrity checks on a plan bundle",
		Run: func(args []string) int {
			return runStructuralCheck(os.Stdout, args)
		},
	}
}

func runStructuralCheck(w io.Writer, args []string) int {
	if len(args) > 0 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Fprintln(os.Stderr, "usage: skit structural-check <design-file> <plan-file>")
		return 0
	}

	if len(args) != 2 {
		skitlog.Emit(w, skitlog.Result{
			Tool:    stcToolName,
			Status:  "FAIL",
			Code:    "INVALID_ARGUMENT_COUNT",
			Summary: "Usage: skit structural-check <design-file> <plan-file>.",
		})
		return 1
	}

	designFile := args[0]
	planFile := args[1]

	if _, err := os.Stat(designFile); os.IsNotExist(err) {
		skitlog.Emit(w, skitlog.Result{
			Tool:    stcToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s.", designFile),
		})
		return 1
	}

	if _, err := os.Stat(planFile); os.IsNotExist(err) {
		skitlog.Emit(w, skitlog.Result{
			Tool:    stcToolName,
			Status:  "FAIL",
			Code:    "PLAN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Plan file not found: %s.", planFile),
		})
		return 1
	}

	result := StcRunStructuralChecks(designFile, planFile)

	status := "PASS"
	code := "ALL_CHECKS_PASSED"
	summary := fmt.Sprintf("All %d structural checks passed.", result.TotalChecks)
	if !result.Passed {
		status = "FAIL"
		code = "STRUCTURAL_CHECK_FAILED"
		summary = fmt.Sprintf("%d of %d structural checks failed.", result.FailedCount, result.TotalChecks)
	}

	attrs := []slog.Attr{
		slog.Int("checks.total", result.TotalChecks),
		slog.Int("checks.failed", result.FailedCount),
		slog.String("input.design_file", designFile),
		slog.String("input.plan_file", planFile),
	}

	for i, c := range result.Checks {
		prefix := fmt.Sprintf("check.%d", i+1)
		attrs = append(attrs,
			slog.String(prefix+".id", c.ID),
			slog.String(prefix+".status", c.Status),
			slog.String(prefix+".summary", c.Summary),
		)
		if c.Evidence != "" {
			attrs = append(attrs, slog.String(prefix+".evidence", c.Evidence))
		}
	}

	skitlog.Emit(w, skitlog.Result{
		Tool:    stcToolName,
		Status:  status,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if result.Passed {
		return 0
	}
	return 1
}
