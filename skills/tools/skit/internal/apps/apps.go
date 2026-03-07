package apps

import (
	"fmt"

	"github.com/shuymn/dotfiles/skills/tools/skit/cmd"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
)

const (
	authoringCommandSet = "authoring"
	adminCommandSet     = "admin"

	skitName       = "skit"
	skitSummary    = "skill authoring toolkit"
	skitkitName    = "skitkit"
	skitkitSummary = "skill management toolkit"
)

// BinaryName is injected at build time via -ldflags -X.
var BinaryName = skitName

// CommandSet is injected at build time via -ldflags -X.
var CommandSet = authoringCommandSet

// NewConfiguredApp builds the CLI selected by build-time flags.
func NewConfiguredApp() *cli.App {
	switch CommandSet {
	case "", authoringCommandSet:
		return newApp(configuredBinaryName(), skitSummary, authoringCommands())
	case adminCommandSet:
		return newApp(configuredBinaryName(), skitkitSummary, adminCommands())
	default:
		panic(fmt.Sprintf("unsupported command set %q", CommandSet))
	}
}

func authoringCommands() []*cli.Command {
	return []*cli.Command{
		cmd.FileScopeCheck(),
		cmd.FreshnessPreflight(),
		cmd.ArtifactFormatCheck(),
		cmd.RiskFormatCheck(),
		cmd.VerificationCmdCheck(),
		cmd.BundleValidateCheck(),
		cmd.DepGraphGen(),
		cmd.TempLifecycleCheck(),
		cmd.RiskDodCheck(),
		cmd.TraceComposeCheck(),
		cmd.AdversarialCoverageCheck(),
		cmd.SplitCheck(),
		cmd.DigestStamp(),
		cmd.StructuralCheck(),
		cmd.ReviewFinalize(),
		cmd.GateCheck(),
	}
}

func adminCommands() []*cli.Command {
	return []*cli.Command{
		cmd.BuildSkills(),
		cmd.ManifestRefresh(),
		cmd.MarkManaged(),
		cmd.Reconcile(),
		cmd.AuditCodex(),
	}
}

func configuredBinaryName() string {
	if BinaryName == "" {
		return skitName
	}
	return BinaryName
}

func newApp(name, summary string, commands []*cli.Command) *cli.App {
	app := cli.New(name, summary)
	app.Root.Add(commands...)
	return app
}
