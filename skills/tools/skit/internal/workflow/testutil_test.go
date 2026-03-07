package workflow

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

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
