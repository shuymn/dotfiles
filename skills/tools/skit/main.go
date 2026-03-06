package main

import (
	"os"

	"skit/cmd"
	"skit/internal/cli"
)

func main() {
	app := &cli.App{Name: "skit"}
	app.Register(cmd.FreshnessPreflight())
	app.Register(cmd.ArtifactFormatCheck())
	app.Register(cmd.RiskFormatCheck())
	os.Exit(app.Run(os.Args))
}
