package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"reflect"
	"strings"
	"testing"
)

func TestRunContextNoSubcommandEmitsStructuredError(t *testing.T) {
	app := newTestApp()
	app.Root.Add(NewCommand("test", "test command"))

	err := app.RunContext(context.Background(), nil)
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["msg"] != "cli-error" {
		t.Fatalf("expected cli-error message, got %v", result["msg"])
	}
	if result["code"] != "NO_SUBCOMMAND" {
		t.Fatalf("expected NO_SUBCOMMAND, got %v", result["code"])
	}
}

func TestRootHelpFlagsPrintUsage(t *testing.T) {
	for _, arg := range []string{"--help", "-h"} {
		app := newTestApp()
		app.Root.Add(NewCommand("build", "build something"))

		if err := app.RunContext(context.Background(), []string{arg}); err != nil {
			t.Fatalf("arg=%s: unexpected error: %v", arg, err)
		}

		out := app.Stdout.(*bytes.Buffer).String()
		if !strings.Contains(out, "Usage: skit <command> [flags]") {
			t.Fatalf("arg=%s: expected root usage, got %q", arg, out)
		}
		if !strings.Contains(out, "build") {
			t.Fatalf("arg=%s: expected command list, got %q", arg, out)
		}
	}
}

func TestHelpSubcommandPrintsLeafUsage(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("build-skills", "Build skill artifacts")
	var source string
	cmd.StringVar(&source, "source", "s", "", "Source root")
	app.Root.Add(cmd)

	if err := app.RunContext(context.Background(), []string{"help", "build-skills"}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := app.Stdout.(*bytes.Buffer).String()
	if !strings.Contains(out, "Usage: skit build-skills [flags] [args...]") {
		t.Fatalf("expected leaf usage, got %q", out)
	}
	if !strings.Contains(out, "--source, -s <value>") {
		t.Fatalf("expected flag help, got %q", out)
	}
}

func TestDispatchWithNestedCommandAndNormalizedFlags(t *testing.T) {
	app := newTestApp()
	parent := NewCommand("parent", "parent command")
	child := NewCommand("child", "child command")

	var (
		path    string
		verbose bool
		force   bool
		color   = true
		got     *State
	)

	child.StringVar(&path, "path", "p", "", "Path")
	child.BoolVar(&verbose, "verbose", "v", false, "Verbose")
	child.BoolVar(&force, "force", "f", false, "Force")
	child.BoolVar(&color, "color", "c", true, "Color")
	child.Run = func(ctx context.Context, s *State) error {
		got = s
		return nil
	}
	parent.Add(child)
	app.Root.Add(parent)

	err := app.RunContext(context.Background(), []string{
		"parent", "child", "pos1", "--path=dst", "-vf", "--no-color", "--", "--literal",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if got == nil {
		t.Fatal("expected state to be captured")
	}
	if path != "dst" || !verbose || !force || color {
		t.Fatalf("unexpected flag state path=%q verbose=%t force=%t color=%t", path, verbose, force, color)
	}
	if !reflect.DeepEqual(got.Path, []string{"parent", "child"}) {
		t.Fatalf("expected path [parent child], got %v", got.Path)
	}
	if !reflect.DeepEqual(got.Args, []string{"pos1", "--literal"}) {
		t.Fatalf("expected args [pos1 --literal], got %v", got.Args)
	}
}

func TestFlagParseErrorEmitsStructuredJSON(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("count", "count command")
	var value int
	cmd.IntVar(&value, "count", "c", 0, "Count")
	cmd.Run = func(ctx context.Context, s *State) error { return nil }
	app.Root.Add(cmd)

	err := app.RunContext(context.Background(), []string{"count", "--count", "nope"})
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["code"] != "FLAG_PARSE_ERROR" {
		t.Fatalf("expected FLAG_PARSE_ERROR, got %v", result["code"])
	}
	if !strings.Contains(result["summary"].(string), "invalid value") {
		t.Fatalf("expected parse summary, got %v", result["summary"])
	}
}

func TestUnknownSubcommandEmitsStructuredJSON(t *testing.T) {
	app := newTestApp()
	app.Root.Add(NewCommand("known", "known"))

	err := app.RunContext(context.Background(), []string{"unknown"})
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["code"] != "UNKNOWN_SUBCOMMAND" {
		t.Fatalf("expected UNKNOWN_SUBCOMMAND, got %v", result["code"])
	}
}

func TestInputHardeningRejectsControlCharacters(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("check", "check command")
	var name string
	cmd.StringVar(&name, "name", "n", "", "Name")
	cmd.Run = func(ctx context.Context, s *State) error { return nil }
	app.Root.Add(cmd)

	err := app.RunContext(context.Background(), []string{"check", "--name", "bad\x01value"})
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["code"] != "INPUT_VALIDATION_ERROR" {
		t.Fatalf("expected INPUT_VALIDATION_ERROR, got %v", result["code"])
	}
}

func TestInputHardeningRejectsPreEncodedSequences(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("check", "check command")
	cmd.Run = func(ctx context.Context, s *State) error { return nil }
	app.Root.Add(cmd)

	err := app.RunContext(context.Background(), []string{"check", "%2e%2e%2fsecret"})
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["code"] != "INPUT_VALIDATION_ERROR" {
		t.Fatalf("expected INPUT_VALIDATION_ERROR, got %v", result["code"])
	}
}

func TestEnableDryRunPropagatesToState(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("write", "write command")
	cmd.EnableDryRun()

	var gotDryRun bool
	cmd.Run = func(ctx context.Context, s *State) error {
		gotDryRun = s.DryRun
		return nil
	}
	app.Root.Add(cmd)

	if err := app.RunContext(context.Background(), []string{"write", "--dry-run"}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !gotDryRun {
		t.Fatal("expected dry-run=true")
	}
}

func TestExitErrorPropagates(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("fail", "fail command")
	cmd.Run = func(ctx context.Context, s *State) error {
		return ExitError(7)
	}
	app.Root.Add(cmd)

	err := app.RunContext(context.Background(), []string{"fail"})
	assertExitCode(t, err, 7)

	if out := app.Stdout.(*bytes.Buffer).String(); out != "" {
		t.Fatalf("expected no framework output, got %q", out)
	}
}

func TestCommandErrorEmitsStructuredJSON(t *testing.T) {
	app := newTestApp()
	cmd := NewCommand("boom", "boom command")
	cmd.Run = func(ctx context.Context, s *State) error {
		return errors.New("boom")
	}
	app.Root.Add(cmd)

	err := app.RunContext(context.Background(), []string{"boom"})
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["code"] != "COMMAND_ERROR" {
		t.Fatalf("expected COMMAND_ERROR, got %v", result["code"])
	}
}

func TestNilRunEmitsStructuredJSON(t *testing.T) {
	app := newTestApp()
	app.Root.Add(NewCommand("noop", "noop command"))

	err := app.RunContext(context.Background(), []string{"noop"})
	assertExitCode(t, err, 1)

	result := decodeJSONLine(t, app.Stdout.(*bytes.Buffer).String())
	if result["code"] != "MISSING_COMMAND_RUNNER" {
		t.Fatalf("expected MISSING_COMMAND_RUNNER, got %v", result["code"])
	}
}

func newTestApp() *App {
	app := New("skit", "skill toolkit")
	app.Stdout = &bytes.Buffer{}
	app.Stderr = &bytes.Buffer{}
	return app
}

func decodeJSONLine(t *testing.T, raw string) map[string]any {
	t.Helper()

	line := strings.TrimSpace(raw)
	if line == "" {
		t.Fatal("expected JSON line output")
	}

	var result map[string]any
	if err := json.Unmarshal([]byte(line), &result); err != nil {
		t.Fatalf("failed to decode JSON %q: %v", line, err)
	}
	return result
}

func assertExitCode(t *testing.T, err error, want int) {
	t.Helper()

	var exitErr ExitError
	if !errors.As(err, &exitErr) {
		t.Fatalf("expected ExitError(%d), got %v", want, err)
	}
	if int(exitErr) != want {
		t.Fatalf("expected exit code %d, got %d", want, exitErr)
	}
}
