package cli

import (
	"context"
	"encoding"
	"flag"
	"fmt"
	"io"
	"sort"
	"strings"
)

type flagBinder struct {
	help  FlagHelp
	apply func(fs *flag.FlagSet)
}

type argKind int

const (
	requiredArg argKind = iota
	optionalArg
	restArg
)

type argBinder struct {
	help  ArgHelp
	kind  argKind
	bind  func([]string)
	reset func()
}

// Command is a CLI command node.
type Command struct {
	Name        string
	Summary     string
	Description string
	Run         func(ctx context.Context, s *State) error

	parent      *Command
	children    []*Command
	flags       []flagBinder
	args        []argBinder
	flagByName  map[string]FlagHelp
	flagByShort map[string]FlagHelp
	dryRun      *bool
}

// NewCommand constructs a command.
func NewCommand(name, summary string) *Command {
	return &Command{
		Name:        name,
		Summary:     summary,
		Description: summary,
		flagByName:  make(map[string]FlagHelp),
		flagByShort: make(map[string]FlagHelp),
	}
}

// Add appends child commands.
func (c *Command) Add(children ...*Command) {
	for _, child := range children {
		if child == nil {
			continue
		}
		child.parent = c
		c.children = append(c.children, child)
	}
}

// Command returns a direct child by name.
func (c *Command) Command(name string) *Command {
	for _, child := range c.children {
		if child.Name == name {
			return child
		}
	}
	return nil
}

// StringVar registers a string flag.
func (c *Command) StringVar(p *string, name, short, value, usage string) {
	c.addFlag(name, short, usage, value, false, func(fs *flag.FlagSet) {
		fs.StringVar(p, name, value, usage)
	})
}

// BoolVar registers a bool flag.
func (c *Command) BoolVar(p *bool, name, short string, value bool, usage string) {
	c.addFlag(name, short, usage, fmt.Sprintf("%t", value), true, func(fs *flag.FlagSet) {
		fs.BoolVar(p, name, value, usage)
	})
}

// IntVar registers an int flag.
func (c *Command) IntVar(p *int, name, short string, value int, usage string) {
	c.addFlag(name, short, usage, fmt.Sprintf("%d", value), false, func(fs *flag.FlagSet) {
		fs.IntVar(p, name, value, usage)
	})
}

// Var registers a custom flag.Value.
func (c *Command) Var(value flag.Value, name, short, usage string) {
	isBool := false
	if b, ok := value.(interface{ IsBoolFlag() bool }); ok {
		isBool = b.IsBoolFlag()
	}
	defaultValue := value.String()
	c.addFlag(name, short, usage, defaultValue, isBool, func(fs *flag.FlagSet) {
		fs.Var(value, name, usage)
	})
}

// TextVar registers a text unmarshaler flag.
func (c *Command) TextVar(p encoding.TextUnmarshaler, name, short string, value encoding.TextMarshaler, usage string) {
	defaultValue := ""
	if value != nil {
		data, err := value.MarshalText()
		if err == nil {
			defaultValue = string(data)
		}
	}
	c.addFlag(name, short, usage, defaultValue, false, func(fs *flag.FlagSet) {
		fs.TextVar(p, name, value, usage)
	})
}

// Path registers a path-like string flag.
func (c *Command) Path(p *string, name, short, value, usage string) {
	c.StringVar(p, name, short, value, usage)
}

// StringArg registers a required positional string argument.
func (c *Command) StringArg(p *string, name, usage string) {
	c.addArg(argBinder{
		help: ArgHelp{Name: name, Usage: usage},
		kind: requiredArg,
		bind: func(values []string) {
			if len(values) > 0 {
				*p = values[0]
			}
		},
		reset: func() {
			*p = ""
		},
	})
}

// OptionalStringArg registers an optional positional string argument.
func (c *Command) OptionalStringArg(p *string, name, usage string) {
	c.addArg(argBinder{
		help: ArgHelp{Name: name, Usage: usage, Optional: true},
		kind: optionalArg,
		bind: func(values []string) {
			if len(values) > 0 {
				*p = values[0]
			}
		},
		reset: func() {
			*p = ""
		},
	})
}

// StringArgs registers a variadic positional string argument.
func (c *Command) StringArgs(p *[]string, name, usage string) {
	c.addArg(argBinder{
		help: ArgHelp{Name: name, Usage: usage, Optional: true, Rest: true},
		kind: restArg,
		bind: func(values []string) {
			*p = append((*p)[:0], values...)
		},
		reset: func() {
			*p = nil
		},
	})
}

// EnableDryRun adds a --dry-run flag and copies the parsed value into State.DryRun.
func (c *Command) EnableDryRun() {
	if c.dryRun != nil {
		return
	}

	var dryRun bool
	c.dryRun = &dryRun
	c.BoolVar(&dryRun, "dry-run", "", false, "Preview changes without writing files")
}

func (c *Command) addFlag(name, short, usage, defaultValue string, isBool bool, apply func(fs *flag.FlagSet)) {
	info := FlagHelp{
		Name:    name,
		Short:   short,
		Usage:   usage,
		Default: defaultValue,
		IsBool:  isBool,
	}

	c.flags = append(c.flags, flagBinder{help: info, apply: apply})
	c.flagByName[name] = info
	if short != "" {
		c.flagByShort[short] = info
	}
}

func (c *Command) addArg(arg argBinder) {
	switch arg.kind {
	case requiredArg:
		for _, existing := range c.args {
			if existing.kind != requiredArg {
				panic(fmt.Sprintf("cli: required positional %q must be declared before optional/rest args", arg.help.Name))
			}
		}
	case optionalArg:
		for _, existing := range c.args {
			if existing.kind == restArg {
				panic(fmt.Sprintf("cli: optional positional %q must be declared before rest args", arg.help.Name))
			}
		}
	case restArg:
		for _, existing := range c.args {
			if existing.kind == restArg {
				panic(fmt.Sprintf("cli: rest positional %q already declared", existing.help.Name))
			}
		}
	}
	c.args = append(c.args, arg)
}

func (c *Command) newFlagSet() *flag.FlagSet {
	fs := flag.NewFlagSet(c.Name, flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	fs.Usage = func() {}
	for _, binder := range c.flags {
		binder.apply(fs)
	}
	return fs
}

func (c *Command) helpFlags() []FlagHelp {
	flags := make([]FlagHelp, 0, len(c.flags)+1)
	for _, binder := range c.flags {
		flags = append(flags, binder.help)
	}
	flags = append(flags, FlagHelp{
		Name:   "help",
		Short:  "h",
		Usage:  "Show help",
		IsBool: true,
	})

	sort.SliceStable(flags, func(i, j int) bool {
		return flags[i].Name < flags[j].Name
	})
	return flags
}

func (c *Command) helpArgs() []ArgHelp {
	args := make([]ArgHelp, 0, len(c.args))
	for _, binder := range c.args {
		args = append(args, binder.help)
	}
	return args
}

func (c *Command) summary() string {
	if c.Summary != "" {
		return c.Summary
	}
	return c.Description
}

func (c *Command) pathSegments() []string {
	var reversed []string
	for cur := c; cur != nil && cur.parent != nil; cur = cur.parent {
		reversed = append(reversed, cur.Name)
	}

	segments := make([]string, len(reversed))
	for i := range reversed {
		segments[i] = reversed[len(reversed)-1-i]
	}
	return segments
}

func (c *Command) displayPath() string {
	root := c
	for root.parent != nil {
		root = root.parent
	}

	parts := []string{root.Name}
	parts = append(parts, c.pathSegments()...)
	return strings.Join(parts, " ")
}

func (c *Command) positionalUsage() string {
	if len(c.args) == 0 {
		return ""
	}
	parts := make([]string, 0, len(c.args))
	for _, arg := range c.args {
		switch arg.kind {
		case requiredArg:
			parts = append(parts, "<"+arg.help.Name+">")
		case optionalArg:
			parts = append(parts, "["+arg.help.Name+"]")
		case restArg:
			parts = append(parts, "["+arg.help.Name+"...]")
		}
	}
	return strings.Join(parts, " ")
}

func (c *Command) resetArgs() {
	for _, binder := range c.args {
		if binder.reset != nil {
			binder.reset()
		}
	}
}

func (c *Command) bindArgs(values []string) error {
	c.resetArgs()

	remaining := append([]string(nil), values...)
	for _, binder := range c.args {
		switch binder.kind {
		case requiredArg:
			if len(remaining) == 0 {
				return &frameworkError{
					code:    "MISSING_REQUIRED_ARGUMENT",
					summary: fmt.Sprintf("missing required argument: %s", binder.help.Name),
				}
			}
			binder.bind(remaining[:1])
			remaining = remaining[1:]
		case optionalArg:
			if len(remaining) == 0 {
				continue
			}
			binder.bind(remaining[:1])
			remaining = remaining[1:]
		case restArg:
			binder.bind(remaining)
			remaining = nil
		}
	}

	if len(remaining) > 0 {
		return &frameworkError{
			code:    "TOO_MANY_ARGUMENTS",
			summary: fmt.Sprintf("too many arguments: %s", strings.Join(remaining, " ")),
		}
	}
	return nil
}

func (c *Command) normalizeArgs(args []string) []string {
	var flags []string
	var positional []string
	afterTerminator := false

	for i := 0; i < len(args); i++ {
		arg := args[i]
		if afterTerminator {
			positional = append(positional, arg)
			continue
		}

		if arg == "--" {
			afterTerminator = true
			continue
		}

		if tokens, consumed, ok := c.consumeFlag(args, i); ok {
			flags = append(flags, tokens...)
			i += consumed - 1
			continue
		}

		positional = append(positional, arg)
	}

	normalized := append([]string(nil), flags...)
	if afterTerminator {
		normalized = append(normalized, "--")
	}
	normalized = append(normalized, positional...)
	return normalized
}

func (c *Command) consumeFlag(args []string, index int) ([]string, int, bool) {
	arg := args[index]
	if !isFlagLike(arg) || arg == "-" {
		return nil, 0, false
	}

	if isHelpToken(arg) {
		return []string{arg}, 1, true
	}

	if strings.HasPrefix(arg, "--no-") {
		name := strings.TrimPrefix(arg, "--no-")
		if info, ok := c.flagByName[name]; ok && info.IsBool {
			return []string{"-" + info.Name + "=false"}, 1, true
		}
		return []string{arg}, 1, true
	}

	if strings.HasPrefix(arg, "--") {
		name, value, hasValue := splitFlagToken(strings.TrimPrefix(arg, "--"))
		if info, ok := c.flagByName[name]; ok {
			token := "-" + info.Name
			if hasValue {
				return []string{token + "=" + value}, 1, true
			}
			if info.IsBool {
				return []string{token}, 1, true
			}
			if index+1 < len(args) {
				return []string{token, args[index+1]}, 2, true
			}
			return []string{token}, 1, true
		}
		return []string{arg}, 1, true
	}

	body := strings.TrimPrefix(arg, "-")
	name, value, hasValue := splitFlagToken(body)

	if info, ok := c.flagByName[name]; ok {
		token := "-" + info.Name
		if hasValue {
			return []string{token + "=" + value}, 1, true
		}
		if info.IsBool {
			return []string{token}, 1, true
		}
		if index+1 < len(args) {
			return []string{token, args[index+1]}, 2, true
		}
		return []string{token}, 1, true
	}

	if len(name) == 1 {
		if info, ok := c.flagByShort[name]; ok {
			token := "-" + info.Name
			if hasValue {
				return []string{token + "=" + value}, 1, true
			}
			if info.IsBool {
				return []string{token}, 1, true
			}
			if index+1 < len(args) {
				return []string{token, args[index+1]}, 2, true
			}
			return []string{token}, 1, true
		}
	}

	if !hasValue && len(name) > 1 && c.isBoolCluster(name) {
		tokens := make([]string, 0, len(name))
		for _, short := range name {
			info := c.flagByShort[string(short)]
			tokens = append(tokens, "-"+info.Name)
		}
		return tokens, 1, true
	}

	return []string{arg}, 1, true
}

func (c *Command) isBoolCluster(name string) bool {
	for _, short := range name {
		info, ok := c.flagByShort[string(short)]
		if !ok || !info.IsBool {
			return false
		}
	}
	return true
}
