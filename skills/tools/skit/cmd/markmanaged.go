package cmd

import (
	"context"
	"fmt"
	"io"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/managedskills"
)

const markManagedTool = "mark-managed"

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
	outcome := managedskills.RunMarkManaged(manifestPath, agentsSkills, marker, dryRun)
	log.Emit(w, outcome.Result, outcome.Attrs...)
	return outcome.ExitCode
}
