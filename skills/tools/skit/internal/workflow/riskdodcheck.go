package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"regexp"
	"strconv"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const riskDodCheckToolName = "risk-dod-check"

// Exact annotation strings as defined in decompose-plan SKILL.md Step 2.6.
const (
	rdcDodCritical     = "Adversarial verification required (minimum 3 probes)."
	rdcDodSensitive1   = "Heightened dod-recheck scrutiny applies."
	rdcDodSensitive2   = "Adversarial verification required (minimum 2 probes: Category 1 + most relevant 1 category)."
	rdcDodStandardImpl = "Adversarial verification required (1 probe: most relevant category)."
)

var (
	// File path patterns that identify non-implementation (test/doc/config) files.
	rdcImplExcludeRe = regexp.MustCompile(`(?i)(?:test|spec|\.md$|^docs/|\.txt$)`)

	rdcTaskRe = regexp.MustCompile(`(?ms)^(### Task (\d+)\b[^\n]*\n.*?)(?:^### Task \d+|^## |\z)`)

	rdcFilesRe = regexp.MustCompile(`(?m)^\s*-?\s*\*\*(?:Allowed Files|Files)\*\*:\s*\n((?:[ \t]+-[^\n]*\n?)*)`)

	rdcDodRe = regexp.MustCompile(`(?s)\*\*DoD\*\*\s*:?\s*(.*?)(?:\*\*[A-Z]|\z)`)

	rdcBacktickRe = regexp.MustCompile("`([^`]+)`")
)

type rdcTask struct {
	ID   int
	Body string
}

// RiskDodCheck returns the risk-dod-check subcommand.
func RiskDodCheck() *cli.Command {
	c := cli.NewCommand("risk-dod-check", "Check that task DoD entries contain required risk tier annotations")
	var planFile, designFile string
	c.StringArg(&planFile, "plan-file", "Plan file to inspect")
	c.StringArg(&designFile, "design-file", "Design file to inspect")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runRiskDodCheck(s.Stdout, planFile, designFile))
	}
	return c
}

func runRiskDodCheck(w io.Writer, planPath, designPath string) int {
	planData, err := os.ReadFile(planPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    riskDodCheckToolName,
			Status:  "FAIL",
			Code:    "PLAN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Plan file not found: %s", planPath),
		}, slog.Any("fix", []string{"FIX_PLAN_FILE_PATH"}))
		return 1
	}

	designData, err := os.ReadFile(designPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    riskDodCheckToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s", designPath),
		}, slog.Any("fix", []string{"FIX_DESIGN_FILE_PATH"}))
		return 1
	}

	maxTier := rdcParseMaxRiskTier(string(designData))
	tasks := rdcExtractTasks(string(planData))

	if len(tasks) == 0 {
		log.Emit(w, log.Result{
			Tool:    riskDodCheckToolName,
			Status:  "SKIP",
			Code:    "NO_TASKS_FOUND",
			Summary: "No tasks found in plan.md.",
		})
		return 0
	}

	var allIssues []string
	for _, task := range tasks {
		allIssues = append(allIssues, rdcCheckTask(task.ID, task.Body, maxTier)...)
	}

	status := "PASS"
	code := "ALL_RISK_DOD_ANNOTATIONS_PRESENT"
	summary := fmt.Sprintf("All %d task(s) have required risk tier DoD annotations (tier=%s).", len(tasks), maxTier)

	if len(allIssues) > 0 {
		status = "FAIL"
		code = "RISK_DOD_ANNOTATIONS_MISSING"
		summary = fmt.Sprintf("%d task(s) missing required risk tier DoD annotation(s).", len(allIssues))
	}

	attrs := []slog.Attr{
		slog.String("signal.max_tier", maxTier),
		slog.Int("signal.total_tasks", len(tasks)),
		slog.Int("signal.issues", len(allIssues)),
	}
	for i, issue := range allIssues {
		attrs = append(attrs, slog.String(fmt.Sprintf("issue.%d", i+1), issue))
	}
	if len(allIssues) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_ADD_ADVERSARIAL_VERIFICATION_DOD_LINE",
			"FIX_ADD_HEIGHTENED_SCRUTINY_DOD_LINE",
		}))
	}

	log.Emit(w, log.Result{
		Tool:    riskDodCheckToolName,
		Status:  status,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(allIssues) > 0 {
		return 1
	}
	return 0
}

// rdcParseMaxRiskTier returns the highest risk tier found in ## Risk Classification.
func rdcParseMaxRiskTier(text string) string {
	section := extractSection(text, "Risk Classification")
	if section == "" {
		return "Standard"
	}
	tierOrder := map[string]int{"Critical": 3, "Sensitive": 2, "Standard": 1}
	rows := parseRiskClassificationRows(section)
	maxTier := "Standard"
	for _, row := range rows {
		tier := strings.TrimSpace(row.RiskTier)
		if tier == "" {
			tier = "Standard"
		}
		if tierOrder[tier] > tierOrder[maxTier] {
			maxTier = tier
		}
	}
	return maxTier
}

// rdcExtractTasks extracts task id + body from plan text.
func rdcExtractTasks(text string) []rdcTask {
	var tasks []rdcTask
	matches := rdcTaskRe.FindAllStringSubmatch(text, -1)
	for _, m := range matches {
		if len(m) < 3 {
			continue
		}
		id, _ := strconv.Atoi(m[2])
		tasks = append(tasks, rdcTask{ID: id, Body: m[1]})
	}
	return tasks
}

// rdcGetTaskFiles extracts file paths from Allowed Files or Files fields.
func rdcGetTaskFiles(body string) []string {
	var files []string
	matches := rdcFilesRe.FindAllStringSubmatch(body, -1)
	for _, m := range matches {
		if len(m) < 2 {
			continue
		}
		for _, line := range strings.Split(m[1], "\n") {
			stripped := strings.TrimSpace(line)
			if !strings.HasPrefix(stripped, "- ") {
				continue
			}
			payload := strings.TrimSpace(stripped[2:])
			if payload == "" {
				continue
			}
			btMatch := rdcBacktickRe.FindStringSubmatch(payload)
			if btMatch != nil {
				files = append(files, btMatch[1])
			} else {
				fields := strings.Fields(payload)
				if len(fields) > 0 {
					files = append(files, fields[0])
				}
			}
		}
	}
	return files
}

// rdcHasImplFiles reports whether any file is an implementation file (not test/doc/config).
func rdcHasImplFiles(files []string) bool {
	for _, f := range files {
		if !rdcImplExcludeRe.MatchString(f) {
			return true
		}
	}
	return false
}

// rdcGetDodText extracts DoD text from task body.
func rdcGetDodText(body string) string {
	m := rdcDodRe.FindStringSubmatch(body)
	if m != nil {
		return m[1]
	}
	return body
}

// rdcCheckTask returns a list of issues for the given task.
func rdcCheckTask(id int, body, maxTier string) []string {
	dod := rdcGetDodText(body)
	var issues []string

	switch maxTier {
	case "Critical":
		if !strings.Contains(dod, rdcDodCritical) {
			issues = append(issues, fmt.Sprintf("Task %d (Critical): missing DoD: %q", id, rdcDodCritical))
		}
	case "Sensitive":
		for _, annotation := range []string{rdcDodSensitive1, rdcDodSensitive2} {
			if !strings.Contains(dod, annotation) {
				issues = append(issues, fmt.Sprintf("Task %d (Sensitive): missing DoD: %q", id, annotation))
			}
		}
	default: // Standard
		files := rdcGetTaskFiles(body)
		if rdcHasImplFiles(files) && !strings.Contains(dod, rdcDodStandardImpl) {
			issues = append(issues, fmt.Sprintf("Task %d (Standard+impl): missing DoD: %q", id, rdcDodStandardImpl))
		}
	}

	return issues
}
