package cli

import (
	"fmt"
	"io"
	"os"
)

// Command represents a subcommand.
type Command struct {
	Name        string
	Description string
	Run         func(args []string) int // returns exit code
}

// App manages the CLI application.
type App struct {
	Name     string
	Commands []*Command
}

// Register adds a subcommand to the app.
func (a *App) Register(cmd *Command) {
	a.Commands = append(a.Commands, cmd)
}

// Run dispatches to the appropriate subcommand and returns an exit code.
// args is expected to be os.Args (program name at index 0).
func (a *App) Run(args []string) int {
	if len(args) < 2 {
		a.printUsage(os.Stderr)
		return 1
	}

	sub := args[1]
	if sub == "--help" || sub == "-h" {
		a.printUsage(os.Stdout)
		return 0
	}

	for _, cmd := range a.Commands {
		if cmd.Name == sub {
			return cmd.Run(args[2:])
		}
	}

	fmt.Fprintf(os.Stderr, "%s: unknown subcommand %q\n", a.Name, sub)
	a.printUsage(os.Stderr)
	return 1
}

func (a *App) printUsage(w io.Writer) {
	fmt.Fprintf(w, "Usage: %s <subcommand> [options]\n\nSubcommands:\n", a.Name)
	for _, cmd := range a.Commands {
		fmt.Fprintf(w, "  %-24s %s\n", cmd.Name, cmd.Description)
	}
}
