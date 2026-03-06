package main

import (
	"os"

	"skit/cmd"
	"skit/internal/cli"
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
	os.Exit(app.Run(os.Args))
}
