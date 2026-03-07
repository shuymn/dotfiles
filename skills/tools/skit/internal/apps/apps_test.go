package apps

import (
	"bytes"
	"context"
	"strings"
	"testing"
)

func TestNewConfiguredAppDefaultsToAuthoringCommandsOnly(t *testing.T) {
	restore := setConfigForTest(t, skitName, authoringCommandSet)
	defer restore()

	app := NewConfiguredApp()
	var stdout bytes.Buffer
	app.Stdout = &stdout

	if err := app.RunContext(context.Background(), []string{"--help"}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := stdout.String()
	if !strings.Contains(out, "Usage: skit <command> [flags]") {
		t.Fatalf("expected skit usage, got %q", out)
	}
	for _, want := range []string{"gate-check", "split-check", "review-finalize"} {
		if !strings.Contains(out, want) {
			t.Fatalf("expected %q in skit help, got %q", want, out)
		}
	}
	for _, unwanted := range []string{"build-skills", "manifest-refresh", "mark-managed", "reconcile", "audit-codex"} {
		if strings.Contains(out, unwanted) {
			t.Fatalf("did not expect %q in skit help, got %q", unwanted, out)
		}
	}
}

func TestNewConfiguredAppUsesAdminCommandsOnly(t *testing.T) {
	restore := setConfigForTest(t, skitkitName, adminCommandSet)
	defer restore()

	app := NewConfiguredApp()
	var stdout bytes.Buffer
	app.Stdout = &stdout

	if err := app.RunContext(context.Background(), []string{"--help"}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := stdout.String()
	if !strings.Contains(out, "Usage: skitkit <command> [flags]") {
		t.Fatalf("expected skitkit usage, got %q", out)
	}
	for _, want := range []string{"build-skills", "manifest-refresh", "mark-managed", "reconcile", "audit-codex"} {
		if !strings.Contains(out, want) {
			t.Fatalf("expected %q in skitkit help, got %q", want, out)
		}
	}
	for _, unwanted := range []string{"gate-check", "split-check", "review-finalize"} {
		if strings.Contains(out, unwanted) {
			t.Fatalf("did not expect %q in skitkit help, got %q", unwanted, out)
		}
	}
}

func TestNewConfiguredAppLeafHelpUsesConfiguredBinaryName(t *testing.T) {
	restore := setConfigForTest(t, skitkitName, adminCommandSet)
	defer restore()

	app := NewConfiguredApp()
	var stdout bytes.Buffer
	app.Stdout = &stdout

	if err := app.RunContext(context.Background(), []string{"help", "build-skills"}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := stdout.String()
	if !strings.Contains(out, "Usage: skitkit build-skills [flags]") {
		t.Fatalf("expected skitkit leaf usage, got %q", out)
	}
}

func TestNewConfiguredAppRejectsUnknownCommandSet(t *testing.T) {
	restore := setConfigForTest(t, "broken", "unknown")
	defer restore()

	defer func() {
		if r := recover(); r == nil {
			t.Fatal("expected panic for unsupported command set")
		}
	}()

	_ = NewConfiguredApp()
}

func setConfigForTest(t *testing.T, binaryName, commandSet string) func() {
	t.Helper()

	prevBinaryName := BinaryName
	prevCommandSet := CommandSet
	BinaryName = binaryName
	CommandSet = commandSet

	return func() {
		BinaryName = prevBinaryName
		CommandSet = prevCommandSet
	}
}
