package cli

import (
	"log/slog"
	"strings"

	intlog "github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

type frameworkError struct {
	code    string
	summary string
}

func (e *frameworkError) Error() string {
	return e.summary
}

func (a *App) emitError(cmd *Command, code, summary string) {
	attrs := []slog.Attr{}
	if cmd != nil && cmd != a.Root {
		attrs = append(attrs, slog.String("command", strings.Join(cmd.pathSegments(), " ")))
	}

	intlog.Emit(a.stdout(), intlog.Result{
		Tool:    a.Name,
		Status:  "FAIL",
		Code:    code,
		Summary: summary,
	}, attrs...)
}
