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
		FormatSourcePath: func(sourceRoot, sourcePath string) string {
			rel, err := filepath.Rel(sourceRoot, sourcePath)
			if err != nil {
				return sourcePath
			}
			return filepath.ToSlash(filepath.Join("src", rel))
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

	// design-doc is excluded by .syncignore so it must not appear in the artifact.
	if _, err := os.Stat(filepath.Join(artifactRoot, "design-doc")); err == nil {
		t.Fatal("design-doc (syncignore-excluded skill) found in artifact root")
	}
}

func TestBuildExcludedSkillsAbsentFromArtifacts(t *testing.T) {
	cfg := testConfig()

	// Pick a skill not already excluded by .syncignore so we can verify --exclude logging.
	srcRoot := skillsSourceRoot()
	syncIgnored, err := ParseSyncIgnore(srcRoot)
	if err != nil {
		t.Fatalf("ParseSyncIgnore: %v", err)
	}
	entries, err := os.ReadDir(srcRoot)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}
	var targetSkill string
	for _, e := range entries {
		if e.IsDir() && e.Name() != "tests" && !syncIgnored[e.Name()] {
			targetSkill = e.Name()
			break
		}
	}
	if targetSkill == "" {
		t.Fatal("no skill found in source tree outside .syncignore")
	}

	cfg.ExcludedSkills = map[string]bool{targetSkill: true}

	tmp := t.TempDir()
	artifactRoot := filepath.Join(tmp, "artifacts")
	var buf bytes.Buffer
	if err := Build(&buf, cfg, srcRoot, artifactRoot, false); err != nil {
		t.Fatalf("Build: %v", err)
	}

	// Excluded skill must not appear in artifact directory.
	if _, err := os.Stat(filepath.Join(artifactRoot, targetSkill)); err == nil {
		t.Errorf("excluded skill %q found in artifact root", targetSkill)
	}

	// Excluded skill must not appear in manifest.
	manifestPath := filepath.Join(artifactRoot, ".dotfiles-managed-skills.json")
	manifestData, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatalf("ReadFile manifest: %v", err)
	}
	if strings.Contains(string(manifestData), `"`+targetSkill+`"`) {
		t.Errorf("excluded skill %q found in manifest", targetSkill)
	}

	// Log must contain the excluded entry.
	logOutput := buf.String()
	expectedLog := "excluded=" + targetSkill + " (reason=--exclude)"
	if !strings.Contains(logOutput, expectedLog) {
		t.Errorf("expected log to contain %q, got:\n%s", expectedLog, logOutput)
	}
}

func TestInjectMarkdownNoticePreservesFrontmatter(t *testing.T) {
	got := injectMarkdownNotice("---\nname: test\n---\nbody\n", "<!-- do not edit -->")
	want := "---\nname: test\n---\n\n<!-- do not edit -->\n\nbody\n"
	if got != want {
		t.Fatalf("injectMarkdownNotice frontmatter mismatch\nwant:\n%s\ngot:\n%s", want, got)
	}
}

func TestInjectMarkdownNoticePrependsWithoutFrontmatter(t *testing.T) {
	got := injectMarkdownNotice("# title\n", "<!-- do not edit -->")
	want := "<!-- do not edit -->\n\n# title\n"
	if got != want {
		t.Fatalf("injectMarkdownNotice plain markdown mismatch\nwant:\n%s\ngot:\n%s", want, got)
	}
}
