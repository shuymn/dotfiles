package workflow

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"testing"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

func TestMain(m *testing.M) {
	gitToplevelFn = func(dir string) (string, error) {
		return "", fmt.Errorf("git stubbed out in tests")
	}
	gitDiffNamesFn = func(root, base string) ([]string, error) {
		return nil, fmt.Errorf("git stubbed out in tests")
	}
	os.Exit(m.Run())
}

func stubGit(t *testing.T, repoRoot string, diffFiles []string) {
	t.Helper()
	origToplevel := gitToplevelFn
	origDiffNames := gitDiffNamesFn
	t.Cleanup(func() {
		gitToplevelFn = origToplevel
		gitDiffNamesFn = origDiffNames
	})
	gitToplevelFn = func(dir string) (string, error) {
		return repoRoot, nil
	}
	gitDiffNamesFn = func(root, base string) ([]string, error) {
		return diffFiles, nil
	}
}

func runCommandOutput(command *cli.Command, stdin string, args ...string) (int, string, string, error) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	app := cli.New("skit", "skill toolkit")
	app.Stdin = strings.NewReader(stdin)
	app.Stdout = &stdout
	app.Stderr = &stderr
	app.Root.Add(command)

	runErr := app.RunContext(context.Background(), append([]string{command.Name}, args...))

	rc := 0
	if runErr != nil {
		var exitErr cli.ExitError
		if errors.As(runErr, &exitErr) {
			rc = int(exitErr)
		} else {
			rc = 1
		}
	}

	return rc, stdout.String(), stderr.String(), nil
}

func parseJSONResult(raw string) map[string]any {
	var result map[string]any
	if line := strings.TrimSpace(raw); line != "" {
		if err := json.Unmarshal([]byte(line), &result); err != nil {
			return map[string]any{"_raw": line, "_err": err.Error()}
		}
	}
	return result
}
