package cmd

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

func runCommandOutput(command *cli.Command, stdin string, args ...string) (int, string, string, error) {
	stdoutReader, stdoutWriter, err := os.Pipe()
	if err != nil {
		return 0, "", "", err
	}
	defer stdoutReader.Close()

	stderrReader, stderrWriter, err := os.Pipe()
	if err != nil {
		_ = stdoutWriter.Close()
		return 0, "", "", err
	}
	defer stderrReader.Close()

	oldStdout := os.Stdout
	oldStderr := os.Stderr
	os.Stdout = stdoutWriter
	os.Stderr = stderrWriter
	defer func() {
		os.Stdout = oldStdout
		os.Stderr = oldStderr
	}()

	oldStdin := os.Stdin
	stdinReader, stdinWriter, err := os.Pipe()
	if err != nil {
		_ = stdoutWriter.Close()
		_ = stderrWriter.Close()
		return 0, "", "", err
	}
	os.Stdin = stdinReader
	if _, err := io.WriteString(stdinWriter, stdin); err != nil {
		_ = stdinReader.Close()
		_ = stdinWriter.Close()
		_ = stdoutWriter.Close()
		_ = stderrWriter.Close()
		return 0, "", "", err
	}
	_ = stdinWriter.Close()
	defer func() {
		os.Stdin = oldStdin
		_ = stdinReader.Close()
	}()

	app := cli.New("skit", "skill toolkit")
	app.Stdout = stdoutWriter
	app.Stderr = stderrWriter
	app.Root.Add(command)

	runErr := app.RunContext(context.Background(), append([]string{command.Name}, args...))

	_ = stdoutWriter.Close()
	_ = stderrWriter.Close()

	stdoutBytes, readStdoutErr := io.ReadAll(stdoutReader)
	if readStdoutErr != nil {
		return 0, "", "", readStdoutErr
	}
	stderrBytes, readStderrErr := io.ReadAll(stderrReader)
	if readStderrErr != nil {
		return 0, "", "", readStderrErr
	}

	rc := 0
	if runErr != nil {
		var exitErr cli.ExitError
		if errors.As(runErr, &exitErr) {
			rc = int(exitErr)
		} else {
			rc = 1
		}
	}

	return rc, string(stdoutBytes), string(stderrBytes), nil
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
