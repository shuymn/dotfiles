package cmd

import (
	"context"
	"fmt"
	"io"
	"os"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/managedskills"
)

const auditCodexTool = "audit-codex"

// removeAllFn is os.RemoveAll, replaceable in tests.
var removeAllFn = os.RemoveAll

// AuditCodex returns the audit-codex subcommand.
func AuditCodex() *cli.Command {
	c := cli.NewCommand(auditCodexTool, "Audit ~/.codex/skills and prune duplicates found in ~/.agents/skills")
	c.EnableDryRun()
	var manifestPath, agentsSkills, codexSkills, marker string
	var pruneDuplicates bool
	c.StringVar(&manifestPath, "manifest", "", "", "Path to managed skills manifest (required)")
	c.StringVar(&agentsSkills, "agents-skills", "", "", "Path to ~/.agents/skills (required)")
	c.StringVar(&codexSkills, "codex-skills", "", "", "Path to ~/.codex/skills (required)")
	c.StringVar(&marker, "marker", "", ".dotfiles-managed", "Managed marker filename")
	c.BoolVar(&pruneDuplicates, "prune-duplicates", "", false, "Remove entries from ~/.codex/skills when the same entry exists in ~/.agents/skills")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if manifestPath == "" || agentsSkills == "" || codexSkills == "" {
			return fmt.Errorf("--manifest, --agents-skills, and --codex-skills are required")
		}
		return exitCode(runAuditCodex(s.Stdout, manifestPath, agentsSkills, codexSkills, marker, pruneDuplicates, s.DryRun))
	}
	return c
}

func runAuditCodex(w io.Writer, manifestPath, agentsSkills, codexSkills, marker string, pruneDuplicates, dryRun bool) int {
	outcome := managedskills.RunAuditCodex(manifestPath, agentsSkills, codexSkills, marker, pruneDuplicates, dryRun, removeAllFn)
	log.Emit(w, outcome.Result, outcome.Attrs...)
	return outcome.ExitCode
}
