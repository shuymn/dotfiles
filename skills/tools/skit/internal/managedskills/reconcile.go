package managedskills

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

// ExecCommandFn is the injectable command factory used by reconcile.
type ExecCommandFn func(name string, arg ...string) *exec.Cmd

// ReconcileOptions controls stale managed-skill removal.
type ReconcileOptions struct {
	ManifestPath string
	AgentsSkills string
	Marker       string
	SkillsCmd    string
	DryRun       bool
	Stdout       io.Writer
	Stderr       io.Writer
	ExecCommand  ExecCommandFn
}

// RunReconcile removes stale managed skills and reports the outcome.
func RunReconcile(opts ReconcileOptions) Outcome {
	resolvedManifest := pathutil.ExpandAndAbs(opts.ManifestPath)
	resolvedAgentsSkills := pathutil.ExpandAndAbs(opts.AgentsSkills)

	m, err := manifest.Load(resolvedManifest)
	if err != nil {
		return Outcome{
			Result: log.Result{
				Tool:    "reconcile",
				Status:  "FAIL",
				Code:    "MANIFEST_ERROR",
				Summary: fmt.Sprintf("Failed to load manifest: %v", err),
			},
			ExitCode: 1,
		}
	}

	if len(m.Skills) == 0 {
		return Outcome{
			Result: log.Result{
				Tool:    "reconcile",
				Status:  "FAIL",
				Code:    "EMPTY_MANIFEST",
				Summary: "Safety stop: manifest has zero managed skills",
			},
			ExitCode: 1,
		}
	}

	desired := make(map[string]bool, len(m.Skills))
	for _, s := range m.Skills {
		desired[s] = true
	}

	installed, err := DiscoverManagedInstalled(resolvedAgentsSkills, opts.Marker)
	if err != nil {
		return Outcome{
			Result: log.Result{
				Tool:    "reconcile",
				Status:  "FAIL",
				Code:    "MANIFEST_ERROR",
				Summary: fmt.Sprintf("Failed to discover installed skills: %v", err),
			},
			ExitCode: 1,
		}
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
		return Outcome{
			Result: log.Result{
				Tool:    "reconcile",
				Status:  "PASS",
				Code:    "NO_STALE_MANAGED_SKILLS",
				Summary: fmt.Sprintf("desired=%d installed=%d removed=%d", len(desired), len(installed), len(toRemove)),
			},
			Attrs: attrs,
		}
	}

	attrs = append(attrs, slog.String("signal.removed_names", strings.Join(toRemove, ",")))
	if opts.DryRun {
		attrs = append(attrs, slog.Bool("signal.dry_run", true))
		return Outcome{
			Result: log.Result{
				Tool:    "reconcile",
				Status:  "PASS",
				Code:    "RECONCILE_DRY_RUN",
				Summary: fmt.Sprintf("desired=%d installed=%d removed=%d dry_run=true", len(desired), len(installed), len(toRemove)),
			},
			Attrs: attrs,
		}
	}

	cmdParts := strings.Fields(opts.SkillsCmd)
	cmdParts = append(cmdParts, "remove", "-g", "-y")
	cmdParts = append(cmdParts, toRemove...)

	cmd := opts.ExecCommand(cmdParts[0], cmdParts[1:]...)
	cmd.Stdout = opts.Stdout
	cmd.Stderr = opts.Stderr

	if err := cmd.Run(); err != nil {
		return Outcome{
			Result: log.Result{
				Tool:    "reconcile",
				Status:  "FAIL",
				Code:    "REMOVE_FAILED",
				Summary: fmt.Sprintf("skills remove failed: %v", err),
			},
			Attrs:    attrs,
			ExitCode: 1,
		}
	}

	return Outcome{
		Result: log.Result{
			Tool:    "reconcile",
			Status:  "PASS",
			Code:    "RECONCILE_COMPLETE",
			Summary: fmt.Sprintf("desired=%d installed=%d removed=%d", len(desired), len(installed), len(toRemove)),
		},
		Attrs: attrs,
	}
}

// DiscoverManagedInstalled returns the names of subdirectories under agentsSkills
// that contain a marker file. Returns nil if agentsSkills does not exist.
func DiscoverManagedInstalled(agentsSkills, marker string) ([]string, error) {
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
