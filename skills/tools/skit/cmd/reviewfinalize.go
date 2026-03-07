package cmd

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"skit/internal/cli"
	skitlog "skit/internal/log"
)

const rfToolName = "review-finalize"

var (
	rfSummaryFields = []string{
		"Forward Fidelity",
		"Reverse Fidelity",
		"Round-trip",
		"Behavioral Lock",
		"Negative Path",
		"Temporal",
		"Traceability",
		"Scope",
		"Testability",
		"Execution Readiness",
		"Integration Coverage",
		"Risk Classification",
	}
	rfSummaryNAFields = map[string]bool{
		"Integration Coverage": true,
		"Risk Classification":  true,
	}
	rfAllowedCards = map[int]bool{1: true, 2: true, 3: true, 5: true, 8: true}
	rfAxes         = []string{"Objective", "Surface", "Verification", "Rollback"}

	rfTaskHeadRe   = regexp.MustCompile(`(?m)^### Task (\d+):`)
	rfTitleRe      = regexp.MustCompile(`(?m)^# (.+)$`)
	rfSourceLineRe = regexp.MustCompile(`(?m)^- \*\*Source\*\*: ` + "`([^`]+)`")
)

var rfAxisRecommendations = map[string]string{
	"Objective":    "Split independently releasable outcomes so this task owns one objective.",
	"Surface":      "Separate unrelated boundaries or top-level path families into different tasks.",
	"Verification": "Reduce the task to one main verification flow and move independent checks into follow-up tasks.",
	"Rollback":     "Separate reversible preparation from irreversible cutover or removal so rollback stays clean.",
}

// --- Data types ---

type rfMachineRow struct {
	Task           string
	Total          string
	Verdict        string
	Trigger        string
	Recommendation string
}

type rfGranularityRow struct {
	Task         string
	Objective    string
	Surface      string
	Verification string
	Rollback     string
	Evidence     string
}

// --- Parse functions ---

func rfExtractSection(markdown, heading string) string {
	// Find the heading line.
	headPattern := regexp.MustCompile(`(?m)^## ` + regexp.QuoteMeta(heading) + `\s*$`)
	loc := headPattern.FindStringIndex(markdown)
	if loc == nil {
		return ""
	}
	// Content starts after the heading line.
	rest := markdown[loc[1]:]
	// Find the next ## heading.
	nextHead := regexp.MustCompile(`(?m)^## [^\n]+`)
	endLoc := nextHead.FindStringIndex(rest)
	if endLoc != nil {
		return strings.TrimSpace(rest[:endLoc[0]])
	}
	return strings.TrimSpace(rest)
}

func rfParseSummary(body string) (map[string]string, []string) {
	rawMap := make(map[string]string)
	for _, line := range strings.Split(body, "\n") {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "- ") {
			continue
		}
		payload := stripped[2:]
		idx := strings.Index(payload, ":")
		if idx < 0 {
			continue
		}
		name := strings.ReplaceAll(strings.TrimSpace(payload[:idx]), "**", "")
		value := strings.TrimSpace(payload[idx+1:])
		rawMap[name] = value
	}

	finalMap := make(map[string]string)
	var errors []string
	for _, field := range rfSummaryFields {
		raw, ok := rawMap[field]
		if !ok {
			finalMap[field] = "FAIL"
			errors = append(errors, fmt.Sprintf("Summary is missing `%s`.", field))
			continue
		}
		verdict, err := rfCanonicalizeSummaryValue(field, raw)
		finalMap[field] = verdict
		if err != "" {
			errors = append(errors, err)
		}
	}
	return finalMap, errors
}

func rfCanonicalizeSummaryValue(field, raw string) (string, string) {
	value := strings.TrimSpace(raw)
	if strings.HasPrefix(value, "PASS") {
		return "PASS", ""
	}
	if strings.HasPrefix(value, "FAIL") {
		return "FAIL", ""
	}
	if strings.HasPrefix(value, "N/A") {
		if rfSummaryNAFields[field] {
			return "N/A", ""
		}
		return "FAIL", fmt.Sprintf("`%s` cannot be `N/A`.", field)
	}
	return "FAIL", fmt.Sprintf("`%s` has an invalid verdict: `%s`.", field, value)
}

func rfParsePlanTasks(planText string) []string {
	var tasks []string
	for _, m := range rfTaskHeadRe.FindAllStringSubmatch(planText, -1) {
		tasks = append(tasks, "Task "+m[1])
	}
	return tasks
}

func rfParsePlanTitle(planText, planPath string) string {
	m := rfTitleRe.FindStringSubmatch(planText)
	if m == nil {
		return filepath.Base(filepath.Dir(planPath)) + " - Plan Review"
	}
	title := strings.TrimSpace(m[1])
	title = strings.TrimSuffix(title, " Implementation Plan")
	return title + " - Plan Review"
}

func rfParseDesignPath(planText, planPath string) string {
	m := rfSourceLineRe.FindStringSubmatch(planText)
	if m != nil {
		source := m[1]
		if filepath.IsAbs(source) {
			return source
		}
		// Try resolving relative to CWD first.
		cwd, _ := os.Getwd()
		candidate := filepath.Join(cwd, source)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
		// Fall back to resolving relative to plan directory.
		candidate = filepath.Join(filepath.Dir(planPath), source)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
		// Return CWD-relative as default.
		return filepath.Join(cwd, source)
	}
	return filepath.Join(filepath.Dir(planPath), "design.md")
}

func rfParseGranularityTable(body string) ([]rfGranularityRow, []string) {
	var rows []rfGranularityRow
	var errors []string
	foundHeader := false

	for _, line := range strings.Split(body, "\n") {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "|") {
			continue
		}
		cells := parseCells(stripped)
		trimmedCells := make([]string, len(cells))
		for i, c := range cells {
			trimmedCells[i] = strings.TrimSpace(c)
		}
		if len(trimmedCells) == 0 || allEmpty(trimmedCells) {
			continue
		}
		if trimmedCells[0] == "Task" {
			foundHeader = true
			continue
		}
		if isSeparatorRow(cells) {
			continue
		}
		if len(trimmedCells) != 6 {
			errors = append(errors, fmt.Sprintf("Malformed granularity row: `%s`.", stripped))
			continue
		}
		rows = append(rows, rfGranularityRow{
			Task:         trimmedCells[0],
			Objective:    trimmedCells[1],
			Surface:      trimmedCells[2],
			Verification: trimmedCells[3],
			Rollback:     trimmedCells[4],
			Evidence:     trimmedCells[5],
		})
	}

	if !foundHeader {
		errors = append(errors, "Granularity Poker table header is missing.")
	}

	return rows, errors
}

func allEmpty(cells []string) bool {
	for _, c := range cells {
		if c != "" {
			return false
		}
	}
	return true
}

// --- Scoring ---

func rfComputeMachineRows(taskIDs []string, granRows []rfGranularityRow, parseErrors []string) ([]rfMachineRow, []string) {
	rowsByTask := make(map[string]rfGranularityRow)
	taskIssues := make(map[string][]string)
	for _, id := range taskIDs {
		taskIssues[id] = nil
	}
	var extraRows []rfMachineRow
	globalIssues := append([]string{}, parseErrors...)

	for _, row := range granRows {
		task := row.Task
		if _, ok := taskIssues[task]; !ok {
			extraRows = append(extraRows, rfMachineRow{
				Task:           task,
				Total:          "n/a",
				Verdict:        "FAIL",
				Trigger:        "unknown task in draft",
				Recommendation: "Delete this row or rename it to an existing Task ID from plan.md.",
			})
			globalIssues = append(globalIssues, fmt.Sprintf("Granularity Poker references unknown task `%s`.", task))
			continue
		}
		if _, exists := rowsByTask[task]; exists {
			taskIssues[task] = append(taskIssues[task], "duplicate draft row")
			continue
		}
		rowsByTask[task] = row
	}

	var machineRows []rfMachineRow
	var blockers []string

	for _, taskID := range taskIDs {
		row, exists := rowsByTask[taskID]
		issues := taskIssues[taskID]

		if !exists {
			issues = append(issues, "missing draft row")
			machineRows = append(machineRows, rfMachineRow{
				Task:           taskID,
				Total:          "n/a",
				Verdict:        "FAIL",
				Trigger:        "missing draft row",
				Recommendation: rfBuildRecommendation(issues, nil, nil, false),
			})
			blockers = append(blockers, fmt.Sprintf("Add one granularity poker row for `%s`.", taskID))
			continue
		}

		rawCards := map[string]string{
			"Objective":    row.Objective,
			"Surface":      row.Surface,
			"Verification": row.Verification,
			"Rollback":     row.Rollback,
		}
		parsedCards := make(map[string]int)
		for _, axis := range rfAxes {
			v, err := strconv.Atoi(rawCards[axis])
			if err != nil {
				issues = append(issues, fmt.Sprintf("invalid %s card `%s`", strings.ToLower(axis), rawCards[axis]))
			} else if !rfAllowedCards[v] {
				issues = append(issues, fmt.Sprintf("invalid %s card `%s`", strings.ToLower(axis), rawCards[axis]))
			} else {
				parsedCards[axis] = v
			}
		}

		var cards []int
		axisScores := make(map[string]int)
		if len(parsedCards) == 4 {
			for _, axis := range rfAxes {
				axisScores[axis] = parsedCards[axis]
				cards = append(cards, parsedCards[axis])
			}
		}

		triggerParts := append([]string{}, issues...)
		var highAxes []string
		aggregateExceeded := false

		if len(cards) == 4 {
			for _, axis := range rfAxes {
				if axisScores[axis] == 8 {
					highAxes = append(highAxes, axis)
				}
			}
			total := 0
			for _, c := range cards {
				total += c
			}
			if len(highAxes) > 0 {
				axisNames := make([]string, len(highAxes))
				for i, a := range highAxes {
					axisNames[i] = strings.ToLower(a)
				}
				triggerParts = append(triggerParts, "axis ceiling exceeded ("+strings.Join(axisNames, ", ")+")")
			}
			if total > 11 {
				triggerParts = append(triggerParts, "aggregate score exceeded machine limit")
				aggregateExceeded = true
			}

			verdict := "PASS"
			if len(triggerParts) > 0 {
				verdict = "FAIL"
			}
			totalText := strconv.Itoa(total)

			if verdict == "FAIL" {
				blockers = append(blockers, fmt.Sprintf("Re-slice `%s` or fix its granularity poker row.", taskID))
			}

			trigger := "within machine limit"
			if len(triggerParts) > 0 {
				trigger = strings.Join(triggerParts, "; ")
			}
			machineRows = append(machineRows, rfMachineRow{
				Task:           taskID,
				Total:          totalText,
				Verdict:        verdict,
				Trigger:        trigger,
				Recommendation: rfBuildRecommendation(issues, axisScores, highAxes, aggregateExceeded),
			})
		} else {
			if len(triggerParts) == 0 {
				triggerParts = append(triggerParts, "invalid card values")
			}
			blockers = append(blockers, fmt.Sprintf("Re-slice `%s` or fix its granularity poker row.", taskID))
			machineRows = append(machineRows, rfMachineRow{
				Task:           taskID,
				Total:          "n/a",
				Verdict:        "FAIL",
				Trigger:        strings.Join(triggerParts, "; "),
				Recommendation: rfBuildRecommendation(issues, nil, nil, false),
			})
		}
	}

	machineRows = append(machineRows, extraRows...)
	blockers = append(blockers, globalIssues...)
	return machineRows, blockers
}

func rfBuildRecommendation(issues []string, axisScores map[string]int, highAxes []string, aggregateExceeded bool) string {
	if len(issues) == 0 && len(highAxes) == 0 && !aggregateExceeded {
		return "-"
	}

	var recommendations []string
	var invalidAxes []string
	seen := make(map[string]bool)

	for _, issue := range issues {
		if issue == "missing draft row" {
			recommendations = append(recommendations, "Add one granularity poker row for this task with all four axis cards and one evidence sentence.")
			continue
		}
		if issue == "duplicate draft row" {
			recommendations = append(recommendations, "Keep exactly one granularity poker row for this task and merge duplicate evidence into that row.")
			continue
		}
		if strings.HasPrefix(issue, "invalid ") && strings.Contains(issue, " card `") {
			axisStr := strings.TrimPrefix(issue, "invalid ")
			axisStr = axisStr[:strings.Index(axisStr, " card `")]
			invalidAxes = append(invalidAxes, rfTitleCase(axisStr))
		}
	}

	if len(invalidAxes) > 0 {
		deduped := rfDedupAxes(invalidAxes)
		axesText := strings.Join(rfLowerAll(deduped), ", ")
		recommendations = append(recommendations, fmt.Sprintf(
			"Replace invalid %s card values with allowed cards (1, 2, 3, 5, 8) and keep one evidence sentence.", axesText,
		))
	}

	for _, axis := range highAxes {
		recommendations = append(recommendations, rfAxisRecommendations[axis])
	}

	if aggregateExceeded {
		rec := rfAggregateRecommendation(axisScores, highAxes)
		recommendations = append(recommendations, rec)
	}

	var ordered []string
	for _, r := range recommendations {
		if !seen[r] {
			seen[r] = true
			ordered = append(ordered, r)
		}
	}

	if len(ordered) == 0 {
		return "-"
	}
	return strings.Join(ordered, " ")
}

func rfAggregateRecommendation(axisScores map[string]int, excludeAxes []string) string {
	excluded := make(map[string]bool)
	for _, a := range excludeAxes {
		excluded[a] = true
	}

	type axisScore struct {
		axis  string
		score int
	}
	var candidates []axisScore
	for _, axis := range rfAxes {
		if excluded[axis] {
			continue
		}
		if score, ok := axisScores[axis]; ok {
			candidates = append(candidates, axisScore{axis, score})
		}
	}

	if len(candidates) == 0 {
		return "Re-slice this task into smaller changes before re-scoring its granularity row."
	}

	sort.SliceStable(candidates, func(i, j int) bool {
		return candidates[i].score > candidates[j].score
	})

	limit := 2
	if len(candidates) < limit {
		limit = len(candidates)
	}
	var parts []string
	for _, c := range candidates[:limit] {
		parts = append(parts, rfAxisRecommendations[c.axis])
	}
	return strings.Join(parts, " ")
}

func rfDedupAxes(axes []string) []string {
	seen := make(map[string]bool)
	var result []string
	for _, axis := range rfAxes {
		for _, a := range axes {
			if strings.EqualFold(a, axis) && !seen[axis] {
				seen[axis] = true
				result = append(result, axis)
			}
		}
	}
	return result
}

func rfTitleCase(s string) string {
	if s == "" {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

func rfLowerAll(items []string) []string {
	result := make([]string, len(items))
	for i, s := range items {
		result[i] = strings.ToLower(s)
	}
	return result
}

// --- Decision ---

func rfMakeDecisionReason(structuralOK bool, summaryMap map[string]string, machineRows []rfMachineRow) (string, string) {
	var failingSummary []string
	for _, field := range rfSummaryFields {
		if summaryMap[field] == "FAIL" {
			failingSummary = append(failingSummary, field)
		}
	}
	var failingTasks []string
	for _, row := range machineRows {
		if row.Verdict == "FAIL" {
			failingTasks = append(failingTasks, row.Task)
		}
	}

	if structuralOK && len(failingSummary) == 0 && len(failingTasks) == 0 {
		return "yes", "Structural check passed, all non-granularity viewpoints passed or were N/A, and the machine granularity gate passed."
	}

	var reasons []string
	if !structuralOK {
		reasons = append(reasons, "structural check failed")
	}
	if len(failingSummary) > 0 {
		reasons = append(reasons, "summary failures: "+strings.Join(failingSummary, ", "))
	}
	if len(failingTasks) > 0 {
		reasons = append(reasons, "granularity failures: "+strings.Join(failingTasks, ", "))
	}
	return "no", strings.Join(reasons, "; ")
}

// --- Rendering ---

func rfNormalizeSection(body, fallback string) string {
	trimmed := strings.TrimSpace(body)
	if trimmed == "" {
		return fallback
	}
	return trimmed
}

func rfBuildBlockingIssuesSection(reviewerBody string, machineBlockers []string) string {
	var parts []string
	if trimmed := strings.TrimSpace(reviewerBody); trimmed != "" {
		parts = append(parts, trimmed)
	}
	if len(machineBlockers) > 0 {
		var items []string
		for _, b := range machineBlockers {
			items = append(items, "- [ ] "+b)
		}
		parts = append(parts, strings.Join(items, "\n"))
	}
	if len(parts) == 0 {
		return "- None."
	}
	return strings.Join(parts, "\n\n")
}

func rfRenderFinalReport(
	title string,
	digestStamp string,
	summaryMap map[string]string,
	structuralOK bool,
	structuralEvidence string,
	machineRows []rfMachineRow,
	findingsBody string,
	blockingBody string,
	improvementsBody string,
	proceed string,
	reason string,
) string {
	updatedAt := time.Now().Local().Format("2006-01-02 15:04 MST")

	granularityVerdict := "PASS"
	for _, row := range machineRows {
		if row.Verdict != "PASS" {
			granularityVerdict = "FAIL"
			break
		}
	}

	overallVerdict := "PASS"
	if !structuralOK {
		overallVerdict = "FAIL"
	}
	for _, field := range rfSummaryFields {
		if summaryMap[field] == "FAIL" {
			overallVerdict = "FAIL"
			break
		}
	}
	if granularityVerdict == "FAIL" {
		overallVerdict = "FAIL"
	}

	summaryLines := []string{
		fmt.Sprintf("- Forward Fidelity: %s", summaryMap["Forward Fidelity"]),
		fmt.Sprintf("- Reverse Fidelity: %s", summaryMap["Reverse Fidelity"]),
		fmt.Sprintf("- Round-trip: %s", summaryMap["Round-trip"]),
		fmt.Sprintf("- Behavioral Lock: %s", summaryMap["Behavioral Lock"]),
		fmt.Sprintf("- Negative Path: %s", summaryMap["Negative Path"]),
		fmt.Sprintf("- Granularity: %s", granularityVerdict),
		fmt.Sprintf("- Temporal: %s", summaryMap["Temporal"]),
		fmt.Sprintf("- Traceability: %s", summaryMap["Traceability"]),
		fmt.Sprintf("- Scope: %s", summaryMap["Scope"]),
		fmt.Sprintf("- Testability: %s", summaryMap["Testability"]),
		fmt.Sprintf("- Execution Readiness: %s", summaryMap["Execution Readiness"]),
		fmt.Sprintf("- Integration Coverage: %s", summaryMap["Integration Coverage"]),
		fmt.Sprintf("- Risk Classification: %s", summaryMap["Risk Classification"]),
		fmt.Sprintf("- Updated At: %s", updatedAt),
	}

	var machineTable []string
	for _, row := range machineRows {
		machineTable = append(machineTable, fmt.Sprintf(
			"| %s | %s | %s | %s | %s |",
			row.Task, row.Total, row.Verdict, row.Trigger, row.Recommendation,
		))
	}

	structuralEvidenceDisplay := structuralEvidence
	if structuralEvidenceDisplay == "" {
		structuralEvidenceDisplay = "not captured"
	}

	lines := []string{
		fmt.Sprintf("# %s", title),
		"",
		"## Review Metadata",
		"",
		digestStamp,
		fmt.Sprintf("- **Overall Verdict**: %s", overallVerdict),
		"",
		"## Summary",
		"",
	}
	lines = append(lines, summaryLines...)
	lines = append(lines,
		"",
		"## Granularity Gate (Machine)",
		"",
		fmt.Sprintf("- **Structural Check**: %s", map[bool]string{true: "PASS", false: "FAIL"}[structuralOK]),
		fmt.Sprintf("- **Structural Evidence**: %s", structuralEvidenceDisplay),
		"",
		"| Task | Total | Verdict | Trigger | Recommendation |",
		"|------|-------|---------|---------|----------------|",
	)
	lines = append(lines, machineTable...)
	lines = append(lines,
		"",
		"## Findings",
		"",
		findingsBody,
		"",
		"## Blocking Issues",
		"",
		blockingBody,
		"",
		"## Non-Blocking Improvements",
		"",
		improvementsBody,
		"",
		"## Decision",
		"",
		fmt.Sprintf("- Proceed to `execute-plan`: %s", proceed),
		fmt.Sprintf("- Reason: %s", reason),
		"",
		"Note: This review validates design and plan artifacts only.",
		"Implementation correctness is verified by dod-recheck (L4) and adversarial-verify (L5).",
		"Plan PASS does not imply implementation PASS.",
		"",
	)

	return strings.Join(lines, "\n")
}

// --- Main workflow ---

func rfExecute(w io.Writer, planPath, draftPath, finalPath string) int {
	planFile, err := filepath.Abs(planPath)
	if err != nil {
		rfEmitFail(w, "INVALID_PATH", fmt.Sprintf("Cannot resolve plan path: %s.", planPath))
		return 1
	}
	draftFile, err := filepath.Abs(draftPath)
	if err != nil {
		rfEmitFail(w, "INVALID_PATH", fmt.Sprintf("Cannot resolve draft path: %s.", draftPath))
		return 1
	}
	finalFile, err := filepath.Abs(finalPath)
	if err != nil {
		rfEmitFail(w, "INVALID_PATH", fmt.Sprintf("Cannot resolve final path: %s.", finalPath))
		return 1
	}

	if draftFile == finalFile {
		rfEmitFail(w, "SAME_FILE", "Draft review file and final review file must differ.")
		return 1
	}

	planData, err := os.ReadFile(planFile)
	if err != nil {
		rfEmitFail(w, "PLAN_FILE_NOT_FOUND", fmt.Sprintf("Plan file not found: %s.", planFile))
		return 1
	}
	draftData, err := os.ReadFile(draftFile)
	if err != nil {
		rfEmitFail(w, "DRAFT_FILE_NOT_FOUND", fmt.Sprintf("Draft review file not found: %s.", draftFile))
		return 1
	}

	planText := string(planData)
	draftText := string(draftData)

	taskIDs := rfParsePlanTasks(planText)
	if len(taskIDs) == 0 {
		rfEmitFail(w, "NO_TASKS", "Plan file does not contain any task headings.")
		return 1
	}

	summaryBody := rfExtractSection(draftText, "Summary")
	if summaryBody == "" {
		summaryBody = rfExtractSection(draftText, "Reviewer Summary")
	}
	summaryMap, summaryErrors := rfParseSummary(summaryBody)

	granularityBody := rfExtractSection(draftText, "Granularity Poker")
	granularityRows, granParseErrors := rfParseGranularityTable(granularityBody)
	machineRows, machineBlockers := rfComputeMachineRows(
		taskIDs, granularityRows, append(summaryErrors, granParseErrors...),
	)

	findingsBody := rfNormalizeSection(
		rfExtractSection(draftText, "Findings"),
		strings.Join([]string{
			"| ID | Severity | Area | File/Section | Issue | Action |",
			"|----|----------|------|--------------|-------|--------|",
			"| M1 | blocker | review-finalize | draft | Draft omitted the Findings section. | Add reviewer findings and re-run finalization. |",
		}, "\n"),
	)
	improvementsBody := rfNormalizeSection(
		rfExtractSection(draftText, "Non-Blocking Improvements"),
		"- None.",
	)

	designPath := rfParseDesignPath(planText, planFile)
	structResult := StcRunStructuralChecks(designPath, planFile)
	structuralOK := structResult.Passed
	structuralEvidence := rfStructuralEvidence(structResult)

	if !structuralOK {
		machineBlockers = append(machineBlockers, "Resolve structural-check failures before rerunning review finalization.")
	}

	blockingBody := rfBuildBlockingIssuesSection(
		rfExtractSection(draftText, "Blocking Issues"),
		machineBlockers,
	)

	proceed, reason := rfMakeDecisionReason(structuralOK, summaryMap, machineRows)

	stamp, err := DsGenerateStamp("plan-review", planFile)
	if err != nil {
		rfEmitFail(w, "DIGEST_STAMP_FAILED", fmt.Sprintf("Failed to generate digest stamp: %v.", err))
		return 1
	}

	finalText := rfRenderFinalReport(
		rfParsePlanTitle(planText, planFile),
		stamp.RenderMarkdown(),
		summaryMap,
		structuralOK,
		strings.ReplaceAll(structuralEvidence, "\n", "\\n"),
		machineRows,
		findingsBody,
		blockingBody,
		improvementsBody,
		proceed,
		reason,
	)

	dir := filepath.Dir(finalFile)
	if err := os.MkdirAll(dir, 0755); err != nil {
		rfEmitFail(w, "WRITE_FAILED", fmt.Sprintf("Cannot create directory: %s.", dir))
		return 1
	}
	if err := os.WriteFile(finalFile, []byte(finalText), 0644); err != nil {
		rfEmitFail(w, "WRITE_FAILED", fmt.Sprintf("Cannot write final file: %s.", finalFile))
		return 1
	}

	// Delete draft (ignore if already gone).
	if err := os.Remove(draftFile); err != nil && !os.IsNotExist(err) {
		// Non-fatal, continue.
	}

	status := "PASS"
	code := "REVIEW_FINALIZED"
	exitCode := 0
	if proceed != "yes" {
		status = "FAIL"
		code = "REVIEW_BLOCKED"
		exitCode = 1
	}

	skitlog.Emit(w, skitlog.Result{
		Tool:    rfToolName,
		Status:  status,
		Code:    code,
		Summary: fmt.Sprintf("Review finalized: proceed=%s.", proceed),
	},
		slog.String("proceed", proceed),
		slog.String("reason", reason),
		slog.String("final_file", finalFile),
	)

	return exitCode
}

func rfStructuralEvidence(result *StcStructuralResult) string {
	if result.Passed {
		return fmt.Sprintf("All %d structural checks passed.", result.TotalChecks)
	}
	var failed []string
	for _, c := range result.Checks {
		if c.Status == "FAIL" {
			if c.Evidence != "" {
				failed = append(failed, fmt.Sprintf("%s: %s (%s)", c.ID, c.Summary, c.Evidence))
			} else {
				failed = append(failed, fmt.Sprintf("%s: %s", c.ID, c.Summary))
			}
		}
	}
	return strings.Join(failed, "; ")
}

func rfEmitFail(w io.Writer, code, summary string) {
	skitlog.Emit(w, skitlog.Result{
		Tool:    rfToolName,
		Status:  "FAIL",
		Code:    code,
		Summary: summary,
	})
}

// ReviewFinalize returns the review-finalize subcommand.
func ReviewFinalize() *cli.Command {
	return &cli.Command{
		Name:        "review-finalize",
		Description: "Finalize a plan review draft into the gate artifact",
		Run: func(args []string) int {
			return runReviewFinalize(os.Stdout, args)
		},
	}
}

func runReviewFinalize(w io.Writer, args []string) int {
	if len(args) > 0 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Fprintln(os.Stderr, "usage: skit review-finalize <plan-file> <draft-file> <final-file>")
		return 0
	}

	if len(args) != 3 {
		skitlog.Emit(w, skitlog.Result{
			Tool:    rfToolName,
			Status:  "FAIL",
			Code:    "INVALID_ARGUMENT_COUNT",
			Summary: "Usage: skit review-finalize <plan-file> <draft-file> <final-file>.",
		})
		return 1
	}

	return rfExecute(w, args[0], args[1], args[2])
}
