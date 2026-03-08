package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

const gcToolName = "gate-check"

var (
	gcOverallVerdictRe  = regexp.MustCompile(`(?m)^\s*-?\s*\*{0,2}Overall Verdict\*{0,2}:\s*(.*)$`)
	gcListVerdictRe     = regexp.MustCompile(`^- [A-Za-z][A-Za-z /()-]*:\s*(PASS|FAIL|N/A)`)
	gcOverallVerdictPfx = regexp.MustCompile(`^- \*{0,2}Overall Verdict`)
	gcTableRowNumRe     = regexp.MustCompile(`^\|[[:space:]]*[0-9]+[[:space:]]*\|`)
)

// GateCheck returns the gate-check subcommand.
func GateCheck() *cli.Command {
	c := cli.NewCommand("gate-check", "Verify review gate before downstream skill execution")
	var reviewFile, sourceFile string
	c.StringArg(&reviewFile, "review-file", "Review artifact to validate")
	c.StringArg(&sourceFile, "source-file", "Source artifact linked from the review")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runGateCheck(s.Stdout, reviewFile, sourceFile))
	}
	return c
}

func runGateCheck(w io.Writer, reviewFile, sourceFile string) int {
	displayReviewFile := pathutil.DisplayPath(reviewFile)

	// Check 1: Review file existence + read
	reviewBytes, err := os.ReadFile(reviewFile)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    gcToolName,
			Status:  "FAIL",
			Code:    "REVIEW_FILE_NOT_FOUND",
			Summary: "Review file was not found.",
		},
			slog.String("signal.missing_path", displayReviewFile),
			slog.String("fix.1", "FIX_REVIEW_FILE_PATH"),
		)
		return 1
	}
	content := string(reviewBytes)

	// Check 2: Overall Verdict
	verdictValue := gcParseOverallVerdict(content)
	if verdictValue == "" {
		log.Emit(w, log.Result{
			Tool:    gcToolName,
			Status:  "FAIL",
			Code:    "MISSING_OVERALL_VERDICT",
			Summary: "Could not find Overall Verdict in review file.",
		},
			slog.String("fix.1", "FIX_ADD_OVERALL_VERDICT_LINE"),
		)
		return 1
	}
	if verdictValue != "PASS" && verdictValue != "FAIL" {
		log.Emit(w, log.Result{
			Tool:    gcToolName,
			Status:  "FAIL",
			Code:    "INVALID_OVERALL_VERDICT_VALUE",
			Summary: "Overall Verdict value is invalid.",
		},
			slog.String("signal.actual_overall_verdict", verdictValue),
			slog.String("fix.1", "FIX_NORMALIZE_OVERALL_VERDICT"),
		)
		return 1
	}
	if verdictValue != "PASS" {
		log.Emit(w, log.Result{
			Tool:    gcToolName,
			Status:  "FAIL",
			Code:    "OVERALL_VERDICT_NOT_PASS",
			Summary: "Overall Verdict is FAIL.",
		},
			slog.String("signal.actual_overall_verdict", verdictValue),
			slog.String("fix.1", "FIX_RESOLVE_REVIEW_FINDINGS"),
			slog.String("fix.2", "FIX_REGENERATE_REVIEW"),
		)
		return 1
	}

	// Check 3: Source freshness (whole-source for review artifacts, task-contract for task-scoped artifacts).
	meta := extractMetadata(content)
	if meta.SourceArtifact == "" && !isTaskScopedArtifact(filepath.Base(reviewFile)) {
		if meta.SourceDigest == "" {
			log.Emit(w, log.Result{
				Tool:    gcToolName,
				Status:  "FAIL",
				Code:    "MISSING_SOURCE_DIGEST",
				Summary: "Could not extract Source Digest from review file.",
			},
				slog.String("fix.1", "FIX_ADD_SOURCE_DIGEST"),
				slog.String("fix.2", "FIX_REGENERATE_HEADER"),
			)
			return 1
		}
		currentDigest, err := sha256File(sourceFile)
		if err != nil {
			log.Emit(w, log.Result{
				Tool:    gcToolName,
				Status:  "FAIL",
				Code:    "SOURCE_FILE_NOT_FOUND",
				Summary: "Source file could not be read.",
			},
				slog.String("fix.1", "FIX_SOURCE_FILE_PATH"),
			)
			return 1
		}
		if currentDigest != meta.SourceDigest {
			log.Emit(w, log.Result{
				Tool:    gcToolName,
				Status:  "FAIL",
				Code:    "SOURCE_DIGEST_MISMATCH",
				Summary: "Source Digest does not match current source file.",
			},
				slog.String("fix.1", "FIX_RERUN_REVIEW_ON_CURRENT_SOURCE"),
				slog.String("fix.2", "FIX_UPDATE_SOURCE_DIGEST"),
			)
			return 1
		}
	} else {
		baseDir := repoRootFromPath(sourceFile)
		if baseDir == "" {
			baseDir = filepath.Dir(sourceFile)
		}
		freshStatus, _, freshIssue := checkArtifactWithSourceHint(reviewFile, baseDir, sourceFile)
		if freshStatus != "PASS" {
			code := "INVALID_ARTIFACT_METADATA"
			summary := freshIssue
			fix := []string{"FIX_REGENERATE_ARTIFACT_ON_CURRENT_SOURCE"}
			switch {
			case strings.Contains(freshIssue, "source file not found"):
				code = "SOURCE_FILE_NOT_FOUND"
				summary = "Source file could not be read."
				fix = []string{"FIX_SOURCE_FILE_PATH"}
			case strings.Contains(freshIssue, "Source Digest"):
				code = "MISSING_SOURCE_DIGEST"
				summary = "Could not extract Source Digest from review file."
				fix = []string{"FIX_ADD_SOURCE_DIGEST", "FIX_REGENERATE_HEADER"}
			case strings.Contains(freshIssue, "Task ID") || strings.Contains(freshIssue, "Task Contract Digest") || strings.Contains(freshIssue, "Base Commit") || strings.Contains(freshIssue, "Implementation Files"):
				code = "MISSING_TASK_CONTRACT_METADATA"
				summary = freshIssue
				fix = []string{"FIX_ADD_TASK_CONTRACT_METADATA", "FIX_RERUN_DOD_RECHECK_ON_CURRENT_TASK"}
			case freshStatus == "STALE" && isTaskScopedArtifact(filepath.Base(reviewFile)):
				code = "TASK_CONTRACT_STALE"
				summary = freshIssue
				fix = []string{"FIX_RERUN_RECHECK_ON_CURRENT_TASK_CONTRACT"}
			case freshStatus == "STALE":
				code = "SOURCE_DIGEST_MISMATCH"
				summary = "Source Digest does not match current source file."
				fix = []string{"FIX_RERUN_REVIEW_ON_CURRENT_SOURCE", "FIX_UPDATE_SOURCE_DIGEST"}
			}
			log.Emit(w, log.Result{
				Tool:    gcToolName,
				Status:  "FAIL",
				Code:    code,
				Summary: summary,
			},
				slog.String("signal.source_status", freshStatus),
				slog.String("signal.source_issue", freshIssue),
				slog.Any("fix", fix),
			)
			return 1
		}
	}

	// Check 4: Sub-verdicts
	subCount, failCount, failLines := gcCheckSubVerdicts(content)
	if subCount > 0 && failCount > 0 {
		log.Emit(w, log.Result{
			Tool:    gcToolName,
			Status:  "FAIL",
			Code:    "SUB_VERDICT_FAILURES",
			Summary: fmt.Sprintf("%d sub-verdict(s) failed.", failCount),
		},
			slog.Int("signal.sub_verdicts_checked", subCount),
			slog.Int("signal.sub_verdicts_failed", failCount),
			slog.String("signal.failed_sub_verdicts", strings.Join(failLines, "; ")),
			slog.String("fix.1", "FIX_RESOLVE_SUB_VERDICTS"),
			slog.String("fix.2", "FIX_REGENERATE_REVIEW"),
		)
		return 1
	}

	// Check 5: Exit codes (dod-recheck only)
	nonzeroCmds := gcCheckExitCodes(content)
	if len(nonzeroCmds) > 0 {
		log.Emit(w, log.Result{
			Tool:    gcToolName,
			Status:  "FAIL",
			Code:    "NONZERO_EXIT_CODES",
			Summary: fmt.Sprintf("%d command(s) recorded non-zero exit codes.", len(nonzeroCmds)),
		},
			slog.Int("signal.nonzero_count", len(nonzeroCmds)),
			slog.String("signal.nonzero_details", strings.Join(nonzeroCmds, "; ")),
			slog.String("fix.1", "FIX_RESOLVE_NONZERO_EXIT_CODES"),
			slog.String("fix.2", "FIX_REGENERATE_REVIEW"),
		)
		return 1
	}

	log.Emit(w, log.Result{
		Tool:    gcToolName,
		Status:  "PASS",
		Code:    "ALL_CHECKS_PASSED",
		Summary: "All gate checks passed.",
	},
		slog.String("detail.overall_verdict", verdictValue),
		slog.Int("detail.sub_verdicts_checked", subCount),
	)
	return 0
}

func gcParseOverallVerdict(content string) string {
	m := gcOverallVerdictRe.FindStringSubmatch(content)
	if m == nil {
		return ""
	}
	return strings.TrimSpace(m[1])
}

func gcCheckSubVerdicts(content string) (subCount, failCount int, failLines []string) {
	skip := false
	for _, line := range strings.Split(content, "\n") {
		// Track DoD/QGate sections to exclude their table rows.
		if strings.HasPrefix(line, "## DoD Verification") || strings.HasPrefix(line, "## Quality Gate Verification") {
			skip = true
		} else if strings.HasPrefix(line, "## ") {
			skip = false
		}

		// List format: "- Key: PASS|FAIL|N/A" (applied to all lines regardless of skip)
		if !gcOverallVerdictPfx.MatchString(line) {
			if m := gcListVerdictRe.FindStringSubmatch(line); m != nil {
				subCount++
				if verdict := m[1]; verdict != "N/A" && verdict != "PASS" {
					failCount++
					failLines = append(failLines, line)
				}
			}
		}

		// Table format: "| N | Criterion | Verdict | Evidence |"
		// Exclude DoD Verification and Quality Gate Verification sections.
		if skip || !gcTableRowNumRe.MatchString(line) {
			continue
		}
		parts := strings.Split(line, "|")
		if len(parts) < 4 {
			continue
		}
		verdict := strings.TrimSpace(parts[3])
		if verdict == "Verdict" || strings.HasPrefix(verdict, "-") || verdict == "" {
			continue
		}
		if verdict != "PASS" && verdict != "FAIL" && !strings.HasPrefix(verdict, "N/A") {
			continue
		}
		subCount++
		if !strings.HasPrefix(verdict, "N/A") && verdict != "PASS" {
			failCount++
			criterion := strings.TrimSpace(parts[2])
			failLines = append(failLines, criterion+": "+verdict)
		}
	}
	return
}

func gcCheckExitCodes(content string) []string {
	lines := strings.Split(content, "\n")

	// Only run if ## DoD Verification exists (dod-recheck reports only).
	hasDod := false
	for _, l := range lines {
		if strings.HasPrefix(l, "## DoD Verification") {
			hasDod = true
			break
		}
	}
	if !hasDod {
		return nil
	}

	type section struct {
		header string
		prefix string
	}
	sections := []section{
		{"## DoD Verification", "DoD"},
		{"## Quality Gate Verification", "QGate"},
	}

	var nonzero []string
	for _, s := range sections {
		for _, line := range gcExtractSection(lines, s.header) {
			if !gcTableRowNumRe.MatchString(line) {
				continue
			}
			parts := strings.Split(line, "|")
			if len(parts) < 4 {
				continue
			}
			exitCodeStr := strings.TrimSpace(parts[3])
			n, err := strconv.Atoi(exitCodeStr)
			if err != nil || n == 0 {
				continue
			}
			cmd := strings.TrimSpace(parts[2])
			nonzero = append(nonzero, fmt.Sprintf("%s:%s:exit=%s", s.prefix, cmd, exitCodeStr))
		}
	}
	return nonzero
}

func gcExtractSection(lines []string, header string) []string {
	var result []string
	inSection := false
	for _, line := range lines {
		if strings.HasPrefix(line, header) {
			inSection = true
			continue
		}
		if inSection {
			if strings.HasPrefix(line, "## ") {
				break
			}
			result = append(result, line)
		}
	}
	return result
}
