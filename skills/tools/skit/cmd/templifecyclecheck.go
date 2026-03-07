package cmd

import (
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/workflow"
)

func TempLifecycleCheck() *cli.Command { return workflow.TempLifecycleCheck() }
