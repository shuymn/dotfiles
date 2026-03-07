package cmd

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// skillsSourceRoot returns the skills/src directory relative to this test.
func skillsSourceRoot() string {
	return filepath.Join("..", "..", "..", "src")
}

type fileSnapshot struct {
	digest string
	mode   fs.FileMode
}

func snapshotTree(t *testing.T, root string) map[string]fileSnapshot {
	t.Helper()
	snap := make(map[string]fileSnapshot)
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(root, path)
		rel = filepath.ToSlash(rel)
		if d.IsDir() {
			snap[rel+"/"] = fileSnapshot{}
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		snap[rel] = fileSnapshot{
			digest: fmt.Sprintf("%x", sha256.Sum256(data)),
			mode:   info.Mode() & 0o777,
		}
		return nil
	})
	if err != nil {
		t.Fatalf("snapshotTree: %v", err)
	}
	return snap
}

func buildToTempDir(t *testing.T) string {
	t.Helper()
	tmp := t.TempDir()
	artifactRoot := filepath.Join(tmp, "artifacts")
	var buf bytes.Buffer
	if err := buildSkills(&buf, skillsSourceRoot(), artifactRoot); err != nil {
		t.Fatalf("buildSkills: %v", err)
	}
	return artifactRoot
}

func TestSourceSkillsHaveNoParentTraversalHelperRefs(t *testing.T) {
	srcRoot := skillsSourceRoot()
	entries, err := os.ReadDir(srcRoot)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}

	for _, e := range entries {
		if e.Name() == "common" || e.Name() == "tests" || !e.IsDir() {
			continue
		}
		skillRoot := filepath.Join(srcRoot, e.Name())

		// Must not have scripts/lib sub-dir directly.
		libPath := filepath.Join(skillRoot, "scripts", "lib")
		if _, err := os.Stat(libPath); err == nil {
			t.Errorf("%s: unexpected scripts/lib directory", e.Name())
		}

		// Check for forbidden patterns in text files.
		forbidden := []string{"../../common/scripts/", "../_shared", "../../_shared"}
		err := filepath.WalkDir(skillRoot, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				return nil
			}
			ext := filepath.Ext(d.Name())
			switch ext {
			case ".md", ".sh", ".txt":
			default:
				return nil
			}
			data, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			s := string(data)
			for _, pattern := range forbidden {
				if strings.Contains(s, pattern) {
					t.Errorf("%s: forbidden pattern %q in %s", e.Name(), pattern, path)
				}
			}
			return nil
		})
		if err != nil {
			t.Errorf("WalkDir %s: %v", e.Name(), err)
		}
	}

	// Verify expected common lib files exist.
	for _, name := range []string{"llm-check-output.sh", "path-display.sh"} {
		p := filepath.Join(srcRoot, "common", "scripts", "lib", name)
		if _, err := os.Stat(p); err != nil {
			t.Errorf("expected common lib file: %s", p)
		}
	}
}

func TestSourceMarkdownUsesExplicitSkillRootForRuntimeRefs(t *testing.T) {
	srcRoot := skillsSourceRoot()
	entries, err := os.ReadDir(srcRoot)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}

	for _, e := range entries {
		if e.Name() == "common" || e.Name() == "tests" || !e.IsDir() {
			continue
		}
		skillRoot := filepath.Join(srcRoot, e.Name())
		if err := validateExplicitSkillRootPaths(skillRoot); err != nil {
			t.Errorf("%s: %v", e.Name(), err)
		}
	}
}

func TestBuildOutputsStandaloneArtifacts(t *testing.T) {
	artifactRoot := buildToTempDir(t)

	// Manifest file must exist.
	manifestPath := filepath.Join(artifactRoot, ".dotfiles-managed-skills.json")
	if _, err := os.Stat(manifestPath); err != nil {
		t.Errorf("manifest file missing: %v", err)
	}

	// _shared must not exist.
	if _, err := os.Stat(filepath.Join(artifactRoot, "_shared")); err == nil {
		t.Error("_shared directory exists in artifact root")
	}

	// tests and __pycache__ must not exist.
	for _, name := range []string{"tests", "__pycache__"} {
		matches, _ := filepath.Glob(filepath.Join(artifactRoot, "*", name))
		if len(matches) > 0 {
			t.Errorf("found %s in artifact: %v", name, matches)
		}
	}

	// No .md.tmpl files.
	err := filepath.WalkDir(artifactRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if strings.HasSuffix(d.Name(), ".md.tmpl") {
			t.Errorf("found .md.tmpl in artifact: %s", path)
		}
		if strings.HasSuffix(d.Name(), ".fragments.json") {
			t.Errorf("found .fragments.json in artifact: %s", path)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("WalkDir: %v", err)
	}

	// Specific artifact checks.
	checkExists := []string{
		filepath.Join(artifactRoot, "design-doc", "scripts", "gate-check.sh"),
		filepath.Join(artifactRoot, "setup-ralph", "scripts", "gate-check.sh"),
		filepath.Join(artifactRoot, "design-doc", "scripts", "lib", "llm-check-output.sh"),
		filepath.Join(artifactRoot, "design-doc", "scripts", "lib", "path-display.sh"),
	}
	for _, p := range checkExists {
		if _, err := os.Stat(p); err != nil {
			t.Errorf("expected artifact file missing: %s", p)
		}
	}

	checkNotExists := []string{
		filepath.Join(artifactRoot, "design-doc", "scripts", "split-check.sh"),
		filepath.Join(artifactRoot, "design-doc", "scripts", "llm-check-output.sh"),
		filepath.Join(artifactRoot, "design-doc", "scripts", "path-display.sh"),
		filepath.Join(artifactRoot, "design-doc", "skill.json"),
	}
	for _, p := range checkNotExists {
		if _, err := os.Stat(p); err == nil {
			t.Errorf("expected path to not exist: %s", p)
		}
	}

	// Rendered template file.
	renderedTemplate := filepath.Join(artifactRoot, "design-doc", "references", "design-templates.md")
	if _, err := os.Stat(renderedTemplate); err != nil {
		t.Errorf("rendered template missing: %v", err)
	}
	content, err := os.ReadFile(renderedTemplate)
	if err != nil {
		t.Fatalf("ReadFile rendered template: %v", err)
	}
	s := string(content)
	if strings.Contains(s, "{{ render_fragment") {
		t.Error("rendered template contains unresolved {{ render_fragment")
	}
	if !strings.Contains(s, "## Clarifications") {
		t.Error("rendered template missing ## Clarifications")
	}
	if !strings.Contains(s, "| Question") {
		t.Error("rendered template missing | Question")
	}
}

func TestBuildIsIdempotent(t *testing.T) {
	artifactRoot := buildToTempDir(t)
	first := snapshotTree(t, artifactRoot)

	var buf bytes.Buffer
	if err := buildSkills(&buf, skillsSourceRoot(), artifactRoot); err != nil {
		t.Fatalf("second buildSkills: %v", err)
	}
	second := snapshotTree(t, artifactRoot)

	if len(first) != len(second) {
		t.Errorf("snapshot size changed: %d → %d", len(first), len(second))
	}
	for path, snap1 := range first {
		snap2, ok := second[path]
		if !ok {
			t.Errorf("path disappeared after second build: %s", path)
			continue
		}
		if snap1.digest != snap2.digest {
			t.Errorf("digest changed for %s", path)
		}
		if snap1.mode != snap2.mode {
			t.Errorf("mode changed for %s: %o → %o", path, snap1.mode, snap2.mode)
		}
	}
	for path := range second {
		if _, ok := first[path]; !ok {
			t.Errorf("new path appeared after second build: %s", path)
		}
	}
}

func TestBuiltShellScriptsAreExecutable(t *testing.T) {
	artifactRoot := buildToTempDir(t)

	targetScripts := map[string]bool{
		"digest-stamp.sh": true,
		"gate-check.sh":   true,
	}

	var found []string
	err := filepath.WalkDir(artifactRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() && targetScripts[d.Name()] {
			found = append(found, path)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("WalkDir: %v", err)
	}

	if len(found) == 0 {
		t.Fatal("no target shell scripts found in artifact")
	}

	for _, path := range found {
		info, err := os.Stat(path)
		if err != nil {
			t.Errorf("Stat %s: %v", path, err)
			continue
		}
		if info.Mode()&0o111 == 0 {
			t.Errorf("shell script not executable: %s (mode %o)", path, info.Mode())
		}
	}
}
