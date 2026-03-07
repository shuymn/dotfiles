package workflow

import (
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const toolName = "freshness-preflight"

var artifactGlobPatterns = []string{
	"*.review.md",
	"*.dod-recheck.md",
	"*.adversarial.md",
}

var (
	digestRe   = regexp.MustCompile(`(?i)Source Digest\*{0,2}\s*:\s*([a-f0-9]{64})`)
	artifactRe = regexp.MustCompile(`(?im)Source Artifact\*{0,2}\s*:\s*(.+?)\s*$`)
)

type checkEntry struct {
	Name  string `json:"name"`
	Issue string `json:"issue"`
}

// FreshnessPreflight returns the freshness-preflight subcommand.
func FreshnessPreflight() *cli.Command {
	c := cli.NewCommand("freshness-preflight", "Pre-flight digest freshness check for review/recheck artifacts")
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
	var skipList []checkEntry
	passed := 0

	for _, af := range artifactFiles {
		status, name, issue := checkArtifact(af, resolvedBase)
		switch status {
		case "STALE":
			staleList = append(staleList, checkEntry{Name: name, Issue: issue})
		case "SKIP":
			skipList = append(skipList, checkEntry{Name: name, Issue: issue})
		default:
			passed++
		}
	}

	total := len(artifactFiles)
	overall := "PASS"
	code := "ALL_ARTIFACTS_FRESH"
	summary := fmt.Sprintf("All %d artifact(s) are fresh.", passed)

	if len(staleList) > 0 {
		overall = "FAIL"
		code = "STALE_REVIEW_ARTIFACTS"
		summary = fmt.Sprintf("%d artifact(s) are stale (source changed after review).", len(staleList))
	}

	attrs := []slog.Attr{
		slog.Int("signal.total_artifacts", total),
		slog.Int("signal.passed", passed),
		slog.Int("signal.stale", len(staleList)),
		slog.Int("signal.skipped", len(skipList)),
	}

	if len(staleList) > 0 {
		attrs = append(attrs, slog.Any("stale", staleList))
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_RERUN_REVIEW_ON_CURRENT_SOURCE",
			"FIX_UPDATE_SOURCE_DIGEST_IN_ARTIFACT",
		}))
	}

	if len(skipList) > 0 {
		attrs = append(attrs, slog.Any("skip", skipList))
	}

	log.Emit(w, log.Result{
		Tool:    toolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(staleList) > 0 {
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
	return found
}

func extractMetadata(text string) (digest, artifactPath string) {
	if m := digestRe.FindStringSubmatch(text); m != nil {
		digest = strings.TrimSpace(m[1])
	}
	if m := artifactRe.FindStringSubmatch(text); m != nil {
		artifactPath = strings.TrimSpace(m[1])
	}
	return
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
		return "SKIP", name, fmt.Sprintf("cannot read artifact: %v", err)
	}

	storedDigest, sourceArtifact := extractMetadata(string(data))
	if storedDigest == "" {
		return "SKIP", name, "no Source Digest found in artifact"
	}
	if sourceArtifact == "" {
		return "SKIP", name, "no Source Artifact path found in artifact"
	}

	sourcePath := sourceArtifact
	if !filepath.IsAbs(sourcePath) {
		candidate := filepath.Join(baseDir, sourcePath)
		if _, err := os.Stat(candidate); os.IsNotExist(err) {
			candidate = filepath.Join(filepath.Dir(artifactPath), sourcePath)
		}
		sourcePath = candidate
	}

	if _, err := os.Stat(sourcePath); os.IsNotExist(err) {
		return "SKIP", name, fmt.Sprintf("source file not found: %s", sourceArtifact)
	}

	currentDigest, err := sha256File(sourcePath)
	if err != nil {
		return "SKIP", name, fmt.Sprintf("cannot read source file: %v", err)
	}

	if currentDigest != storedDigest {
		return "STALE", name, fmt.Sprintf(
			"digest mismatch: stored=%s... current=%s... (source: %s)",
			storedDigest[:12], currentDigest[:12], sourceArtifact,
		)
	}

	return "PASS", name, ""
}
