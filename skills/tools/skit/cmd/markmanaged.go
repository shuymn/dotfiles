package cmd

import (
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"skit/internal/cli"
	skitlog "skit/internal/log"
	"skit/internal/manifest"
	"skit/internal/pathutil"
)

const markManagedTool = "mark-managed"
const markerContent = "managed-by-dotfiles\n"

// MarkManaged returns the mark-managed subcommand.
func MarkManaged() *cli.Command {
	return &cli.Command{
		Name:        markManagedTool,
		Description: "Mark installed skills as managed by dotfiles",
		Run: func(args []string) int {
			return runMarkManaged(os.Stdout, args)
		},
	}
}

func runMarkManaged(w io.Writer, args []string) int {
	fs := flag.NewFlagSet(markManagedTool, flag.ContinueOnError)
	manifestPath := fs.String("manifest", "", "Path to managed skills manifest (required)")
	agentsSkills := fs.String("agents-skills", "", "Path to ~/.agents/skills (required)")
	marker := fs.String("marker", ".dotfiles-managed", "Managed marker filename")

	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 1
	}

	if *manifestPath == "" || *agentsSkills == "" {
		fmt.Fprintln(os.Stderr, "usage: skit mark-managed --manifest <path> --agents-skills <path> [--marker <name>]")
		return 1
	}

	resolvedManifest := pathutil.ExpandAndAbs(*manifestPath)
	resolvedAgentsSkills := pathutil.ExpandAndAbs(*agentsSkills)

	m, err := manifest.Load(resolvedManifest)
	if err != nil {
		skitlog.Emit(w, skitlog.Result{
			Tool:    markManagedTool,
			Status:  "FAIL",
			Code:    "MANIFEST_ERROR",
			Summary: fmt.Sprintf("Failed to load manifest: %v", err),
		})
		return 1
	}

	if len(m.Skills) == 0 {
		skitlog.Emit(w, skitlog.Result{
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
		markerPath := filepath.Join(resolvedAgentsSkills, skill, *marker)
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

	skitlog.Emit(w, skitlog.Result{
		Tool:    markManagedTool,
		Status:  "PASS",
		Code:    "MARK_COMPLETE",
		Summary: fmt.Sprintf("marked=%d missing=%d", marked, len(missing)),
	}, attrs...)

	return 0
}
