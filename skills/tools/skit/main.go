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
	os.Exit(app.Run(os.Args))
}
