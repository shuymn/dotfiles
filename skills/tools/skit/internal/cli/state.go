package cli

import (
	"fmt"
	"io"
	"strings"
)

// ExitError carries an explicit process exit code.
type ExitError int

func (e ExitError) Error() string {
	return fmt.Sprintf("exit status %d", int(e))
}

// FlagHelp contains rendered help metadata for a single flag.
type FlagHelp struct {
	Name    string
	Short   string
	Usage   string
	Default string
	IsBool  bool
}

// ArgHelp contains rendered help metadata for a single positional argument.
type ArgHelp struct {
	Name     string
	Usage    string
	Optional bool
	Rest     bool
}

// StringSlice is a repeated string flag helper.
type StringSlice []string

func (s *StringSlice) String() string {
	if s == nil {
		return ""
	}
	return strings.Join(*s, ",")
}

func (s *StringSlice) Set(value string) error {
	*s = append(*s, value)
	return nil
}

func (s *StringSlice) Get() any {
	if s == nil {
		return []string(nil)
	}
	return append([]string(nil), (*s)...)
}

// State is passed to a command run function after flag parsing.
type State struct {
	AppName string
	Command *Command
	Path    []string
	DryRun  bool
	Stdin   io.Reader
	Stdout  io.Writer
	Stderr  io.Writer
}
