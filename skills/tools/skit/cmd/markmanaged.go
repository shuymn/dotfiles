package cmd

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

const markManagedTool = "mark-managed"
const markerContent = "managed-by-dotfiles\n"

// MarkManaged returns the mark-managed subcommand.
func MarkManaged() *cli.Command {
	c := cli.NewCommand(markManagedTool, "Mark installed skills as managed by dotfiles")
	c.EnableDryRun()
	var manifestPath, agentsSkills, marker string
	c.StringVar(&manifestPath, "manifest", "", "", "Path to managed skills manifest (required)")
	c.StringVar(&agentsSkills, "agents-skills", "", "", "Path to ~/.agents/skills (required)")
	c.StringVar(&marker, "marker", "", ".dotfiles-managed", "Managed marker filename")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if manifestPath == "" || agentsSkills == "" {
			return fmt.Errorf("--manifest and --agents-skills are required")
		}
		return exitCode(runMarkManaged(s.Stdout, manifestPath, agentsSkills, marker, s.DryRun))
	}
	return c
}

func runMarkManaged(w io.Writer, manifestPath, agentsSkills, marker string, dryRun bool) int {
	resolvedManifest := pathutil.ExpandAndAbs(manifestPath)
	resolvedAgentsSkills := pathutil.ExpandAndAbs(agentsSkills)

	m, err := manifest.Load(resolvedManifest)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    markManagedTool,
			Status:  "FAIL",
			Code:    "MANIFEST_ERROR",
			Summary: fmt.Sprintf("Failed to load manifest: %v", err),
		})
		return 1
	}

	if len(m.Skills) == 0 {
		log.Emit(w, log.Result{
			Tool:    markManagedTool,
			Status:  "PASS",
			Code:    "NOTHING_TO_MARK",
			Summary: "managed_skills=0 (nothing to mark)",
		})
		return 0
	}

	var missing []string
	marked := 0

	for _, skill := range m.Skills {
		markerPath := filepath.Join(resolvedAgentsSkills, skill, marker)
		if dryRun {
			if info, err := os.Stat(filepath.Dir(markerPath)); err != nil || !info.IsDir() {
				missing = append(missing, skill)
				continue
			}
			marked++
			continue
		}
		if err := os.WriteFile(markerPath, []byte(markerContent), 0644); err != nil {
			missing = append(missing, skill)
			continue
		}
		marked++
	}

	if len(missing) > 1 {
		sort.Strings(missing)
	}

	attrs := []slog.Attr{
		slog.Int("signal.marked", marked),
		slog.Int("signal.missing", len(missing)),
	}
	if len(missing) > 0 {
		attrs = append(attrs, slog.String("signal.missing_names", strings.Join(missing, ",")))
	}
	if dryRun {
		attrs = append(attrs, slog.Bool("signal.dry_run", true))
	}

	log.Emit(w, log.Result{
		Tool:    markManagedTool,
		Status:  "PASS",
		Code:    "MARK_COMPLETE",
		Summary: fmt.Sprintf("marked=%d missing=%d", marked, len(missing)),
	}, attrs...)

	return 0
}
