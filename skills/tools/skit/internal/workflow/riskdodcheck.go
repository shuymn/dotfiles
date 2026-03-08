package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const riskDodCheckToolName = "risk-dod-check"

const (
	rdcLegacyCritical     = "Adversarial verification required (minimum 3 probes)."
	rdcLegacySensitive1   = "Heightened dod-recheck scrutiny applies."
	rdcLegacySensitive2   = "Adversarial verification required (minimum 2 probes: Category 1 + most relevant 1 category)."
	rdcLegacyStandardImpl = "Adversarial verification required (1 probe: most relevant category)."
)

var rdcAllowedRiskTiers = map[string]bool{
	"Standard":  true,
	"Sensitive": true,
	"Critical":  true,
}

// RiskDodCheck returns the risk-dod-check subcommand.
func RiskDodCheck() *cli.Command {
	c := cli.NewCommand("risk-dod-check", "Check risk-driven task contract requirements")
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
	if _, err := os.ReadFile(designPath); err != nil {
		log.Emit(w, log.Result{
			Tool:    riskDodCheckToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s", designPath),
		}, slog.Any("fix", []string{"FIX_DESIGN_FILE_PATH"}))
		return 1
	}

	tasks := extractTaskBlocks(string(planData))
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
		allIssues = append(allIssues, rdcCheckTask(task)...)
	}

	status := "PASS"
	code := "ALL_TASK_CONTRACTS_VALID"
	summary := fmt.Sprintf("All %d task(s) satisfy risk-driven task contract checks.", len(tasks))
	if len(allIssues) > 0 {
		status = "FAIL"
		code = "TASK_CONTRACT_ISSUES"
		summary = fmt.Sprintf("%d task contract issue(s) found.", len(allIssues))
	}

	attrs := []slog.Attr{
		slog.Int("signal.total_tasks", len(tasks)),
		slog.Int("signal.issues", len(allIssues)),
	}
	for i, issue := range allIssues {
		attrs = append(attrs, slog.String(fmt.Sprintf("issue.%d", i+1), issue))
	}
	if len(allIssues) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_ADD_TASK_LEVEL_RISK_TIER",
			"FIX_ADD_SCOPE_CONTRACT_OWNED_PATHS",
			"FIX_ADD_BOUNDARY_VERIFICATION_FOR_SENSITIVE_OR_CRITICAL_TASKS",
			"FIX_REMOVE_LEGACY_RISK_DOD_BOILERPLATE",
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

func rdcCheckTask(task taskContract) []string {
	var issues []string
	taskLabel := fmt.Sprintf("Task %d", task.ID)

	if !rdcAllowedRiskTiers[task.RiskTier] {
		issues = append(issues, fmt.Sprintf("%s: missing or invalid Risk Tier %q", taskLabel, task.RiskTier))
	}
	if len(task.Scope.Owned) == 0 {
		issues = append(issues, fmt.Sprintf("%s: Scope Contract is missing Owned Paths", taskLabel))
	}
	for _, shared := range task.Scope.Shared {
		if shared.Rationale == "" {
			issues = append(issues, fmt.Sprintf("%s: Shared Touchpoint %q is missing a rationale", taskLabel, shared.Pattern))
		}
	}
	if (task.RiskTier == "Sensitive" || task.RiskTier == "Critical") && strings.TrimSpace(task.BoundaryVerification) == "" {
		issues = append(issues, fmt.Sprintf("%s (%s): missing Boundary Verification", taskLabel, task.RiskTier))
	}
	for _, legacy := range []string{rdcLegacyCritical, rdcLegacySensitive1, rdcLegacySensitive2, rdcLegacyStandardImpl} {
		if strings.Contains(task.Block, legacy) {
			issues = append(issues, fmt.Sprintf("%s: legacy DoD boilerplate still present: %q", taskLabel, legacy))
		}
	}
	for _, legacyField := range []string{"Allowed Files", "Exception Files", "Files"} {
		if extractFieldValue(task.Block, legacyField) != "" || len(extractFieldList(task.Block, legacyField)) > 0 {
			issues = append(issues, fmt.Sprintf("%s: legacy field %q must be removed in favor of Scope Contract", taskLabel, legacyField))
		}
	}
	return issues
}

