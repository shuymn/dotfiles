package workflow

import (
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"slices"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const toolName = "freshness-preflight"

var artifactGlobPatterns = []string{
	"*.review.md",
	"*.dod-recheck.md",
	"*.adversarial.md",
	"*.audit.md",
}

var (
	digestRe             = regexp.MustCompile(`(?i)Source Digest\*{0,2}\s*:\s*([a-f0-9]{64})`)
	artifactRe           = regexp.MustCompile(`(?im)Source Artifact\*{0,2}\s*:\s*(.+?)\s*$`)
	taskIDRe             = regexp.MustCompile(`(?im)Task ID\*{0,2}\s*:\s*(?:Task\s+)?0*([0-9]+)\s*$`)
	taskContractDigestRe = regexp.MustCompile(`(?im)Task Contract Digest\*{0,2}\s*:\s*([a-f0-9]{64})\s*$`)
	baseCommitRe         = regexp.MustCompile(`(?im)Base Commit\*{0,2}\s*:\s*([a-f0-9]{7,40})\s*$`)
)

type checkEntry struct {
	Name  string `json:"name"`
	Issue string `json:"issue"`
}

type artifactMetadata struct {
	SourceArtifact     string
	SourceDigest       string
	TaskID             string
	TaskContractDigest string
	BaseCommit         string
	ImplementationFiles []string
}

// FreshnessPreflight returns the freshness-preflight subcommand.
func FreshnessPreflight() *cli.Command {
	c := cli.NewCommand("freshness-preflight", "Pre-flight freshness check for review and task verification artifacts")
	var baseDir string
	var topicDir string
	c.StringVar(&baseDir, "base-dir", "", "", "Repository root for resolving relative source paths (default: topic_dir/../..)")
	c.StringArg(&topicDir, "topic-dir", "Topic directory containing review artifacts")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runFreshnessPreflight(s.Stdout, baseDir, topicDir))
	}
	return c
}

func runFreshnessPreflight(w io.Writer, baseDir, topicDir string) int {
	resolvedBase := baseDir

	info, err := os.Stat(topicDir)
	if err != nil || !info.IsDir() {
		log.Emit(w, log.Result{
			Tool:    toolName,
			Status:  "FAIL",
			Code:    "TOPIC_DIR_NOT_FOUND",
			Summary: fmt.Sprintf("Topic directory not found: %s", topicDir),
		},
			slog.String("fix.1", "FIX_TOPIC_DIR_PATH"),
		)
		return 1
	}

	if resolvedBase == "" {
		abs, err := filepath.Abs(topicDir)
		if err != nil {
			resolvedBase = filepath.Dir(filepath.Dir(topicDir))
		} else {
			resolvedBase = filepath.Dir(filepath.Dir(abs))
		}
	}

	artifactFiles := findArtifactFiles(topicDir)
	if len(artifactFiles) == 0 {
		log.Emit(w, log.Result{
			Tool:    toolName,
			Status:  "SKIP",
			Code:    "NO_REVIEW_ARTIFACTS",
			Summary: fmt.Sprintf("No review/recheck/adversarial artifacts found in %s.", topicDir),
		})
		return 0
	}

	var staleList []checkEntry
	var invalidList []checkEntry
	passed := 0

	for _, af := range artifactFiles {
		status, name, issue := checkArtifact(af, resolvedBase)
		switch status {
		case "STALE":
			staleList = append(staleList, checkEntry{Name: name, Issue: issue})
		case "INVALID":
			invalidList = append(invalidList, checkEntry{Name: name, Issue: issue})
		default:
			passed++
		}
	}

	total := len(artifactFiles)
	overall := "PASS"
	code := "ALL_ARTIFACTS_FRESH"
	summary := fmt.Sprintf("All %d artifact(s) are fresh.", passed)

	if len(staleList) > 0 || len(invalidList) > 0 {
		overall = "FAIL"
		code = "ARTIFACT_FRESHNESS_VIOLATIONS"
		summary = fmt.Sprintf("%d artifact(s) stale, %d artifact(s) invalid.", len(staleList), len(invalidList))
	}

	attrs := []slog.Attr{
		slog.Int("signal.total_artifacts", total),
		slog.Int("signal.passed", passed),
		slog.Int("signal.stale", len(staleList)),
		slog.Int("signal.invalid", len(invalidList)),
	}

	if len(staleList) > 0 {
		attrs = append(attrs, slog.Any("stale", staleList))
	}
	if len(invalidList) > 0 {
		attrs = append(attrs, slog.Any("invalid", invalidList))
	}
	if len(staleList) > 0 || len(invalidList) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_RERUN_ARTIFACT_ON_CURRENT_TASK_CONTRACT",
			"FIX_REGENERATE_MISSING_TASK_METADATA",
		}))
	}

	log.Emit(w, log.Result{
		Tool:    toolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(staleList) > 0 || len(invalidList) > 0 {
		return 1
	}
	return 0
}

func findArtifactFiles(topicDir string) []string {
	var found []string
	for _, pattern := range artifactGlobPatterns {
		matches, err := filepath.Glob(filepath.Join(topicDir, pattern))
		if err != nil {
			continue
		}
		found = append(found, matches...)
	}
	slices.Sort(found)
	return slices.Compact(found)
}

func extractMetadata(text string) artifactMetadata {
	meta := artifactMetadata{ImplementationFiles: parseImplementationFiles(text)}
	if m := digestRe.FindStringSubmatch(text); m != nil {
		meta.SourceDigest = strings.TrimSpace(m[1])
	}
	if m := artifactRe.FindStringSubmatch(text); m != nil {
		meta.SourceArtifact = strings.TrimSpace(m[1])
	}
	if m := taskIDRe.FindStringSubmatch(text); m != nil {
		meta.TaskID = strings.TrimSpace(m[1])
	}
	if m := taskContractDigestRe.FindStringSubmatch(text); m != nil {
		meta.TaskContractDigest = strings.TrimSpace(m[1])
	}
	if m := baseCommitRe.FindStringSubmatch(text); m != nil {
		meta.BaseCommit = strings.TrimSpace(m[1])
	}
	return meta
}

func sha256Bytes(data []byte) string {
	sum := sha256.Sum256(data)
	return fmt.Sprintf("%x", sum)
}

func sha256File(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return sha256Bytes(data), nil
}

func checkArtifact(artifactPath, baseDir string) (status, name, issue string) {
	name = filepath.Base(artifactPath)
	data, err := os.ReadFile(artifactPath)
	if err != nil {
		return "INVALID", name, fmt.Sprintf("cannot read artifact: %v", err)
	}

	meta := extractMetadata(string(data))
	if meta.SourceArtifact == "" {
		return "INVALID", name, "missing Source Artifact metadata"
	}

	sourcePath := meta.SourceArtifact
	if !filepath.IsAbs(sourcePath) {
		sourcePath = resolveExistingPath(
			filepath.Join(baseDir, sourcePath),
			filepath.Join(filepath.Dir(artifactPath), sourcePath),
		)
	}
	if _, err := os.Stat(sourcePath); err != nil {
		return "INVALID", name, fmt.Sprintf("source file not found: %s", meta.SourceArtifact)
	}

	if isTaskScopedArtifact(name) {
		status, issue = checkTaskScopedArtifact(name, sourcePath, artifactPath, meta)
		return status, name, issue
	}
	status, issue = checkWholeSourceArtifact(name, sourcePath, meta)
	return status, name, issue
}

func checkWholeSourceArtifact(name, sourcePath string, meta artifactMetadata) (status, issue string) {
	if meta.SourceDigest == "" {
		return "INVALID", "missing Source Digest metadata"
	}
	currentDigest, err := sha256File(sourcePath)
	if err != nil {
		return "INVALID", fmt.Sprintf("cannot read source file: %v", err)
	}
	if currentDigest != meta.SourceDigest {
		return "STALE", fmt.Sprintf(
			"source digest mismatch: stored=%s... current=%s...",
			meta.SourceDigest[:12], currentDigest[:12],
		)
	}
	return "PASS", ""
}

func checkTaskScopedArtifact(name, sourcePath, artifactPath string, meta artifactMetadata) (status, issue string) {
	if meta.TaskID == "" {
		return "INVALID", "missing Task ID metadata"
	}
	if meta.TaskContractDigest == "" {
		return "INVALID", "missing Task Contract Digest metadata"
	}
	taskID, err := strconv.Atoi(meta.TaskID)
	if err != nil {
		return "INVALID", fmt.Sprintf("invalid Task ID metadata: %s", meta.TaskID)
	}
	planData, err := os.ReadFile(sourcePath)
	if err != nil {
		return "INVALID", fmt.Sprintf("cannot read plan file: %v", err)
	}
	block := extractTaskBlock(string(planData), taskID)
	if block == "" {
		return "STALE", fmt.Sprintf("task %d no longer exists in source plan", taskID)
	}
	currentDigest := computeTaskContractDigest(block)
	if currentDigest != meta.TaskContractDigest {
		return "STALE", fmt.Sprintf(
			"task contract digest mismatch for Task %d: stored=%s... current=%s...",
			taskID, meta.TaskContractDigest[:12], currentDigest[:12],
		)
	}
	if meta.BaseCommit == "" {
		return "INVALID", "missing Base Commit metadata"
	}
	if len(meta.ImplementationFiles) == 0 {
		return "INVALID", "missing Implementation Files metadata"
	}

	repoRoot, err := gitRepoRoot(filepath.Dir(sourcePath))
	if err != nil {
		return "INVALID", fmt.Sprintf("cannot resolve git repo root: %v", err)
	}
	diffFiles, err := gitDiffNames(repoRoot, meta.BaseCommit)
	if err != nil {
		return "INVALID", fmt.Sprintf("cannot inspect git diff from %s: %v", meta.BaseCommit, err)
	}
	sourceRel, err := filepath.Rel(repoRoot, sourcePath)
	if err == nil {
		diffFiles = filterPaths(diffFiles, filepath.ToSlash(sourceRel))
	}
	diffFiles = filterPaths(diffFiles, filepath.ToSlash(meta.SourceArtifact))
	artifactRel, err := filepath.Rel(repoRoot, artifactPath)
	if err == nil {
		diffFiles = filterPaths(diffFiles, filepath.ToSlash(artifactRel))
	}

	expected := normalizeRepoPaths(meta.ImplementationFiles)
	actual := normalizeRepoPaths(diffFiles)
	if !slices.Equal(expected, actual) {
		return "STALE", fmt.Sprintf(
			"implementation file set drift from base %s: recorded=%s actual=%s",
			meta.BaseCommit,
			strings.Join(expected, ", "),
			strings.Join(actual, ", "),
		)
	}

	return "PASS", ""
}

func isTaskScopedArtifact(name string) bool {
	return strings.HasSuffix(name, ".dod-recheck.md") || strings.HasSuffix(name, ".adversarial.md")
}

func gitRepoRoot(dir string) (string, error) {
	cmd := exec.Command("git", "-C", dir, "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func gitDiffNames(repoRoot, baseCommit string) ([]string, error) {
	cmd := exec.Command("git", "-C", repoRoot, "diff", "--name-only", baseCommit)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	var files []string
	for _, line := range strings.Split(string(out), "\n") {
		if trimmed := strings.TrimSpace(line); trimmed != "" {
			files = append(files, trimmed)
		}
	}
	return files, nil
}

func normalizeRepoPaths(files []string) []string {
	if len(files) == 0 {
		return nil
	}
	uniq := make(map[string]bool)
	for _, file := range files {
		normalized := filepath.ToSlash(strings.TrimSpace(file))
		if normalized != "" {
			uniq[normalized] = true
		}
	}
	var result []string
	for file := range uniq {
		result = append(result, file)
	}
	slices.Sort(result)
	return result
}

func filterPaths(files []string, ignore string) []string {
	if ignore == "" {
		return files
	}
	var result []string
	for _, file := range files {
		if filepath.ToSlash(strings.TrimSpace(file)) != ignore {
			result = append(result, file)
		}
	}
	return result
}
