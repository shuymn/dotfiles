package workflow

import (
	"context"
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

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
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

	rfTaskHeadRe   = regexp.MustCompile(`(?m)^### Task (\d+):`)
	rfTitleRe      = regexp.MustCompile(`(?m)^# (.+)$`)
	rfSourceLineRe = regexp.MustCompile(`(?m)^- \*\*Source\*\*: ` + "`([^`]+)`")

	rfAllowedTaskShapePredicates = map[string]bool{
		"MULTI_OBJECTIVE":                 true,
		"BOUNDARY_WITHOUT_VERIFICATION":   true,
		"RUNTIME_PATH_WITHOUT_REAL_CHECK": true,
		"OWNERSHIP_TOO_BROAD":             true,
		"HARNESS_ONLY_CLOSURE":            true,
	}
)

type rfTaskShapeFinding struct {
	Task      string
	Severity  string
	Predicate string
	Evidence  string
	Action    string
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
		return resolveRepoRelativePath(planPath, source)
	}
	return filepath.Join(filepath.Dir(planPath), "design.md")
}

func rfParseTaskShapeFindings(body string, validTasks []string) ([]rfTaskShapeFinding, []string) {
	if strings.TrimSpace(body) == "" {
		return nil, nil
	}

	rows := parseGenericTable(body)
	if len(rows) == 0 {
		return nil, []string{"Task Shape Findings section must contain a markdown table."}
	}

	validTaskSet := make(map[string]bool, len(validTasks))
	for _, task := range validTasks {
		validTaskSet[task] = true
	}

	var findings []rfTaskShapeFinding
	var issues []string
	for _, row := range rows {
		finding := rfTaskShapeFinding{
			Task:      strings.TrimSpace(firstNonEmpty(row["Task"], row["task"])),
			Severity:  strings.ToLower(strings.TrimSpace(firstNonEmpty(row["Severity"], row["severity"]))),
			Predicate: strings.TrimSpace(firstNonEmpty(row["Predicate"], row["predicate"])),
			Evidence:  strings.TrimSpace(firstNonEmpty(row["Evidence"], row["evidence"])),
			Action:    strings.TrimSpace(firstNonEmpty(row["Action"], row["action"])),
		}
		if finding.Task == "" {
			issues = append(issues, "Task Shape Findings contains a row without Task.")
			continue
		}
		if finding.Task != "General" && !validTaskSet[finding.Task] {
			issues = append(issues, fmt.Sprintf("Task Shape Findings references unknown task `%s`.", finding.Task))
		}
		if finding.Severity != "blocker" && finding.Severity != "warning" && finding.Severity != "info" {
			issues = append(issues, fmt.Sprintf("Task Shape Findings row for `%s` has invalid severity `%s`.", finding.Task, finding.Severity))
			continue
		}
		if !rfAllowedTaskShapePredicates[finding.Predicate] {
			issues = append(issues, fmt.Sprintf("Task Shape Findings row for `%s` has invalid predicate `%s`.", finding.Task, finding.Predicate))
			continue
		}
		if finding.Evidence == "" || finding.Action == "" {
			issues = append(issues, fmt.Sprintf("Task Shape Findings row for `%s` is missing Evidence or Action.", finding.Task))
			continue
		}
		findings = append(findings, finding)
	}

	sort.SliceStable(findings, func(i, j int) bool {
		if findings[i].Task == findings[j].Task {
			if findings[i].Severity == findings[j].Severity {
				return findings[i].Predicate < findings[j].Predicate
			}
			return findings[i].Severity < findings[j].Severity
		}
		return findings[i].Task < findings[j].Task
	})
	return findings, issues
}

func rfMakeDecisionReason(structuralOK bool, summaryMap map[string]string, taskShape []rfTaskShapeFinding) (string, string) {
	var failingSummary []string
	for _, field := range rfSummaryFields {
		if summaryMap[field] == "FAIL" {
			failingSummary = append(failingSummary, field)
		}
	}

	var blockers []string
	for _, finding := range taskShape {
		if finding.Severity == "blocker" {
			blockers = append(blockers, finding.Task+"("+finding.Predicate+")")
		}
	}

	if structuralOK && len(failingSummary) == 0 && len(blockers) == 0 {
		return "yes", "Structural check passed, all summary viewpoints passed or were N/A, and task shape blockers are absent."
	}

	var reasons []string
	if !structuralOK {
		reasons = append(reasons, "structural check failed")
	}
	if len(failingSummary) > 0 {
		reasons = append(reasons, "summary failures: "+strings.Join(failingSummary, ", "))
	}
	if len(blockers) > 0 {
		reasons = append(reasons, "task shape blockers: "+strings.Join(blockers, ", "))
	}
	return "no", strings.Join(reasons, "; ")
}

func rfNormalizeSection(body, fallback string) string {
	trimmed := strings.TrimSpace(body)
	if trimmed == "" {
		return fallback
	}
	return trimmed
}

func rfBuildBlockingIssuesSection(reviewerBody string, autoBlockers []string) string {
	var parts []string
	if trimmed := strings.TrimSpace(reviewerBody); trimmed != "" {
		parts = append(parts, trimmed)
	}
	if len(autoBlockers) > 0 {
		var items []string
		for _, blocker := range autoBlockers {
			items = append(items, "- [ ] "+blocker)
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
	taskShape []rfTaskShapeFinding,
	findingsBody string,
	blockingBody string,
	improvementsBody string,
	proceed string,
	reason string,
) string {
	updatedAt := time.Now().Local().Format("2006-01-02 15:04 MST")

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
	for _, finding := range taskShape {
		if finding.Severity == "blocker" {
			overallVerdict = "FAIL"
			break
		}
	}

	summaryLines := []string{
		fmt.Sprintf("- Forward Fidelity: %s", summaryMap["Forward Fidelity"]),
		fmt.Sprintf("- Reverse Fidelity: %s", summaryMap["Reverse Fidelity"]),
		fmt.Sprintf("- Round-trip: %s", summaryMap["Round-trip"]),
		fmt.Sprintf("- Behavioral Lock: %s", summaryMap["Behavioral Lock"]),
		fmt.Sprintf("- Negative Path: %s", summaryMap["Negative Path"]),
		fmt.Sprintf("- Temporal: %s", summaryMap["Temporal"]),
		fmt.Sprintf("- Traceability: %s", summaryMap["Traceability"]),
		fmt.Sprintf("- Scope: %s", summaryMap["Scope"]),
		fmt.Sprintf("- Testability: %s", summaryMap["Testability"]),
		fmt.Sprintf("- Execution Readiness: %s", summaryMap["Execution Readiness"]),
		fmt.Sprintf("- Integration Coverage: %s", summaryMap["Integration Coverage"]),
		fmt.Sprintf("- Risk Classification: %s", summaryMap["Risk Classification"]),
		fmt.Sprintf("- Updated At: %s", updatedAt),
	}

	blockers := 0
	warnings := 0
	info := 0
	var shapeRows []string
	for _, finding := range taskShape {
		switch finding.Severity {
		case "blocker":
			blockers++
		case "warning":
			warnings++
		case "info":
			info++
		}
		shapeRows = append(shapeRows, fmt.Sprintf(
			"| %s | %s | %s | %s | %s |",
			finding.Task, finding.Severity, finding.Predicate, finding.Evidence, finding.Action,
		))
	}
	if len(shapeRows) == 0 {
		shapeRows = append(shapeRows, "| General | info | n/a | No task shape findings recorded. | - |")
	}

	structuralEvidenceDisplay := structuralEvidence
	if structuralEvidenceDisplay == "" {
		structuralEvidenceDisplay = "not captured"
	}
	taskShapeBlockers := "none"
	if blockers > 0 {
		taskShapeBlockers = strconv.Itoa(blockers)
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
		"## Task Shape Findings",
		"",
		fmt.Sprintf("- **Structural Check**: %s", map[bool]string{true: "PASS", false: "FAIL"}[structuralOK]),
		fmt.Sprintf("- **Structural Evidence**: %s", structuralEvidenceDisplay),
		fmt.Sprintf("- **Task Shape Blockers**: %s", taskShapeBlockers),
		fmt.Sprintf("- **Task Shape Warnings**: %d", warnings),
		fmt.Sprintf("- **Task Shape Info**: %d", info),
		"",
		"| Task | Severity | Predicate | Evidence | Action |",
		"|------|----------|-----------|----------|--------|",
	)
	lines = append(lines, shapeRows...)
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
		"Implementation correctness is verified by dod-recheck (L4), adversarial-verify (L5), and completion-audit (final closure).",
		"Plan PASS does not imply implementation PASS.",
		"",
	)

	return strings.Join(lines, "\n")
}

func rfExecute(w io.Writer, planPath, draftPath, finalPath string, dryRun bool) int {
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

	summaryBody := extractSection(draftText, "Summary")
	if summaryBody == "" {
		summaryBody = extractSection(draftText, "Reviewer Summary")
	}
	summaryMap, summaryErrors := rfParseSummary(summaryBody)

	taskShapeBody := extractSection(draftText, "Task Shape Findings")
	taskShapeFindings, taskShapeErrors := rfParseTaskShapeFindings(taskShapeBody, taskIDs)

	findingsBody := rfNormalizeSection(
		extractSection(draftText, "Findings"),
		strings.Join([]string{
			"| ID | Severity | Area | File/Section | Issue | Action |",
			"|----|----------|------|--------------|-------|--------|",
			"| M1 | blocker | review-finalize | draft | Draft omitted the Findings section. | Add reviewer findings and re-run finalization. |",
		}, "\n"),
	)
	improvementsBody := rfNormalizeSection(
		extractSection(draftText, "Non-Blocking Improvements"),
		"- None.",
	)

	designPath := rfParseDesignPath(planText, planFile)
	structResult := StcRunStructuralChecks(designPath, planFile)
	structuralOK := structResult.Passed
	structuralEvidence := rfStructuralEvidence(structResult)

	var autoBlockers []string
	if !structuralOK {
		autoBlockers = append(autoBlockers, "Resolve structural-check failures before rerunning review finalization.")
	}
	for _, issue := range summaryErrors {
		autoBlockers = append(autoBlockers, issue)
	}
	for _, issue := range taskShapeErrors {
		autoBlockers = append(autoBlockers, issue)
	}
	for _, finding := range taskShapeFindings {
		if finding.Severity == "blocker" {
			autoBlockers = append(autoBlockers, fmt.Sprintf("%s: %s (%s)", finding.Task, finding.Predicate, finding.Evidence))
		}
	}

	blockingBody := rfBuildBlockingIssuesSection(
		extractSection(draftText, "Blocking Issues"),
		autoBlockers,
	)

	proceed, reason := rfMakeDecisionReason(structuralOK, summaryMap, taskShapeFindings)

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
		structuralEvidence,
		taskShapeFindings,
		findingsBody,
		blockingBody,
		improvementsBody,
		proceed,
		reason,
	)

	if !dryRun {
		dir := filepath.Dir(finalFile)
		if err := os.MkdirAll(dir, 0755); err != nil {
			rfEmitFail(w, "WRITE_FAILED", fmt.Sprintf("Cannot create directory: %s.", dir))
			return 1
		}
		if err := os.WriteFile(finalFile, []byte(finalText), 0644); err != nil {
			rfEmitFail(w, "WRITE_FAILED", fmt.Sprintf("Cannot write final file: %s.", finalFile))
			return 1
		}
		if err := os.Remove(draftFile); err != nil && !os.IsNotExist(err) {
			// Ignore draft cleanup failures.
		}
	}

	status := "PASS"
	code := "REVIEW_FINALIZED"
	exitCode := 0
	if proceed != "yes" {
		status = "FAIL"
		code = "REVIEW_BLOCKED"
		exitCode = 1
	}

	log.Emit(w, log.Result{
		Tool:    rfToolName,
		Status:  status,
		Code:    code,
		Summary: fmt.Sprintf("Review finalized: proceed=%s.", proceed),
	},
		slog.String("proceed", proceed),
		slog.String("reason", reason),
		slog.String("final_file", finalFile),
		slog.Bool("dry_run", dryRun),
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
	log.Emit(w, log.Result{
		Tool:    rfToolName,
		Status:  "FAIL",
		Code:    code,
		Summary: summary,
	})
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

// ReviewFinalize returns the review-finalize subcommand.
func ReviewFinalize() *cli.Command {
	c := cli.NewCommand("review-finalize", "Finalize a plan review draft into the gate artifact")
	c.EnableDryRun()
	var planFile, draftFile, finalFile string
	c.StringArg(&planFile, "plan-file", "Plan bundle file")
	c.StringArg(&draftFile, "draft-file", "Draft review artifact")
	c.StringArg(&finalFile, "final-file", "Final review artifact path")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runReviewFinalize(s.Stdout, planFile, draftFile, finalFile, s.DryRun))
	}
	return c
}

func runReviewFinalize(w io.Writer, planFile, draftFile, finalFile string, dryRun bool) int {
	return rfExecute(w, planFile, draftFile, finalFile, dryRun)
}
