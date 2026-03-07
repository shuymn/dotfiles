package workflow

import "github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"

func exitCode(rc int) error {
	if rc != 0 {
		return cli.ExitError(rc)
	}
	return nil
}
