package cmd

import (
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/workflow"
)

func AdversarialCoverageCheck() *cli.Command { return workflow.AdversarialCoverageCheck() }
