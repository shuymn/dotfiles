package main

import (
	"os"

	"github.com/shuymn/dotfiles/skills/tools/skit/cmd"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

func main() {
	app := &cli.App{Name: "skit"}
	app.Register(cmd.FileScopeCheck())
	app.Register(cmd.FreshnessPreflight())
	app.Register(cmd.ArtifactFormatCheck())
	app.Register(cmd.RiskFormatCheck())
	app.Register(cmd.VerificationCmdCheck())
	app.Register(cmd.BundleValidateCheck())
	app.Register(cmd.DepGraphGen())
	app.Register(cmd.TempLifecycleCheck())
	app.Register(cmd.RiskDodCheck())
	app.Register(cmd.TraceComposeCheck())
	app.Register(cmd.AdversarialCoverageCheck())
	app.Register(cmd.SplitCheck())
	app.Register(cmd.DigestStamp())
	app.Register(cmd.StructuralCheck())
	app.Register(cmd.ReviewFinalize())
	app.Register(cmd.GateCheck())

	// scripts
	app.Register(cmd.BuildSkills())
	app.Register(cmd.ManifestRefresh())
	app.Register(cmd.MarkManaged())
	app.Register(cmd.Reconcile())
	app.Register(cmd.AuditCodex())

	os.Exit(app.Run(os.Args))
}
