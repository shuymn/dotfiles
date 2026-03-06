package cli

import (
	"testing"
)

func TestNoArgs(t *testing.T) {
	app := &App{Name: "skit"}
	rc := app.Run([]string{"skit"})
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
}

func TestHelpFlag(t *testing.T) {
	app := &App{Name: "skit"}
	for _, arg := range []string{"--help", "-h"} {
		rc := app.Run([]string{"skit", arg})
		if rc != 0 {
			t.Errorf("expected rc=0 for %q, got %d", arg, rc)
		}
	}
}

func TestUnknownSubcommand(t *testing.T) {
	app := &App{Name: "skit"}
	rc := app.Run([]string{"skit", "unknown"})
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
}

func TestKnownSubcommand(t *testing.T) {
	app := &App{Name: "skit"}
	called := false
	var receivedArgs []string
	app.Register(&Command{
		Name:        "test-cmd",
		Description: "test command",
		Run: func(args []string) int {
			called = true
			receivedArgs = args
			return 0
		},
	})
	rc := app.Run([]string{"skit", "test-cmd", "arg1", "arg2"})
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if !called {
		t.Error("expected command to be called")
	}
	if len(receivedArgs) != 2 || receivedArgs[0] != "arg1" || receivedArgs[1] != "arg2" {
		t.Errorf("expected [arg1 arg2], got %v", receivedArgs)
	}
}
