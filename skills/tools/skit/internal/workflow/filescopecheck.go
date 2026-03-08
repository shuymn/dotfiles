package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const fileScopeCheckToolName = "file-scope-check"

const (
	scopeStatusOwned        = "OWNED_OK"
	scopeStatusShared       = "SHARED_OK"
	scopeStatusCrossBoundary = "CROSS_BOUNDARY"
	scopeStatusProhibited   = "PROHIBITED"
)

type fileMatch struct {
	Path      string
	Pattern   string
	Status    string
	Rationale string
}

type fileEntry struct {
	Path      string `json:"path"`
	Pattern   string `json:"pattern"`
	Status    string `json:"status"`
	Rationale string `json:"rationale,omitempty"`
}

// FileScopeCheck returns the file-scope-check subcommand.
func FileScopeCheck() *cli.Command {
	c := cli.NewCommand("file-scope-check", "Verify that changed files satisfy a task Scope Contract")
	var taskID int
	var planFile string
	c.IntVar(&taskID, "task", "", 0, "Task number (required)")
	c.StringArg(&planFile, "plan-file", "Plan file to inspect")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if taskID == 0 {
			return fmt.Errorf("--task is required")
		}
		return exitCode(runFileScopeCheck(s.Stdin, s.Stdout, s.Stderr, taskID, planFile))
	}
	return c
}

func runFileScopeCheck(r io.Reader, w, stderr io.Writer, taskID int, planFile string) int {
	planData, err := os.ReadFile(planFile)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    fileScopeCheckToolName,
			Status:  "FAIL",
			Code:    "PLAN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Plan file not found: %s", planFile),
		}, slog.String("fix.1", "FIX_PLAN_FILE_PATH"))
		return 1
	}

	block := extractTaskBlock(string(planData), taskID)
	if block == "" {
		log.Emit(w, log.Result{
			Tool:    fileScopeCheckToolName,
			Status:  "FAIL",
			Code:    "TASK_NOT_FOUND",
			Summary: fmt.Sprintf("Task %d not found in plan.", taskID),
		}, slog.String("fix.1", "FIX_CHECK_TASK_ID"))
		return 1
	}

	scope, scopeIssues := parseScopeContract(block)
	if len(scope.Owned) == 0 {
		log.Emit(w, log.Result{
			Tool:    fileScopeCheckToolName,
			Status:  "FAIL",
			Code:    "NO_OWNED_PATHS",
			Summary: fmt.Sprintf("Task %d is missing Scope Contract Owned Paths.", taskID),
		}, slog.Any("fix", append([]string{"FIX_ADD_SCOPE_CONTRACT_OWNED_PATHS"}, scopeIssues...)))
		return 1
	}

	stdinData, err := io.ReadAll(r)
	if err != nil {
		fmt.Fprintf(stderr, "error reading stdin: %v\n", err)
		return 1
	}

	var changedFiles []string
	for _, line := range strings.Split(string(stdinData), "\n") {
		if trimmed := strings.TrimSpace(line); trimmed != "" {
			changedFiles = append(changedFiles, trimmed)
		}
	}

	if len(changedFiles) == 0 {
		log.Emit(w, log.Result{
			Tool:    fileScopeCheckToolName,
			Status:  "SKIP",
			Code:    "NO_CHANGED_FILES",
			Summary: "No changed files provided on stdin.",
		})
		return 0
	}

	var matches []fileMatch
	for _, f := range changedFiles {
		matches = append(matches, matchFile(f, scope))
	}

	return emitScopeResult(w, matches, taskID, scopeIssues)
}

func emitScopeResult(w io.Writer, matches []fileMatch, taskID int, scopeIssues []string) int {
	ownedCount := 0
	sharedCount := 0
	crossCount := 0
	prohibitedCount := 0
	for _, m := range matches {
		switch m.Status {
		case scopeStatusOwned:
			ownedCount++
		case scopeStatusShared:
			sharedCount++
		case scopeStatusCrossBoundary:
			crossCount++
		case scopeStatusProhibited:
			prohibitedCount++
		}
	}

	overall := "PASS"
	code := "SCOPE_CONTRACT_SATISFIED"
	summary := fmt.Sprintf("All %d file(s) satisfy the Scope Contract for Task %d.", len(matches), taskID)
	exitCode := 0
	if prohibitedCount > 0 {
		overall = "FAIL"
		code = "PROHIBITED_PATH_CHANGE_DETECTED"
		summary = fmt.Sprintf("%d file(s) hit Prohibited Paths for Task %d.", prohibitedCount, taskID)
		exitCode = 1
	} else if crossCount > 0 {
		overall = "FAIL"
		code = "CROSS_BOUNDARY_CHANGE_DETECTED"
		summary = fmt.Sprintf("%d file(s) are outside Owned Paths / Shared Touchpoints for Task %d.", crossCount, taskID)
		exitCode = 1
	}

	entries := make([]fileEntry, len(matches))
	for i, m := range matches {
		entries[i] = fileEntry{
			Path:      m.Path,
			Pattern:   m.Pattern,
			Status:    m.Status,
			Rationale: m.Rationale,
		}
	}

	attrs := []slog.Attr{
		slog.Int("signal.task", taskID),
		slog.Int("signal.total_files", len(matches)),
		slog.Int("signal.owned", ownedCount),
		slog.Int("signal.shared", sharedCount),
		slog.Int("signal.cross_boundary", crossCount),
		slog.Int("signal.prohibited", prohibitedCount),
		slog.Any("files", entries),
	}
	if len(scopeIssues) > 0 {
		attrs = append(attrs, slog.Any("scope_contract_issues", scopeIssues))
	}
	if exitCode != 0 {
		var paths []string
		for _, m := range matches {
			if m.Status == scopeStatusCrossBoundary || m.Status == scopeStatusProhibited {
				paths = append(paths, m.Path)
			}
		}
		attrs = append(attrs,
			slog.String("evidence", strings.Join(paths, ", ")),
			slog.Any("fix", []string{
				"FIX_RESLICE_PLAN_FOR_CROSS_BOUNDARY_WORK",
				"FIX_REVERT_PROHIBITED_PATH_CHANGES",
			}),
		)
	}

	log.Emit(w, log.Result{
		Tool:    fileScopeCheckToolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	return exitCode
}

func matchFile(filePath string, scope scopeContract) fileMatch {
	for _, pattern := range scope.Prohibited {
		if fullMatch(pattern.Pattern, filePath) {
			return fileMatch{
				Path:      filePath,
				Pattern:   pattern.Pattern,
				Status:    scopeStatusProhibited,
				Rationale: pattern.Rationale,
			}
		}
	}
	for _, pattern := range scope.Owned {
		if fullMatch(pattern.Pattern, filePath) {
			return fileMatch{
				Path:      filePath,
				Pattern:   pattern.Pattern,
				Status:    scopeStatusOwned,
				Rationale: pattern.Rationale,
			}
		}
	}
	for _, pattern := range scope.Shared {
		if fullMatch(pattern.Pattern, filePath) {
			return fileMatch{
				Path:      filePath,
				Pattern:   pattern.Pattern,
				Status:    scopeStatusShared,
				Rationale: pattern.Rationale,
			}
		}
	}
	return fileMatch{Path: filePath, Pattern: "NONE", Status: scopeStatusCrossBoundary}
}

// fullMatch reports whether pattern matches path using glob semantics,
// including support for ** (matches zero or more path segments).
func fullMatch(pattern, filePath string) bool {
	return matchParts(strings.Split(pattern, "/"), strings.Split(filePath, "/"))
}

func matchParts(patParts, pathParts []string) bool {
	if len(patParts) == 0 {
		return len(pathParts) == 0
	}
	if patParts[0] == "**" {
		if matchParts(patParts[1:], pathParts) {
			return true
		}
		for i := 1; i <= len(pathParts); i++ {
			if matchParts(patParts[1:], pathParts[i:]) {
				return true
			}
		}
		return false
	}
	if len(pathParts) == 0 {
		return false
	}
	matched, err := path.Match(patParts[0], pathParts[0])
	if err != nil || !matched {
		return false
	}
	return matchParts(patParts[1:], pathParts[1:])
}

