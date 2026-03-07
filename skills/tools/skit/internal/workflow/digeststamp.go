package workflow

import (
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"log/slog"
	"os"
	"time"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

const dsToolName = "digest-stamp"

var dsValidModes = map[string]bool{
	"design-review":      true,
	"plan-review":        true,
	"dod-recheck":        true,
	"adversarial-verify": true,
}

// DsStampResult holds the computed stamp fields.
type DsStampResult struct {
	Mode           string
	SourceArtifact string
	SourceDigest   string
	ReviewedAt     string
	Isolation      string
}

// DsGenerateStamp computes the digest stamp for a given mode and source file.
func DsGenerateStamp(mode, sourceFile string) (*DsStampResult, error) {
	if !dsValidModes[mode] {
		return nil, fmt.Errorf("invalid mode: %s", mode)
	}

	data, err := os.ReadFile(sourceFile)
	if err != nil {
		return nil, fmt.Errorf("source file not found: %s", sourceFile)
	}

	digest := fmt.Sprintf("%x", sha256.Sum256(data))
	displayPath := pathutil.DisplayPath(sourceFile)

	return &DsStampResult{
		Mode:           mode,
		SourceArtifact: displayPath,
		SourceDigest:   digest,
		ReviewedAt:     time.Now().UTC().Format("2006-01-02T15:04:05Z"),
		Isolation:      "sub-agent (fork_context=false)",
	}, nil
}

// RenderMarkdown returns the stamp as markdown bullet lines.
func (s *DsStampResult) RenderMarkdown() string {
	return fmt.Sprintf(
		"- **Mode**: %s\n- **Source Artifact**: %s\n- **Source Digest**: %s\n- **Reviewed At**: %s\n- **Isolation**: %s",
		s.Mode, s.SourceArtifact, s.SourceDigest, s.ReviewedAt, s.Isolation,
	)
}

// DigestStamp returns the digest-stamp subcommand.
func DigestStamp() *cli.Command {
	c := cli.NewCommand("digest-stamp", "Generate review header metadata (digest + timestamp)")
	var mode, sourceFile string
	c.StringArg(&mode, "mode", "Header mode to generate")
	c.StringArg(&sourceFile, "source-file", "Source artifact to hash")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runDigestStamp(s.Stdout, mode, sourceFile))
	}
	return c
}

func runDigestStamp(w io.Writer, mode, sourceFile string) int {
	if !dsValidModes[mode] {
		log.Emit(w, log.Result{
			Tool:    dsToolName,
			Status:  "FAIL",
			Code:    "INVALID_MODE",
			Summary: fmt.Sprintf("Invalid mode: %s. Use one of: design-review, plan-review, dod-recheck, adversarial-verify.", mode),
		})
		return 1
	}

	stamp, err := DsGenerateStamp(mode, sourceFile)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    dsToolName,
			Status:  "FAIL",
			Code:    "SOURCE_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Source file not found: %s.", sourceFile),
		})
		return 1
	}

	log.Emit(w, log.Result{
		Tool:    dsToolName,
		Status:  "PASS",
		Code:    "STAMP_GENERATED",
		Summary: "Digest stamp generated.",
	},
		slog.String("mode", stamp.Mode),
		slog.String("source_artifact", stamp.SourceArtifact),
		slog.String("source_digest", stamp.SourceDigest),
		slog.String("reviewed_at", stamp.ReviewedAt),
		slog.String("isolation", stamp.Isolation),
		slog.String("markdown", stamp.RenderMarkdown()),
	)
	return 0
}
