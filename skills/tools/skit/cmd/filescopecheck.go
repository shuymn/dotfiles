package cmd

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path"
	"regexp"
	"strconv"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const fileScopeCheckToolName = "file-scope-check"

const (
	scopeStatusOK        = "OK"
	scopeStatusException = "OK (exception)"
	scopeStatusDeviation = "SCOPE_DEVIATION"
)

var taskEndRe = regexp.MustCompile(`(?m)^(### Task \d+|## )`)

type exceptionEntry struct {
	Pattern   string
	Rationale string
}

type fileMatch struct {
	Path    string
	Pattern string
	Status  string
}

type fileEntry struct {
	Path    string `json:"path"`
	Pattern string `json:"pattern"`
	Status  string `json:"status"`
}

// FileScopeCheck returns the file-scope-check subcommand.
func FileScopeCheck() *cli.Command {
	c := cli.NewCommand("file-scope-check", "Verify that changed files fall within a task's Allowed/Exception Files scope")
	var taskID int
	c.IntVar(&taskID, "task", "", 0, "Task number (required)")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if taskID == 0 || len(s.Args) < 1 {
			return fmt.Errorf("usage: skit file-scope-check <plan-file> --task <N>")
		}
		return exitCode(runFileScopeCheck(os.Stdin, os.Stdout, taskID, s.Args[0]))
	}
	return c
}

func runFileScopeCheck(r io.Reader, w io.Writer, taskID int, planFile string) int {
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

	planText := string(planData)
	block := extractTaskBlock(planText, taskID)
	if block == "" {
		log.Emit(w, log.Result{
			Tool:    fileScopeCheckToolName,
			Status:  "FAIL",
			Code:    "TASK_NOT_FOUND",
			Summary: fmt.Sprintf("Task %d not found in plan.", taskID),
		}, slog.String("fix.1", "FIX_CHECK_TASK_ID"))
		return 1
	}

	allowed := parseAllowedFiles(block)
	if len(allowed) == 0 {
		log.Emit(w, log.Result{
			Tool:    fileScopeCheckToolName,
			Status:  "SKIP",
			Code:    "NO_ALLOWED_FILES",
			Summary: fmt.Sprintf("No Allowed Files defined for Task %d. Scope check skipped.", taskID),
		})
		return 0
	}

	exceptions := parseExceptionFiles(block)

	stdinData, err := io.ReadAll(r)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error reading stdin: %v\n", err)
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
		matches = append(matches, matchFile(f, allowed, exceptions))
	}

	return emitScopeResult(w, matches, taskID)
}

func emitScopeResult(w io.Writer, matches []fileMatch, taskID int) int {
	var deviations []fileMatch
	okCount := 0
	exceptionCount := 0
	for _, m := range matches {
		switch m.Status {
		case scopeStatusDeviation:
			deviations = append(deviations, m)
		case scopeStatusOK:
			okCount++
		case scopeStatusException:
			exceptionCount++
		}
	}

	overall := "PASS"
	code := "ALL_FILES_IN_SCOPE"
	summary := fmt.Sprintf("All %d file(s) within scope for Task %d.", len(matches), taskID)
	if len(deviations) > 0 {
		overall = "FAIL"
		code = "SCOPE_DEVIATION_DETECTED"
		summary = fmt.Sprintf("%d file(s) outside allowed scope for Task %d.", len(deviations), taskID)
	}

	entries := make([]fileEntry, len(matches))
	for i, m := range matches {
		entries[i] = fileEntry{Path: m.Path, Pattern: m.Pattern, Status: m.Status}
	}

	attrs := []slog.Attr{
		slog.Int("signal.task", taskID),
		slog.Int("signal.total_files", len(matches)),
		slog.Int("signal.ok", okCount),
		slog.Int("signal.exception", exceptionCount),
		slog.Int("signal.deviation", len(deviations)),
		slog.Any("files", entries),
	}

	if len(deviations) > 0 {
		var paths []string
		for _, d := range deviations {
			paths = append(paths, d.Path)
		}
		attrs = append(attrs,
			slog.String("evidence", strings.Join(paths, ", ")),
			slog.Any("fix", []string{
				"FIX_ADD_TO_ALLOWED_OR_EXCEPTION_FILES",
				"FIX_REVERT_OUT_OF_SCOPE_CHANGES",
			}),
		)
	}

	log.Emit(w, log.Result{
		Tool:    fileScopeCheckToolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(deviations) > 0 {
		return 1
	}
	return 0
}

func extractTaskBlock(planText string, taskID int) string {
	headerRe := regexp.MustCompile(`(?m)^### Task ` + strconv.Itoa(taskID) + `\b[^\n]*\n`)
	loc := headerRe.FindStringIndex(planText)
	if loc == nil {
		return ""
	}
	rest := planText[loc[1]:]
	endLoc := taskEndRe.FindStringIndex(rest)
	if endLoc == nil {
		return planText[loc[0]:]
	}
	return planText[loc[0] : loc[1]+endLoc[0]]
}

func extractFieldList(block, fieldName string) []string {
	re := regexp.MustCompile(`(?m)^-?\s*\*\*` + regexp.QuoteMeta(fieldName) + `\*\*:\s*\n((?:[ \t]+-[^\n]*\n?)*)`)
	m := re.FindStringSubmatch(block)
	if m == nil {
		return nil
	}
	return strings.Split(m[1], "\n")
}

func parseAllowedFiles(block string) []string {
	lines := extractFieldList(block, "Allowed Files")
	var patterns []string
	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "- ") {
			continue
		}
		payload := strings.TrimSpace(stripped[2:])
		if strings.HasPrefix(payload, "`") {
			if end := strings.Index(payload[1:], "`"); end >= 0 {
				patterns = append(patterns, payload[1:end+1])
				continue
			}
		}
		if payload != "" {
			patterns = append(patterns, strings.Fields(payload)[0])
		}
	}
	return patterns
}

var (
	exceptionBtRe    = regexp.MustCompile("^`([^`]+)`\\s*(?:\\(([^)]*)\\))?")
	exceptionPlainRe = regexp.MustCompile(`^(\S+)\s*(?:\(([^)]*)\))?`)
)

func parseExceptionFiles(block string) []exceptionEntry {
	lines := extractFieldList(block, "Exception Files")
	var results []exceptionEntry
	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "- ") {
			continue
		}
		payload := strings.TrimSpace(stripped[2:])
		m := exceptionBtRe.FindStringSubmatch(payload)
		if m == nil {
			m = exceptionPlainRe.FindStringSubmatch(payload)
		}
		if m != nil {
			rationale := ""
			if len(m) > 2 {
				rationale = m[2]
			}
			results = append(results, exceptionEntry{Pattern: m[1], Rationale: rationale})
		}
	}
	return results
}

func matchFile(filePath string, allowed []string, exceptions []exceptionEntry) fileMatch {
	for _, pattern := range allowed {
		if fullMatch(pattern, filePath) {
			return fileMatch{Path: filePath, Pattern: pattern, Status: scopeStatusOK}
		}
	}
	for _, exc := range exceptions {
		if fullMatch(exc.Pattern, filePath) {
			return fileMatch{
				Path:    filePath,
				Pattern: "EXCEPTION(" + exc.Pattern + ")",
				Status:  scopeStatusException,
			}
		}
	}
	return fileMatch{Path: filePath, Pattern: "NONE", Status: scopeStatusDeviation}
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
		// ** matches zero or more path segments
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
