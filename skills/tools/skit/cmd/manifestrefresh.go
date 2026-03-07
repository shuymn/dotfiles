package cmd

import (
	"context"
	"fmt"
	"io"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/managedskills"
)

const (
	manifestRefreshTool      = "manifest-refresh"
	manifestRefreshLogPrefix = managedskills.LogPrefix
)

const (
	manifestRefreshDefaultName = managedskills.DefaultManifestName
	manifestRefreshSkillFile   = managedskills.SkillFileName
	manifestRefreshVersion     = managedskills.ManifestVersion
)

// ManifestRefresh returns the manifest-refresh subcommand.
func ManifestRefresh() *cli.Command {
	c := cli.NewCommand(manifestRefreshTool, "Refresh the dotfiles-managed skills manifest from a local skills source")
	c.EnableDryRun()
	var source, manifestPath string
	var printOnly bool
	c.StringVar(&source, "source", "", "", "Path to the local skills source root (required)")
	c.StringVar(&manifestPath, "manifest", "", "", "Manifest output path (default: <source>/.dotfiles-managed-skills.json)")
	c.BoolVar(&printOnly, "print-only", "", false, "Print the generated manifest instead of writing it")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if source == "" {
			return fmt.Errorf("--source is required")
		}
		return exitCode(runManifestRefresh(s.Stdout, s.Stderr, source, manifestPath, printOnly, s.DryRun))
	}
	return c
}

func runManifestRefresh(w, stderr io.Writer, source, manifestPath string, printOnly, dryRun bool) int {
	result, err := managedskills.RefreshManifest(managedskills.RefreshOptions{
		Source:       source,
		ManifestPath: manifestPath,
		Write:        !printOnly && !dryRun,
	})
	if err != nil {
		printManifestRefreshError(stderr, err)
		return 1
	}

	if printOnly {
		fmt.Fprintf(w, "%s\n", result.Data)
		return 0
	}
	fmt.Fprintf(w, "%s manifest_path=%s\n", manifestRefreshLogPrefix, result.ManifestPath)
	fmt.Fprintf(w, "%s managed_skills=%d\n", manifestRefreshLogPrefix, result.ManagedSkills)
	if dryRun {
		fmt.Fprintf(w, "%s dry_run=true\n", manifestRefreshLogPrefix)
	}
	return 0
}

func printManifestRefreshError(stderr io.Writer, err error) {
	refreshErr, ok := err.(*managedskills.RefreshError)
	if !ok {
		fmt.Fprintf(stderr, "manifest-refresh: %v\n", err)
		return
	}

	switch refreshErr.Op {
	case "source":
		fmt.Fprintf(stderr, "manifest-refresh: source skills directory does not exist: %s\n", refreshErr.Path)
	case "read":
		fmt.Fprintf(stderr, "manifest-refresh: failed to discover skills: %v\n", refreshErr.Err)
	case "json":
		fmt.Fprintf(stderr, "manifest-refresh: failed to marshal manifest: %v\n", refreshErr.Err)
	case "mkdir":
		fmt.Fprintf(stderr, "manifest-refresh: failed to create manifest directory: %v\n", refreshErr.Err)
	case "write":
		fmt.Fprintf(stderr, "manifest-refresh: failed to write manifest: %v\n", refreshErr.Err)
	default:
		fmt.Fprintf(stderr, "manifest-refresh: %v\n", err)
	}
}

func sanitizeName(name string) string {
	return managedskills.SanitizeName(name)
}

func discoverSkills(sourceRoot string) ([]string, error) {
	return managedskills.DiscoverSkills(sourceRoot)
}

func formatSourceRoot(sourceRoot, manifestPath string) string {
	return managedskills.FormatSourceRoot(sourceRoot, manifestPath)
}
