package skillbuild

import (
	"bytes"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func testConfig() Config {
	return Config{
		LogPrefix:       "[skills:build]",
		SkillFile:       "SKILL.md",
		ManifestName:    ".dotfiles-managed-skills.json",
		ManifestVersion: 1,
		TemplateSuffix:  ".md.tmpl",
		FragmentSuffix:  ".fragments.json",
		IgnoredNames: map[string]bool{
			"tests": true,
		},
		ScriptReferencePattern: regexp.MustCompile(
			`(?:[^A-Za-z0-9_.\-]|^)(?:<skill-root>/)?(scripts/(?:[A-Za-z0-9][A-Za-z0-9_.\-]*/)*[A-Za-z0-9][A-Za-z0-9_.\-]*\.[A-Za-z0-9][A-Za-z0-9_.\-]*)`,
		),
		ExplicitSkillRootPatterns: []ExplicitSkillRootPattern{
			{
				Re:   regexp.MustCompile(`(?i)\b(?:re-)?run ` + "`" + `(?:bash )?scripts/`),
				Hint: "use <skill-root>/scripts/... for executed helper commands",
			},
			{
				Re:   regexp.MustCompile(`(?i)\b(?:read|load|modify|edit|inspect|use) ` + "`" + `(?:scripts|references)/`),
				Hint: "use <skill-root>/scripts/... or <skill-root>/references/... for skill-relative paths",
			},
		},
		ForbiddenPatterns: []string{
			"../_shared",
			"../../_shared",
		},
		TextSuffixes: map[string]bool{
			".md":   true,
			".sh":   true,
			".txt":  true,
			".json": true,
		},
		DiscoverSkills: func(sourceRoot string) ([]string, error) {
			entries, err := os.ReadDir(sourceRoot)
			if err != nil {
				return nil, err
			}
			var names []string
			for _, e := range entries {
				if !e.IsDir() {
					continue
				}
				if _, err := os.Stat(filepath.Join(sourceRoot, e.Name(), "SKILL.md")); err == nil {
					names = append(names, e.Name())
				}
			}
			return names, nil
		},
		FormatSourceRoot: func(sourceRoot, manifestPath string) string {
			rel, err := filepath.Rel(filepath.Dir(manifestPath), sourceRoot)
			if err != nil {
				return sourceRoot
			}
			if rel == "." {
				return "."
			}
			return filepath.ToSlash(rel)
		},
	}
}

func skillsSourceRoot() string {
	return filepath.Join("..", "..", "..", "..", "src")
}

func TestValidateExplicitSkillRootPaths_SourceTree(t *testing.T) {
	srcRoot := skillsSourceRoot()
	entries, err := os.ReadDir(srcRoot)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}

	cfg := testConfig()
	for _, e := range entries {
		if e.Name() == "tests" || !e.IsDir() {
			continue
		}
		skillRoot := filepath.Join(srcRoot, e.Name())
		if err := ValidateExplicitSkillRootPaths(skillRoot, cfg); err != nil {
			t.Errorf("%s: %v", e.Name(), err)
		}
	}
}

func TestBuildOutputsStandaloneArtifacts(t *testing.T) {
	cfg := testConfig()
	tmp := t.TempDir()
	artifactRoot := filepath.Join(tmp, "artifacts")
	var buf bytes.Buffer
	if err := Build(&buf, cfg, skillsSourceRoot(), artifactRoot, false); err != nil {
		t.Fatalf("Build: %v", err)
	}

	manifestPath := filepath.Join(artifactRoot, ".dotfiles-managed-skills.json")
	if _, err := os.Stat(manifestPath); err != nil {
		t.Fatalf("manifest file missing: %v", err)
	}

	renderedTemplate := filepath.Join(artifactRoot, "design-doc", "references", "design-templates.md")
	content, err := os.ReadFile(renderedTemplate)
	if err != nil {
		t.Fatalf("ReadFile rendered template: %v", err)
	}
	if strings.Contains(string(content), "{{ render_fragment") {
		t.Fatal("rendered template contains unresolved fragment token")
	}
}
