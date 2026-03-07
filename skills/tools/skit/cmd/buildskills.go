package cmd

import (
	"context"
	"fmt"
	"io"
	"regexp"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/skillbuild"
)

const (
	buildSkillsTool         = "build-skills"
	buildSkillsLogPrefix    = "[skills:build]"
	buildSkillsSkillFile    = "SKILL.md"
	buildSkillsManifestName = ".dotfiles-managed-skills.json"
	buildSkillsTmplSuffix   = ".md.tmpl"
	buildSkillsFragSuffix   = ".fragments.json"
)

var (
	buildSkillsIgnoredNames = map[string]bool{
		"tests": true,
	}

	// SCRIPT_REFERENCE_PATTERN matches script references in SKILL.md.
	buildSkillsScriptRefPattern = regexp.MustCompile(
		`(?:[^A-Za-z0-9_.\-]|^)(?:<skill-root>/)?(scripts/(?:[A-Za-z0-9][A-Za-z0-9_.\-]*/)*[A-Za-z0-9][A-Za-z0-9_.\-]*\.[A-Za-z0-9][A-Za-z0-9_.\-]*)`,
	)

	// EXPLICIT_SKILL_ROOT_PATTERNS detects bare path references in markdown.
	buildSkillsExplicitSkillRootPatterns = []struct {
		re   *regexp.Regexp
		hint string
	}{
		{
			regexp.MustCompile(`(?i)\b(?:re-)?run ` + "`" + `(?:bash )?scripts/`),
			"use <skill-root>/scripts/... for executed helper commands",
		},
		{
			regexp.MustCompile(`(?i)\b(?:read|load|modify|edit|inspect|use) ` + "`" + `(?:scripts|references)/`),
			"use <skill-root>/scripts/... or <skill-root>/references/... for skill-relative paths",
		},
	}

	buildSkillsForbiddenPatterns = []string{
		"../_shared",
		"../../_shared",
	}

	buildSkillsTextSuffixes = map[string]bool{
		".md":   true,
		".sh":   true,
		".txt":  true,
		".json": true,
	}
)

// BuildSkills returns the build-skills subcommand.
func BuildSkills() *cli.Command {
	c := cli.NewCommand(buildSkillsTool, "Build standalone skill artifacts from a source tree")
	c.EnableDryRun()
	var source, artifact string
	c.StringVar(&source, "source", "", "", "Path to the source skills root (required)")
	c.StringVar(&artifact, "artifact", "", "", "Path to the artifact skills root (required)")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if source == "" || artifact == "" {
			return fmt.Errorf("--source and --artifact are required")
		}
		return exitCode(runBuildSkills(s.Stdout, s.Stderr, source, artifact, s.DryRun))
	}
	return c
}

func runBuildSkills(w, stderr io.Writer, source, artifact string, dryRun bool) int {
	if err := buildSkills(w, source, artifact, dryRun); err != nil {
		fmt.Fprintf(stderr, "build-skills: %v\n", err)
		return 1
	}
	return 0
}

func buildSkills(w io.Writer, sourceStr, artifactStr string, dryRun bool) error {
	return skillbuild.Build(w, buildSkillsConfig(), sourceStr, artifactStr, dryRun)
}

func validateExplicitSkillRootPaths(skillRoot string) error {
	return skillbuild.ValidateExplicitSkillRootPaths(skillRoot, buildSkillsConfig())
}

func buildSkillsConfig() skillbuild.Config {
	patterns := make([]skillbuild.ExplicitSkillRootPattern, 0, len(buildSkillsExplicitSkillRootPatterns))
	for _, p := range buildSkillsExplicitSkillRootPatterns {
		patterns = append(patterns, skillbuild.ExplicitSkillRootPattern{
			Re:   p.re,
			Hint: p.hint,
		})
	}

	return skillbuild.Config{
		LogPrefix:                 buildSkillsLogPrefix,
		SkillFile:                 buildSkillsSkillFile,
		ManifestName:              buildSkillsManifestName,
		ManifestVersion:           manifestRefreshVersion,
		TemplateSuffix:            buildSkillsTmplSuffix,
		FragmentSuffix:            buildSkillsFragSuffix,
		IgnoredNames:              buildSkillsIgnoredNames,
		ScriptReferencePattern:    buildSkillsScriptRefPattern,
		ExplicitSkillRootPatterns: patterns,
		ForbiddenPatterns:         buildSkillsForbiddenPatterns,
		TextSuffixes:              buildSkillsTextSuffixes,
		DiscoverSkills:            discoverSkills,
		FormatSourceRoot:          formatSourceRoot,
	}
}
