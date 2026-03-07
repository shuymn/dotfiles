package cmd

import (
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/workflow"
)

func ReviewFinalize() *cli.Command { return workflow.ReviewFinalize() }
