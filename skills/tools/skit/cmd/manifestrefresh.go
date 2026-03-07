package cmd

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"skit/internal/cli"
	"skit/internal/manifest"
	"skit/internal/pathutil"
)

const (
	manifestRefreshTool        = "manifest-refresh"
	manifestRefreshDefaultName = ".dotfiles-managed-skills.json"
	manifestRefreshSkillFile   = "SKILL.md"
	manifestRefreshVersion     = 1
	manifestRefreshLogPrefix   = "[skills:manifest]"
)

var (
	reInvalidChars    = regexp.MustCompile(`[^a-z0-9._]+`)
	reLeadingTrailing = regexp.MustCompile(`^[.-]+|[.-]+$`)
)

// ManifestRefresh returns the manifest-refresh subcommand.
func ManifestRefresh() *cli.Command {
	return &cli.Command{
		Name:        manifestRefreshTool,
		Description: "Refresh the dotfiles-managed skills manifest from a local skills source",
		Run: func(args []string) int {
			return runManifestRefresh(os.Stdout, args)
		},
	}
}

func runManifestRefresh(w io.Writer, args []string) int {
	fs := flag.NewFlagSet(manifestRefreshTool, flag.ContinueOnError)
	source := fs.String("source", "", "Path to the local skills source root (required)")
	manifestPath := fs.String("manifest", "", "Manifest output path (default: <source>/.dotfiles-managed-skills.json)")
	printOnly := fs.Bool("print-only", false, "Print the generated manifest instead of writing it")

	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 1
	}

	if *source == "" {
		fmt.Fprintln(os.Stderr, "usage: skit manifest-refresh --source <path> [--manifest <path>] [--print-only]")
		return 1
	}

	sourceRoot := pathutil.ExpandAndAbs(*source)

	info, err := os.Stat(sourceRoot)
	if err != nil || !info.IsDir() {
		fmt.Fprintf(os.Stderr, "manifest-refresh: source skills directory does not exist: %s\n", sourceRoot)
		return 1
	}

	var outPath string
	if *manifestPath != "" {
		outPath = pathutil.ExpandAndAbs(*manifestPath)
	} else {
		outPath = filepath.Join(sourceRoot, manifestRefreshDefaultName)
	}

	skills, err := discoverSkills(sourceRoot)
	if err != nil {
		fmt.Fprintf(os.Stderr, "manifest-refresh: failed to discover skills: %v\n", err)
		return 1
	}

	m := manifest.ManagedSkillsManifest{
		Version:    manifestRefreshVersion,
		SourceRoot: formatSourceRoot(sourceRoot, outPath),
		Skills:     skills,
	}

	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "manifest-refresh: failed to marshal manifest: %v\n", err)
		return 1
	}

	if *printOnly {
		fmt.Fprintf(w, "%s\n", data)
		return 0
	}

	if err := os.MkdirAll(filepath.Dir(outPath), 0755); err != nil {
		fmt.Fprintf(os.Stderr, "manifest-refresh: failed to create manifest directory: %v\n", err)
		return 1
	}
	if err := os.WriteFile(outPath, append(data, '\n'), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "manifest-refresh: failed to write manifest: %v\n", err)
		return 1
	}

	fmt.Fprintf(w, "%s manifest_path=%s\n", manifestRefreshLogPrefix, outPath)
	fmt.Fprintf(w, "%s managed_skills=%d\n", manifestRefreshLogPrefix, len(skills))
	return 0
}

func sanitizeName(name string) string {
	s := reInvalidChars.ReplaceAllString(strings.ToLower(name), "-")
	s = reLeadingTrailing.ReplaceAllString(s, "")
	if len(s) > 255 {
		s = s[:255]
	}
	if s == "" {
		return "unnamed-skill"
	}
	return s
}

func discoverSkills(sourceRoot string) ([]string, error) {
	entries, err := os.ReadDir(sourceRoot)
	if err != nil {
		return nil, err
	}

	seen := make(map[string]bool)
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		skillFile := filepath.Join(sourceRoot, e.Name(), manifestRefreshSkillFile)
		if _, err := os.Stat(skillFile); err == nil {
			seen[sanitizeName(e.Name())] = true
		}
	}

	names := make([]string, 0, len(seen))
	for name := range seen {
		names = append(names, name)
	}
	sort.Strings(names)
	return names, nil
}

func formatSourceRoot(sourceRoot, manifestPath string) string {
	rel, err := filepath.Rel(filepath.Dir(manifestPath), sourceRoot)
	if err != nil {
		return sourceRoot
	}
	if rel == "." {
		return "."
	}
	return filepath.ToSlash(rel)
}
