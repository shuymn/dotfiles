package main

import (
	"context"
	"errors"
	"os"

	"github.com/shuymn/dotfiles/skills/tools/skit/cmd"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

func main() {
	app := cli.New("skit", "skill toolkit")
	app.Root.Add(
		cmd.FileScopeCheck(),
		cmd.FreshnessPreflight(),
		cmd.ArtifactFormatCheck(),
		cmd.RiskFormatCheck(),
		cmd.VerificationCmdCheck(),
		cmd.BundleValidateCheck(),
		cmd.DepGraphGen(),
		cmd.TempLifecycleCheck(),
		cmd.RiskDodCheck(),
		cmd.TraceComposeCheck(),
		cmd.AdversarialCoverageCheck(),
		cmd.SplitCheck(),
		cmd.DigestStamp(),
		cmd.StructuralCheck(),
		cmd.ReviewFinalize(),
		cmd.GateCheck(),
		cmd.BuildSkills(),
		cmd.ManifestRefresh(),
		cmd.MarkManaged(),
		cmd.Reconcile(),
		cmd.AuditCodex(),
	)

	if err := app.RunContext(context.Background(), os.Args[1:]); err != nil {
		var exitErr cli.ExitError
		if errors.As(err, &exitErr) {
			os.Exit(int(exitErr))
		}
		os.Exit(1)
	}
}
