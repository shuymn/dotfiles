package cli

import (
	"context"
	"io"
	"os"
)

// App owns the command tree and dispatch.
type App struct {
	Name    string
	Summary string
	Root    *Command
	Stdin   io.Reader
	Stdout  io.Writer
	Stderr  io.Writer
}

// New constructs a new CLI application.
func New(name, summary string) *App {
	root := &Command{
		Name:        name,
		Summary:     summary,
		Description: summary,
		flagByName:  make(map[string]FlagHelp),
		flagByShort: make(map[string]FlagHelp),
	}
	return &App{
		Name:    name,
		Summary: summary,
		Root:    root,
		Stdin:   os.Stdin,
		Stdout:  os.Stdout,
		Stderr:  os.Stderr,
	}
}

// Run dispatches using a background context.
func (a *App) Run(args []string) error {
	return a.RunContext(context.Background(), args)
}

// Command returns a descendant command by path.
func (a *App) Command(path ...string) *Command {
	cur := a.Root
	for _, name := range path {
		cur = cur.Command(name)
		if cur == nil {
			return nil
		}
	}
	return cur
}

func (a *App) stdin() io.Reader {
	if a.Stdin != nil {
		return a.Stdin
	}
	return os.Stdin
}

func (a *App) stdout() io.Writer {
	if a.Stdout != nil {
		return a.Stdout
	}
	return os.Stdout
}

func (a *App) stderr() io.Writer {
	if a.Stderr != nil {
		return a.Stderr
	}
	return os.Stderr
}
