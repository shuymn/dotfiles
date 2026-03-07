package managedskills

import (
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

// RunAuditCodex audits codex/agents skill overlap and optionally prunes duplicates.
func RunAuditCodex(manifestPath, agentsSkills, codexSkills, marker string, pruneDuplicates, dryRun bool, removeAll func(string) error) Outcome {
	resolvedManifest := pathutil.ExpandAndAbs(manifestPath)
	resolvedAgentsSkills := pathutil.ExpandAndAbs(agentsSkills)
	resolvedCodexSkills := pathutil.ExpandAndAbs(codexSkills)

	m, err := manifest.Load(resolvedManifest)
	if err != nil {
		return Outcome{
			Result: log.Result{
				Tool:    "audit-codex",
				Status:  "FAIL",
				Code:    "MANIFEST_ERROR",
				Summary: fmt.Sprintf("Failed to load manifest: %v", err),
			},
			ExitCode: 1,
		}
	}

	managed := make(map[string]bool, len(m.Skills))
	for _, s := range m.Skills {
		managed[s] = true
	}

	codexEntries, err := ListSkillDirs(resolvedCodexSkills)
	if err != nil {
		if os.IsNotExist(err) {
			return Outcome{
				Result: log.Result{
					Tool:    "audit-codex",
					Status:  "PASS",
					Code:    "CODEX_DIR_MISSING",
					Summary: fmt.Sprintf("codex_dir_missing=%s", resolvedCodexSkills),
				},
			}
		}
		return Outcome{
			Result: log.Result{
				Tool:    "audit-codex",
				Status:  "FAIL",
				Code:    "MANIFEST_ERROR",
				Summary: fmt.Sprintf("Failed to read codex skills dir: %v", err),
			},
			ExitCode: 1,
		}
	}

	if len(codexEntries) == 0 {
		return Outcome{
			Result: log.Result{
				Tool:    "audit-codex",
				Status:  "PASS",
				Code:    "CODEX_DIR_EMPTY",
				Summary: fmt.Sprintf("codex_dir_empty=%s", resolvedCodexSkills),
			},
		}
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
			if err := removeAll(target); err != nil {
				attrs = append(attrs, slog.Int("signal.pruned", pruned))
				return Outcome{
					Result: log.Result{
						Tool:    "audit-codex",
						Status:  "FAIL",
						Code:    "PRUNE_FAILED",
						Summary: fmt.Sprintf("Failed to remove %s: %v", target, err),
					},
					Attrs:    attrs,
					ExitCode: 1,
				}
			}
			pruned++
		}
	}

	attrs = append(attrs, slog.Int("signal.pruned", pruned))
	if dryRun {
		attrs = append(attrs, slog.Bool("signal.dry_run", true))
	}

	return Outcome{
		Result: log.Result{
			Tool:   "audit-codex",
			Status: "PASS",
			Code:   "AUDIT_COMPLETE",
			Summary: fmt.Sprintf("codex=%d duplicates=%d managed_duplicates=%d external_duplicates=%d codex_only=%d pruned=%d",
				len(codexEntries), len(duplicates), len(managedDuplicates), len(externalDuplicates), len(codexOnly), pruned),
		},
		Attrs: attrs,
	}
}

// ListSkillDirs returns sorted subdirectory names under dir.
func ListSkillDirs(dir string) ([]string, error) {
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
