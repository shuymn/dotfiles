package cmd

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

const auditCodexTool = "audit-codex"

// removeAllFn is os.RemoveAll, replaceable in tests.
var removeAllFn = os.RemoveAll

// AuditCodex returns the audit-codex subcommand.
func AuditCodex() *cli.Command {
	c := cli.NewCommand(auditCodexTool, "Audit ~/.codex/skills and prune duplicates found in ~/.agents/skills")
	c.EnableDryRun()
	var manifestPath, agentsSkills, codexSkills, marker string
	var pruneDuplicates bool
	c.StringVar(&manifestPath, "manifest", "", "", "Path to managed skills manifest (required)")
	c.StringVar(&agentsSkills, "agents-skills", "", "", "Path to ~/.agents/skills (required)")
	c.StringVar(&codexSkills, "codex-skills", "", "", "Path to ~/.codex/skills (required)")
	c.StringVar(&marker, "marker", "", ".dotfiles-managed", "Managed marker filename")
	c.BoolVar(&pruneDuplicates, "prune-duplicates", "", false, "Remove entries from ~/.codex/skills when the same entry exists in ~/.agents/skills")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if manifestPath == "" || agentsSkills == "" || codexSkills == "" {
			return fmt.Errorf("usage: %s audit-codex --manifest <path> --agents-skills <path> --codex-skills <path> [--marker <name>] [--prune-duplicates]", s.AppName)
		}
		return exitCode(runAuditCodex(os.Stdout, manifestPath, agentsSkills, codexSkills, marker, pruneDuplicates, s.DryRun))
	}
	return c
}

func runAuditCodex(w io.Writer, manifestPath, agentsSkills, codexSkills, marker string, pruneDuplicates, dryRun bool) int {
	resolvedManifest := pathutil.ExpandAndAbs(manifestPath)
	resolvedAgentsSkills := pathutil.ExpandAndAbs(agentsSkills)
	resolvedCodexSkills := pathutil.ExpandAndAbs(codexSkills)

	m, err := manifest.Load(resolvedManifest)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    auditCodexTool,
			Status:  "FAIL",
			Code:    "MANIFEST_ERROR",
			Summary: fmt.Sprintf("Failed to load manifest: %v", err),
		})
		return 1
	}

	managed := make(map[string]bool, len(m.Skills))
	for _, s := range m.Skills {
		managed[s] = true
	}

	codexEntries, err := listSkillDirs(resolvedCodexSkills)
	if err != nil {
		if os.IsNotExist(err) {
			log.Emit(w, log.Result{
				Tool:    auditCodexTool,
				Status:  "PASS",
				Code:    "CODEX_DIR_MISSING",
				Summary: fmt.Sprintf("codex_dir_missing=%s", resolvedCodexSkills),
			})
			return 0
		}
		log.Emit(w, log.Result{
			Tool:    auditCodexTool,
			Status:  "FAIL",
			Code:    "MANIFEST_ERROR",
			Summary: fmt.Sprintf("Failed to read codex skills dir: %v", err),
		})
		return 1
	}

	if len(codexEntries) == 0 {
		log.Emit(w, log.Result{
			Tool:    auditCodexTool,
			Status:  "PASS",
			Code:    "CODEX_DIR_EMPTY",
			Summary: fmt.Sprintf("codex_dir_empty=%s", resolvedCodexSkills),
		})
		return 0
	}

	var duplicates []string
	var managedDuplicates []string
	var externalDuplicates []string
	var codexOnly []string

	for _, name := range codexEntries {
		agentsSkillDir := filepath.Join(resolvedAgentsSkills, name)
		info, err := os.Stat(agentsSkillDir)
		existsInAgents := err == nil && info.IsDir()

		if existsInAgents {
			duplicates = append(duplicates, name)
			markerPath := filepath.Join(agentsSkillDir, marker)
			_, markerErr := os.Stat(markerPath)
			hasMarker := markerErr == nil
			if managed[name] || hasMarker {
				managedDuplicates = append(managedDuplicates, name)
			} else {
				externalDuplicates = append(externalDuplicates, name)
			}
		} else {
			codexOnly = append(codexOnly, name)
		}
	}

	attrs := []slog.Attr{
		slog.Int("signal.codex", len(codexEntries)),
		slog.Int("signal.duplicates", len(duplicates)),
		slog.Int("signal.managed_duplicates", len(managedDuplicates)),
		slog.Int("signal.external_duplicates", len(externalDuplicates)),
		slog.Int("signal.codex_only", len(codexOnly)),
	}

	if len(duplicates) > 0 {
		attrs = append(attrs, slog.String("signal.duplicate_names", strings.Join(duplicates, ",")))
	}
	if len(codexOnly) > 0 {
		attrs = append(attrs, slog.String("signal.codex_only_names", strings.Join(codexOnly, ",")))
	}

	pruned := 0
	if pruneDuplicates && len(duplicates) > 0 && !dryRun {
		for _, name := range duplicates {
			target := filepath.Join(resolvedCodexSkills, name)
			if err := removeAllFn(target); err != nil {
				attrs = append(attrs, slog.Int("signal.pruned", pruned))
				log.Emit(w, log.Result{
					Tool:    auditCodexTool,
					Status:  "FAIL",
					Code:    "PRUNE_FAILED",
					Summary: fmt.Sprintf("Failed to remove %s: %v", target, err),
				}, attrs...)
				return 1
			}
			pruned++
		}
	}

	attrs = append(attrs, slog.Int("signal.pruned", pruned))
	if dryRun {
		attrs = append(attrs, slog.Bool("signal.dry_run", true))
	}

	log.Emit(w, log.Result{
		Tool:   auditCodexTool,
		Status: "PASS",
		Code:   "AUDIT_COMPLETE",
		Summary: fmt.Sprintf("codex=%d duplicates=%d managed_duplicates=%d external_duplicates=%d codex_only=%d pruned=%d",
			len(codexEntries), len(duplicates), len(managedDuplicates), len(externalDuplicates), len(codexOnly), pruned),
	}, attrs...)

	return 0
}

// listSkillDirs returns sorted subdirectory names under dir.
func listSkillDirs(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}

	var names []string
	for _, e := range entries {
		if e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	return names, nil
}
