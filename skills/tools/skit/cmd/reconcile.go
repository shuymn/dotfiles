package cmd

import (
	"context"
	"fmt"
	"io"
	"os/exec"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/managedskills"
)

const reconcileTool = "reconcile"

// execCommandFn is exec.Command, replaceable in tests.
var execCommandFn = exec.Command

// Reconcile returns the reconcile subcommand.
func Reconcile() *cli.Command {
	c := cli.NewCommand(reconcileTool, "Remove stale managed skills while preserving external skills")
	c.EnableDryRun()
	var manifestPath, agentsSkills, marker, skillsCmd string
	c.StringVar(&manifestPath, "manifest", "", "", "Path to managed skills manifest (required)")
	c.StringVar(&agentsSkills, "agents-skills", "", "", "Path to ~/.agents/skills (required)")
	c.StringVar(&marker, "marker", "", ".dotfiles-managed", "Managed marker filename")
	c.StringVar(&skillsCmd, "skills-cmd", "", "", "Skills CLI command prefix, e.g. 'bunx --bun skills' (required)")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if manifestPath == "" || agentsSkills == "" || skillsCmd == "" {
			return fmt.Errorf("--manifest, --agents-skills, and --skills-cmd are required")
		}
		return exitCode(runReconcile(s.Stdout, s.Stderr, manifestPath, agentsSkills, marker, skillsCmd, s.DryRun))
	}
	return c
}

func runReconcile(w, stderr io.Writer, manifestPath, agentsSkills, marker, skillsCmd string, dryRun bool) int {
	outcome := managedskills.RunReconcile(managedskills.ReconcileOptions{
		ManifestPath: manifestPath,
		AgentsSkills: agentsSkills,
		Marker:       marker,
		SkillsCmd:    skillsCmd,
		DryRun:       dryRun,
		Stdout:       w,
		Stderr:       stderr,
		ExecCommand:  execCommandFn,
	})
	log.Emit(w, outcome.Result, outcome.Attrs...)
	return outcome.ExitCode
}
