package cmd

import (
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

const reconcileTool = "reconcile"

// execCommandFn is exec.Command, replaceable in tests.
var execCommandFn = exec.Command

// Reconcile returns the reconcile subcommand.
func Reconcile() *cli.Command {
	return &cli.Command{
		Name:        reconcileTool,
		Description: "Remove stale managed skills while preserving external skills",
		Run: func(args []string) int {
			return runReconcile(os.Stdout, args)
		},
	}
}

func runReconcile(w io.Writer, args []string) int {
	fs := flag.NewFlagSet(reconcileTool, flag.ContinueOnError)
	manifestPath := fs.String("manifest", "", "Path to managed skills manifest (required)")
	agentsSkills := fs.String("agents-skills", "", "Path to ~/.agents/skills (required)")
	marker := fs.String("marker", ".dotfiles-managed", "Managed marker filename")
	// strings.Fields splits by whitespace; sufficient for real values like "bunx --bun skills".
	// Quoted tokens (e.g. paths with spaces) are not supported.
	skillsCmd := fs.String("skills-cmd", "", "Skills CLI command prefix, e.g. 'bunx --bun skills' (required)")

	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 1
	}

	if *manifestPath == "" || *agentsSkills == "" || *skillsCmd == "" {
		fmt.Fprintln(os.Stderr, "usage: skit reconcile --manifest <path> --agents-skills <path> --skills-cmd <cmd> [--marker <name>]")
		return 1
	}

	resolvedManifest := pathutil.ExpandAndAbs(*manifestPath)
	resolvedAgentsSkills := pathutil.ExpandAndAbs(*agentsSkills)

	m, err := manifest.Load(resolvedManifest)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    reconcileTool,
			Status:  "FAIL",
			Code:    "MANIFEST_ERROR",
			Summary: fmt.Sprintf("Failed to load manifest: %v", err),
		})
		return 1
	}

	if len(m.Skills) == 0 {
		log.Emit(w, log.Result{
			Tool:    reconcileTool,
			Status:  "FAIL",
			Code:    "EMPTY_MANIFEST",
			Summary: "Safety stop: manifest has zero managed skills",
		})
		return 1
	}

	desired := make(map[string]bool, len(m.Skills))
	for _, s := range m.Skills {
		desired[s] = true
	}

	installed, err := discoverManagedInstalled(resolvedAgentsSkills, *marker)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    reconcileTool,
			Status:  "FAIL",
			Code:    "MANIFEST_ERROR",
			Summary: fmt.Sprintf("Failed to discover installed skills: %v", err),
		})
		return 1
	}

	var toRemove []string
	for _, s := range installed {
		if !desired[s] {
			toRemove = append(toRemove, s)
		}
	}
	sort.Strings(toRemove)

	attrs := []slog.Attr{
		slog.Int("signal.desired", len(desired)),
		slog.Int("signal.installed", len(installed)),
		slog.Int("signal.removed", len(toRemove)),
	}

	if len(toRemove) == 0 {
		log.Emit(w, log.Result{
			Tool:    reconcileTool,
			Status:  "PASS",
			Code:    "NO_STALE_MANAGED_SKILLS",
			Summary: fmt.Sprintf("desired=%d installed=%d removed=%d", len(desired), len(installed), len(toRemove)),
		}, attrs...)
		return 0
	}

	attrs = append(attrs, slog.String("signal.removed_names", strings.Join(toRemove, ",")))

	cmdParts := strings.Fields(*skillsCmd)
	cmdParts = append(cmdParts, "remove", "-g", "-y")
	cmdParts = append(cmdParts, toRemove...)

	cmd := execCommandFn(cmdParts[0], cmdParts[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		log.Emit(w, log.Result{
			Tool:    reconcileTool,
			Status:  "FAIL",
			Code:    "REMOVE_FAILED",
			Summary: fmt.Sprintf("skills remove failed: %v", err),
		}, attrs...)
		return 1
	}

	log.Emit(w, log.Result{
		Tool:    reconcileTool,
		Status:  "PASS",
		Code:    "RECONCILE_COMPLETE",
		Summary: fmt.Sprintf("desired=%d installed=%d removed=%d", len(desired), len(installed), len(toRemove)),
	}, attrs...)

	return 0
}

// discoverManagedInstalled returns the names of subdirectories under agentsSkills
// that contain a marker file. Returns nil if agentsSkills does not exist.
func discoverManagedInstalled(agentsSkills, marker string) ([]string, error) {
	entries, err := os.ReadDir(agentsSkills)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	managed := make([]string, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		markerPath := filepath.Join(agentsSkills, e.Name(), marker)
		if _, err := os.Stat(markerPath); err == nil {
			managed = append(managed, e.Name())
		}
	}

	return managed, nil
}
