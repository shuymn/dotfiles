package cli

import (
	"fmt"
	"io"
	"text/tabwriter"
)

func (a *App) printUsage(w io.Writer, cmd *Command) {
	if cmd == nil {
		cmd = a.Root
	}

	usageSuffix := "<command> [flags]"
	if len(cmd.children) == 0 {
		usageSuffix = "[flags]"
		if positional := cmd.positionalUsage(); positional != "" {
			usageSuffix += " " + positional
		}
	}

	fmt.Fprintf(w, "Usage: %s %s\n", cmd.displayPath(), usageSuffix)
	if cmd.summary() != "" {
		fmt.Fprintf(w, "\n%s\n", cmd.summary())
	}

	if len(cmd.children) > 0 {
		fmt.Fprintln(w, "\nCommands:")
		tw := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
		for _, child := range cmd.children {
			fmt.Fprintf(tw, "  %s\t%s\n", child.Name, child.summary())
		}
		fmt.Fprintln(tw, "  help\tShow help for a command")
		_ = tw.Flush()
	}

	flags := cmd.helpFlags()
	if len(flags) > 0 {
		fmt.Fprintln(w, "\nFlags:")
		tw := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
		for _, info := range flags {
			fmt.Fprintf(tw, "  %s\t%s\n", renderFlagLabel(info), renderFlagUsage(info))
		}
		_ = tw.Flush()
	}

	args := cmd.helpArgs()
	if len(args) > 0 {
		fmt.Fprintln(w, "\nArguments:")
		tw := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
		for _, info := range args {
			fmt.Fprintf(tw, "  %s\t%s\n", renderArgLabel(info), info.Usage)
		}
		_ = tw.Flush()
	}
}

func renderFlagLabel(info FlagHelp) string {
	label := "--" + info.Name
	if info.Short != "" {
		label += ", -" + info.Short
	}
	if !info.IsBool {
		label += " <value>"
	}
	return label
}

func renderFlagUsage(info FlagHelp) string {
	usage := info.Usage
	if info.Default == "" || info.Default == "false" {
		return usage
	}
	return fmt.Sprintf("%s (default: %s)", usage, info.Default)
}

func renderArgLabel(info ArgHelp) string {
	switch {
	case info.Rest:
		return "[" + info.Name + "...]"
	case info.Optional:
		return "[" + info.Name + "]"
	default:
		return "<" + info.Name + ">"
	}
}
