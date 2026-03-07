package cli

import (
	"context"
	"encoding"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"sort"
	"strings"
	"text/tabwriter"
)

var preEncodedFragments = []string{
	"%00", "%01", "%02", "%03", "%04", "%05", "%06", "%07",
	"%08", "%09", "%0a", "%0b", "%0c", "%0d", "%0e", "%0f",
	"%10", "%11", "%12", "%13", "%14", "%15", "%16", "%17",
	"%18", "%19", "%1a", "%1b", "%1c", "%1d", "%1e", "%1f",
	"%2e", "%2f", "%5c", "%7f",
}

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
	Command *Command
	Path    []string
	Flags   *flag.FlagSet
	Args    []string
	DryRun  bool
}

type flagBinder struct {
	help  FlagHelp
	apply func(fs *flag.FlagSet)
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
	flagByName  map[string]FlagHelp
	flagByShort map[string]FlagHelp
	dryRun      *bool
}

// App owns the command tree and dispatch.
type App struct {
	Name    string
	Summary string
	Root    *Command
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

	if containsHelpArg(remaining) {
		a.printUsage(a.stdout(), cmd)
		return nil
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

	state := &State{
		Command: cmd,
		Path:    cmd.pathSegments(),
		Flags:   fs,
		Args:    append([]string(nil), fs.Args()...),
	}
	if cmd.dryRun != nil {
		state.DryRun = *cmd.dryRun
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

func (a *App) printUsage(w io.Writer, cmd *Command) {
	if cmd == nil {
		cmd = a.Root
	}

	usageSuffix := "<command> [flags]"
	if len(cmd.children) == 0 {
		usageSuffix = "[flags] [args...]"
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
}

func (a *App) emitError(cmd *Command, code, summary string) {
	logger := slog.New(slog.NewJSONHandler(a.stdout(), nil))

	attrs := []slog.Attr{
		slog.String("tool", a.Name),
		slog.String("code", code),
		slog.String("summary", summary),
	}
	if cmd != nil && cmd != a.Root {
		attrs = append(attrs, slog.String("command", strings.Join(cmd.pathSegments(), " ")))
	}

	logger.LogAttrs(context.Background(), slog.LevelError, "cli-error", attrs...)
}

func (a *App) stdout() io.Writer {
	if a.Stdout != nil {
		return a.Stdout
	}
	return os.Stdout
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

func (c *Command) newFlagSet() *flag.FlagSet {
	fs := flag.NewFlagSet(c.Name, flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	fs.Usage = func() {}
	for _, binder := range c.flags {
		binder.apply(fs)
	}
	return fs
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

func validateInputs(fs *flag.FlagSet) error {
	var firstErr error
	fs.VisitAll(func(f *flag.Flag) {
		if firstErr != nil {
			return
		}
		value := f.Value.String()
		switch {
		case containsControlChars(value):
			firstErr = fmt.Errorf("flag --%s contains control characters", f.Name)
		case containsPreEncoded(value):
			firstErr = fmt.Errorf("flag --%s contains pre-encoded control or path characters", f.Name)
		}
	})
	if firstErr != nil {
		return firstErr
	}

	for index, arg := range fs.Args() {
		switch {
		case containsControlChars(arg):
			return fmt.Errorf("argument %d contains control characters", index+1)
		case containsPreEncoded(arg):
			return fmt.Errorf("argument %d contains pre-encoded control or path characters", index+1)
		}
	}
	return nil
}

func containsControlChars(s string) bool {
	for i := 0; i < len(s); i++ {
		b := s[i]
		if b == '\t' || b == '\n' || b == '\r' {
			continue
		}
		if b < 0x20 || b == 0x7f {
			return true
		}
	}
	return false
}

func containsPreEncoded(s string) bool {
	lower := strings.ToLower(s)
	for _, fragment := range preEncodedFragments {
		if strings.Contains(lower, fragment) {
			return true
		}
	}
	return false
}

func containsHelpArg(args []string) bool {
	for _, arg := range args {
		if arg == "--" {
			return false
		}
		if isHelpToken(arg) {
			return true
		}
	}
	return false
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

func splitFlagToken(token string) (name, value string, hasValue bool) {
	name, value, hasValue = strings.Cut(token, "=")
	return name, value, hasValue
}

func isFlagLike(arg string) bool {
	return strings.HasPrefix(arg, "-") && arg != ""
}

func isHelpToken(arg string) bool {
	return arg == "--help" || arg == "-h"
}
