package skillbuild

import (
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/template"
)

type ExplicitSkillRootPattern struct {
	Re   *regexp.Regexp
	Hint string
}

type Config struct {
	LogPrefix                 string
	SkillFile                 string
	ManifestName              string
	ManifestVersion           int
	TemplateSuffix            string
	FragmentSuffix            string
	IgnoredNames              map[string]bool
	ScriptReferencePattern    *regexp.Regexp
	ExplicitSkillRootPatterns []ExplicitSkillRootPattern
	ForbiddenPatterns         []string
	TextSuffixes              map[string]bool
	DiscoverSkills            func(string) ([]string, error)
	FormatSourceRoot          func(string, string) string
}

// BuildError is returned when the skill build fails.
type BuildError struct {
	msg string
}

func (e *BuildError) Error() string { return e.msg }

func NewBuildError(format string, args ...any) *BuildError {
	return &BuildError{msg: fmt.Sprintf(format, args...)}
}

func Build(w io.Writer, cfg Config, sourceStr, artifactStr string, dryRun bool) error {
	if err := cfg.validate(); err != nil {
		return err
	}

	sourceRoot, err := filepath.Abs(sourceStr)
	if err != nil {
		return err
	}
	artifactRoot, err := filepath.Abs(artifactStr)
	if err != nil {
		return err
	}

	if sourceRoot == artifactRoot {
		return NewBuildError("source and artifact roots must be different")
	}
	displayArtifactRoot := artifactRoot
	if dryRun {
		tmpRoot, err := os.MkdirTemp("", "skit-build-skills-*")
		if err != nil {
			return err
		}
		defer os.RemoveAll(tmpRoot)
		artifactRoot = filepath.Join(tmpRoot, "artifact")
	}
	info, err := os.Stat(sourceRoot)
	if err != nil || !info.IsDir() {
		return NewBuildError("source skills directory does not exist: %s", sourceRoot)
	}

	skillDirs, err := cfg.iterSkillDirs(sourceRoot)
	if err != nil {
		return err
	}

	for _, skillRoot := range skillDirs {
		if err := cfg.validateReferencedScripts(skillRoot); err != nil {
			return err
		}
		if err := cfg.validateNoForbiddenPaths(skillRoot); err != nil {
			return err
		}
		if err := ValidateExplicitSkillRootPaths(skillRoot, cfg); err != nil {
			return err
		}
	}

	if err := cleanArtifactRoot(artifactRoot); err != nil {
		return err
	}

	for _, skillRoot := range skillDirs {
		if err := cfg.copySkill(skillRoot, artifactRoot); err != nil {
			return err
		}
	}

	if err := cfg.writeBuildManifest(artifactRoot); err != nil {
		return err
	}

	if err := cfg.validateArtifactRoot(artifactRoot); err != nil {
		return err
	}

	artifactSkillDirs, err := cfg.iterSkillDirs(artifactRoot)
	if err != nil {
		return err
	}

	fmt.Fprintf(w, "%s source=%s\n", cfg.LogPrefix, sourceRoot)
	fmt.Fprintf(w, "%s artifact=%s\n", cfg.LogPrefix, displayArtifactRoot)
	if dryRun {
		fmt.Fprintf(w, "%s dry_run=true\n", cfg.LogPrefix)
	}
	fmt.Fprintf(w, "%s skills=%d\n", cfg.LogPrefix, len(artifactSkillDirs))
	return nil
}

func ValidateExplicitSkillRootPaths(skillRoot string, cfg Config) error {
	var violations []string
	err := filepath.WalkDir(skillRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		name := d.Name()
		ext := filepath.Ext(name)
		if ext != ".md" && !strings.HasSuffix(name, cfg.TemplateSuffix) {
			return nil
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(skillRoot, path)
		relFwd := filepath.ToSlash(rel)
		for lineno, line := range strings.Split(string(content), "\n") {
			for _, p := range cfg.ExplicitSkillRootPatterns {
				if p.Re.MatchString(line) {
					violations = append(violations, fmt.Sprintf("%s:%d (%s)", relFwd, lineno+1, p.Hint))
					break
				}
			}
		}
		return nil
	})
	if err != nil {
		return err
	}
	if len(violations) > 0 {
		return NewBuildError("%s: bare skill-relative path references remain: %s", filepath.Base(skillRoot), strings.Join(violations, ", "))
	}
	return nil
}

func (cfg Config) validate() error {
	switch {
	case cfg.LogPrefix == "":
		return fmt.Errorf("skillbuild: missing LogPrefix")
	case cfg.SkillFile == "":
		return fmt.Errorf("skillbuild: missing SkillFile")
	case cfg.ManifestName == "":
		return fmt.Errorf("skillbuild: missing ManifestName")
	case cfg.TemplateSuffix == "":
		return fmt.Errorf("skillbuild: missing TemplateSuffix")
	case cfg.FragmentSuffix == "":
		return fmt.Errorf("skillbuild: missing FragmentSuffix")
	case cfg.ScriptReferencePattern == nil:
		return fmt.Errorf("skillbuild: missing ScriptReferencePattern")
	case cfg.DiscoverSkills == nil:
		return fmt.Errorf("skillbuild: missing DiscoverSkills")
	case cfg.FormatSourceRoot == nil:
		return fmt.Errorf("skillbuild: missing FormatSourceRoot")
	}
	return nil
}

func (cfg Config) shouldIgnore(name string) bool {
	if cfg.IgnoredNames[name] {
		return true
	}
	return strings.HasSuffix(name, cfg.TemplateSuffix) ||
		strings.HasSuffix(name, cfg.FragmentSuffix)
}

func (cfg Config) isSkillDir(path string) bool {
	fi, err := os.Stat(path)
	if err != nil || !fi.IsDir() {
		return false
	}
	_, err = os.Stat(filepath.Join(path, cfg.SkillFile))
	return err == nil
}

func (cfg Config) iterSkillDirs(sourceRoot string) ([]string, error) {
	entries, err := os.ReadDir(sourceRoot)
	if err != nil {
		return nil, err
	}
	var dirs []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		p := filepath.Join(sourceRoot, e.Name())
		if cfg.isSkillDir(p) {
			dirs = append(dirs, p)
		}
	}
	sort.Strings(dirs)
	return dirs, nil
}

func cleanArtifactRoot(artifactRoot string) error {
	if err := os.RemoveAll(artifactRoot); err != nil {
		return err
	}
	return os.MkdirAll(artifactRoot, 0o755)
}

func (cfg Config) writeBuildManifest(artifactRoot string) error {
	skills, err := cfg.DiscoverSkills(artifactRoot)
	if err != nil {
		return fmt.Errorf("write manifest: discover skills: %w", err)
	}
	manifestPath := filepath.Join(artifactRoot, cfg.ManifestName)
	m := manifest.ManagedSkillsManifest{
		Version:    cfg.ManifestVersion,
		SourceRoot: cfg.FormatSourceRoot(artifactRoot, manifestPath),
		Skills:     skills,
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return fmt.Errorf("write manifest: marshal: %w", err)
	}
	return os.WriteFile(manifestPath, append(data, '\n'), 0o644)
}

func (cfg Config) validateReferencedScripts(skillRoot string) error {
	skillMd := filepath.Join(skillRoot, cfg.SkillFile)
	content, err := os.ReadFile(skillMd)
	if err != nil {
		return err
	}

	matches := cfg.ScriptReferencePattern.FindAllSubmatch(content, -1)
	refSet := make(map[string]bool)
	for _, m := range matches {
		if len(m) >= 2 {
			refSet[string(m[1])] = true
		}
	}

	var missing, notExecutable []string
	refs := make([]string, 0, len(refSet))
	for r := range refSet {
		refs = append(refs, r)
	}
	sort.Strings(refs)

	for _, ref := range refs {
		scriptPath := filepath.Join(skillRoot, filepath.FromSlash(ref))
		fi, err := os.Stat(scriptPath)
		if err != nil || !fi.Mode().IsRegular() {
			missing = append(missing, ref)
			continue
		}
		if filepath.Ext(scriptPath) == ".sh" && fi.Mode()&0o111 == 0 {
			notExecutable = append(notExecutable, ref)
		}
	}

	skillName := filepath.Base(skillRoot)
	if len(missing) > 0 {
		sort.Strings(missing)
		return NewBuildError("%s: missing scripts referenced by SKILL.md: %s", skillName, strings.Join(missing, ", "))
	}
	if len(notExecutable) > 0 {
		sort.Strings(notExecutable)
		return NewBuildError("%s: shell scripts must be executable: %s", skillName, strings.Join(notExecutable, ", "))
	}
	return nil
}

func (cfg Config) iterTextFiles(root string) ([]string, error) {
	var files []string
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		name := d.Name()
		ext := filepath.Ext(name)
		if cfg.TextSuffixes[ext] || name == cfg.SkillFile || strings.HasSuffix(name, cfg.TemplateSuffix) {
			files = append(files, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Strings(files)
	return files, nil
}

func (cfg Config) validateNoForbiddenPaths(skillRoot string) error {
	files, err := cfg.iterTextFiles(skillRoot)
	if err != nil {
		return err
	}
	var violations []string
	for _, path := range files {
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		s := string(content)
		rel, _ := filepath.Rel(skillRoot, path)
		for _, pattern := range cfg.ForbiddenPatterns {
			if strings.Contains(s, pattern) {
				violations = append(violations, rel+":"+pattern)
			}
		}
	}
	if len(violations) > 0 {
		return NewBuildError("%s: forbidden path traversal references remain: %s", filepath.Base(skillRoot), strings.Join(violations, ", "))
	}
	return nil
}

func (cfg Config) copySkill(sourceSkillRoot, artifactRoot string) error {
	skillName := filepath.Base(sourceSkillRoot)
	artifactSkillRoot := filepath.Join(artifactRoot, skillName)

	if err := filepath.WalkDir(sourceSkillRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(sourceSkillRoot, path)
		parts := strings.SplitN(rel, string(filepath.Separator), 2)
		if cfg.shouldIgnore(parts[0]) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			if rel == "." {
				return nil
			}
			if cfg.shouldIgnore(d.Name()) {
				return filepath.SkipDir
			}
			return nil
		}
		if cfg.shouldIgnore(d.Name()) {
			return nil
		}
		dst := filepath.Join(artifactSkillRoot, rel)
		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			return err
		}
		return copyFile(path, dst)
	}); err != nil {
		return err
	}

	if err := cfg.renderStructuredTemplates(sourceSkillRoot, artifactSkillRoot); err != nil {
		return NewBuildError("%s: %v", skillName, err)
	}

	return nil
}

func copyFile(src, dst string) error {
	srcFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer srcFile.Close()

	srcInfo, err := srcFile.Stat()
	if err != nil {
		return err
	}

	dstFile, err := os.OpenFile(dst, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, srcInfo.Mode())
	if err != nil {
		return err
	}
	defer dstFile.Close()

	_, err = io.Copy(dstFile, srcFile)
	return err
}

func (cfg Config) renderStructuredTemplates(sourceSkillRoot, artifactSkillRoot string) error {
	var templates []string
	err := filepath.WalkDir(sourceSkillRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() && strings.HasSuffix(d.Name(), cfg.TemplateSuffix) {
			templates = append(templates, path)
		}
		return nil
	})
	if err != nil {
		return err
	}
	sort.Strings(templates)

	for _, tmplPath := range templates {
		rendered, err := template.RenderStructuredTemplate(tmplPath)
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(sourceSkillRoot, tmplPath)
		relOut := strings.TrimSuffix(rel, ".tmpl")
		dstPath := filepath.Join(artifactSkillRoot, relOut)
		if err := os.MkdirAll(filepath.Dir(dstPath), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(dstPath, []byte(rendered), 0o644); err != nil {
			return err
		}
	}
	return nil
}

func (cfg Config) validateArtifactRoot(artifactRoot string) error {
	var leakedPaths, tokenPaths []string
	err := filepath.WalkDir(artifactRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		name := d.Name()
		if cfg.shouldIgnore(name) {
			rel, _ := filepath.Rel(artifactRoot, path)
			leakedPaths = append(leakedPaths, rel)
		}
		if !d.IsDir() && filepath.Ext(name) == ".md" {
			content, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			s := string(content)
			if strings.Contains(s, "{{") || strings.Contains(s, "}}") {
				rel, _ := filepath.Rel(artifactRoot, path)
				tokenPaths = append(tokenPaths, filepath.ToSlash(rel))
			}
		}
		return nil
	})
	if err != nil {
		return err
	}
	if len(leakedPaths) > 0 {
		sort.Strings(leakedPaths)
		return NewBuildError("artifact tree contains source-only files: %s", strings.Join(leakedPaths, ", "))
	}
	if len(tokenPaths) > 0 {
		sort.Strings(tokenPaths)
		return NewBuildError("artifact tree contains unresolved template tokens: %s", strings.Join(tokenPaths, ", "))
	}

	skillDirs, err := cfg.iterSkillDirs(artifactRoot)
	if err != nil {
		return err
	}
	for _, skillRoot := range skillDirs {
		if err := cfg.validateReferencedScripts(skillRoot); err != nil {
			return err
		}
		if err := cfg.validateNoForbiddenPaths(skillRoot); err != nil {
			return err
		}
		if err := ValidateExplicitSkillRootPaths(skillRoot, cfg); err != nil {
			return err
		}
	}
	return nil
}
