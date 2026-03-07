package main

import (
	"context"
	"errors"
	"os"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/apps"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

func main() {
	if err := apps.NewConfiguredApp().RunContext(context.Background(), os.Args[1:]); err != nil {
		var exitErr cli.ExitError
		if errors.As(err, &exitErr) {
			os.Exit(int(exitErr))
		}
		os.Exit(1)
	}
}
