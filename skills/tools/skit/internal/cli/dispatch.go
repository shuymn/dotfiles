package cli

import (
	"context"
	"errors"
	"fmt"
)

// RunContext resolves the command tree, parses flags, validates inputs, and runs the target command.
func (a *App) RunContext(ctx context.Context, args []string) error {
	if len(args) == 0 {
		a.emitError(nil, "NO_SUBCOMMAND", "no subcommand specified")
		return ExitError(1)
	}

	if args[0] == "help" {
		return a.runHelp(args[1:])
	}
	if isHelpToken(args[0]) {
		a.printUsage(a.stdout(), a.Root)
		return nil
	}

	cmd, remaining := a.selectCommand(args)
	if cmd == nil {
		a.emitError(nil, "NO_SUBCOMMAND", "no subcommand specified")
		return ExitError(1)
	}

	if containsHelpArg(remaining) {
		a.printUsage(a.stdout(), cmd)
		return nil
	}

	if cmd.Run == nil && len(cmd.children) > 0 {
		if len(remaining) == 0 || isFlagLike(remaining[0]) {
			a.emitError(cmd, "NO_SUBCOMMAND", fmt.Sprintf("no subcommand specified for %s", cmd.displayPath()))
		} else {
			a.emitError(cmd, "UNKNOWN_SUBCOMMAND", fmt.Sprintf("unknown subcommand: %s", remaining[0]))
		}
		return ExitError(1)
	}

	if len(remaining) > 0 && cmd == a.Root && !isFlagLike(remaining[0]) {
		a.emitError(cmd, "UNKNOWN_SUBCOMMAND", fmt.Sprintf("unknown subcommand: %s", remaining[0]))
		return ExitError(1)
	}

	if cmd.Run == nil {
		a.emitError(cmd, "MISSING_COMMAND_RUNNER", fmt.Sprintf("command has no runnable action: %s", cmd.displayPath()))
		return ExitError(1)
	}

	fs := cmd.newFlagSet()
	if err := fs.Parse(cmd.normalizeArgs(remaining)); err != nil {
		a.emitError(cmd, "FLAG_PARSE_ERROR", err.Error())
		return ExitError(1)
	}
	if err := validateInputs(fs); err != nil {
		a.emitError(cmd, "INPUT_VALIDATION_ERROR", err.Error())
		return ExitError(1)
	}
	if err := cmd.bindArgs(fs.Args()); err != nil {
		var fwErr *frameworkError
		if errors.As(err, &fwErr) {
			a.emitError(cmd, fwErr.code, fwErr.summary)
			return ExitError(1)
		}
		a.emitError(cmd, "ARGUMENT_BIND_ERROR", err.Error())
		return ExitError(1)
	}

	state := &State{
		AppName: a.Name,
		Command: cmd,
		Path:    cmd.pathSegments(),
		DryRun:  cmd.dryRun != nil && *cmd.dryRun,
		Stdin:   a.stdin(),
		Stdout:  a.stdout(),
		Stderr:  a.stderr(),
	}

	err := cmd.Run(ctx, state)
	if err == nil {
		return nil
	}

	var exitErr ExitError
	if errors.As(err, &exitErr) {
		return exitErr
	}

	a.emitError(cmd, "COMMAND_ERROR", err.Error())
	return ExitError(1)
}

func (a *App) runHelp(args []string) error {
	target := a.Root
	for _, arg := range args {
		next := target.Command(arg)
		if next == nil {
			a.emitError(target, "UNKNOWN_SUBCOMMAND", fmt.Sprintf("unknown subcommand: %s", arg))
			return ExitError(1)
		}
		target = next
	}

	a.printUsage(a.stdout(), target)
	return nil
}

func (a *App) selectCommand(args []string) (*Command, []string) {
	current := a.Root
	index := 0
	for index < len(args) {
		arg := args[index]
		if isFlagLike(arg) || arg == "help" {
			break
		}

		child := current.Command(arg)
		if child == nil {
			break
		}

		current = child
		index++
	}

	return current, args[index:]
}
