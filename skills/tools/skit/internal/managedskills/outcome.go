package managedskills

import (
	"log/slog"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

// Outcome is the structured result consumed by thin cmd wrappers.
type Outcome struct {
	Result   log.Result
	Attrs    []slog.Attr
	ExitCode int
}
