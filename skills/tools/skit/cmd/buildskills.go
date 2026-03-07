package cmd

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"skit/internal/cli"
	"skit/internal/manifest"
	skittemplate "skit/internal/template"
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

// BuildError is returned when the skill build fails.
type BuildError struct {
	msg string
}

func (e *BuildError) Error() string { return e.msg }

func buildErr(format string, args ...any) *BuildError {
	return &BuildError{msg: fmt.Sprintf(format, args...)}
}

// BuildSkills returns the build-skills subcommand.
func BuildSkills() *cli.Command {
	return &cli.Command{
		Name:        buildSkillsTool,
		Description: "Build standalone skill artifacts from a source tree",
		Run: func(args []string) int {
			return runBuildSkills(os.Stdout, args)
		},
	}
}

func runBuildSkills(w io.Writer, args []string) int {
	fs := flag.NewFlagSet(buildSkillsTool, flag.ContinueOnError)
	source := fs.String("source", "", "Path to the source skills root (required)")
	artifact := fs.String("artifact", "", "Path to the artifact skills root (required)")

	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 1
	}
	if *source == "" || *artifact == "" {
		fmt.Fprintln(os.Stderr, "usage: skit build-skills --source <path> --artifact <path>")
		return 1
	}

	if err := buildSkills(w, *source, *artifact); err != nil {
		fmt.Fprintf(os.Stderr, "build-skills: %v\n", err)
		return 1
	}
	return 0
}

func buildSkills(w io.Writer, sourceStr, artifactStr string) error {
	sourceRoot, err := filepath.Abs(sourceStr)
	if err != nil {
		return err
	}
	artifactRoot, err := filepath.Abs(artifactStr)
	if err != nil {
		return err
	}

	if sourceRoot == artifactRoot {
		return buildErr("source and artifact roots must be different")
	}
	info, err := os.Stat(sourceRoot)
	if err != nil || !info.IsDir() {
		return buildErr("source skills directory does not exist: %s", sourceRoot)
	}

	skillDirs, err := iterSkillDirs(sourceRoot)
	if err != nil {
		return err
	}

	for _, skillRoot := range skillDirs {
		if err := validateReferencedScripts(skillRoot); err != nil {
			return err
		}
		if err := validateNoForbiddenPaths(skillRoot); err != nil {
			return err
		}
		if err := validateExplicitSkillRootPaths(skillRoot); err != nil {
			return err
		}
	}

	if err := cleanArtifactRoot(artifactRoot); err != nil {
		return err
	}

	for _, skillRoot := range skillDirs {
		if err := copySkill(skillRoot, artifactRoot); err != nil {
			return err
		}
	}

	if err := writeBuildManifest(artifactRoot); err != nil {
		return err
	}

	if err := validateArtifactRoot(artifactRoot); err != nil {
		return err
	}

	artifactSkillDirs, err := iterSkillDirs(artifactRoot)
	if err != nil {
		return err
	}

	fmt.Fprintf(w, "%s source=%s\n", buildSkillsLogPrefix, sourceRoot)
	fmt.Fprintf(w, "%s artifact=%s\n", buildSkillsLogPrefix, artifactRoot)
	fmt.Fprintf(w, "%s skills=%d\n", buildSkillsLogPrefix, len(artifactSkillDirs))
	return nil
}

func buildSkillsShouldIgnore(name string) bool {
	if buildSkillsIgnoredNames[name] {
		return true
	}
	return strings.HasSuffix(name, buildSkillsTmplSuffix) ||
		strings.HasSuffix(name, buildSkillsFragSuffix)
}

func isSkillDir(path string) bool {
	fi, err := os.Stat(path)
	if err != nil || !fi.IsDir() {
		return false
	}
	_, err = os.Stat(filepath.Join(path, buildSkillsSkillFile))
	return err == nil
}

func iterSkillDirs(sourceRoot string) ([]string, error) {
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
		if isSkillDir(p) {
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
	return os.MkdirAll(artifactRoot, 0755)
}

func writeBuildManifest(artifactRoot string) error {
	skills, err := discoverSkills(artifactRoot)
	if err != nil {
		return fmt.Errorf("write manifest: discover skills: %w", err)
	}
	manifestPath := filepath.Join(artifactRoot, buildSkillsManifestName)
	m := manifest.ManagedSkillsManifest{
		Version:    manifestRefreshVersion,
		SourceRoot: formatSourceRoot(artifactRoot, manifestPath),
		Skills:     skills,
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return fmt.Errorf("write manifest: marshal: %w", err)
	}
	return os.WriteFile(manifestPath, append(data, '\n'), 0644)
}

func validateReferencedScripts(skillRoot string) error {
	skillMd := filepath.Join(skillRoot, buildSkillsSkillFile)
	content, err := os.ReadFile(skillMd)
	if err != nil {
		return err
	}

	matches := buildSkillsScriptRefPattern.FindAllSubmatch(content, -1)
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
		if filepath.Ext(scriptPath) == ".sh" {
			if fi.Mode()&0111 == 0 {
				notExecutable = append(notExecutable, ref)
			}
		}
	}

	skillName := filepath.Base(skillRoot)
	if len(missing) > 0 {
		sort.Strings(missing)
		return buildErr("%s: missing scripts referenced by SKILL.md: %s", skillName, strings.Join(missing, ", "))
	}
	if len(notExecutable) > 0 {
		sort.Strings(notExecutable)
		return buildErr("%s: shell scripts must be executable: %s", skillName, strings.Join(notExecutable, ", "))
	}
	return nil
}

func iterTextFiles(root string) ([]string, error) {
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
		if buildSkillsTextSuffixes[ext] || name == buildSkillsSkillFile || strings.HasSuffix(name, buildSkillsTmplSuffix) {
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

func validateNoForbiddenPaths(skillRoot string) error {
	files, err := iterTextFiles(skillRoot)
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
		for _, pattern := range buildSkillsForbiddenPatterns {
			if strings.Contains(s, pattern) {
				violations = append(violations, rel+":"+pattern)
			}
		}
	}
	if len(violations) > 0 {
		return buildErr("%s: forbidden path traversal references remain: %s", filepath.Base(skillRoot), strings.Join(violations, ", "))
	}
	return nil
}

func validateExplicitSkillRootPaths(skillRoot string) error {
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
		if ext != ".md" && !strings.HasSuffix(name, buildSkillsTmplSuffix) {
			return nil
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(skillRoot, path)
		relFwd := filepath.ToSlash(rel)
		for lineno, line := range strings.Split(string(content), "\n") {
			for _, p := range buildSkillsExplicitSkillRootPatterns {
				if p.re.MatchString(line) {
					violations = append(violations, fmt.Sprintf("%s:%d (%s)", relFwd, lineno+1, p.hint))
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
		return buildErr("%s: bare skill-relative path references remain: %s", filepath.Base(skillRoot), strings.Join(violations, ", "))
	}
	return nil
}

func copySkill(sourceSkillRoot, artifactRoot string) error {
	skillName := filepath.Base(sourceSkillRoot)
	artifactSkillRoot := filepath.Join(artifactRoot, skillName)

	// Copy skill tree, skipping ignored entries.
	if err := filepath.WalkDir(sourceSkillRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(sourceSkillRoot, path)
		parts := strings.SplitN(rel, string(filepath.Separator), 2)
		if buildSkillsShouldIgnore(parts[0]) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			if rel == "." {
				return nil
			}
			if buildSkillsShouldIgnore(d.Name()) {
				return filepath.SkipDir
			}
			return nil
		}
		if buildSkillsShouldIgnore(d.Name()) {
			return nil
		}
		dst := filepath.Join(artifactSkillRoot, rel)
		if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
			return err
		}
		return copyFile(path, dst)
	}); err != nil {
		return err
	}

	// Render structured templates.
	if err := renderStructuredTemplates(sourceSkillRoot, artifactSkillRoot); err != nil {
		return buildErr("%s: %v", skillName, err)
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

func renderStructuredTemplates(sourceSkillRoot, artifactSkillRoot string) error {
	var templates []string
	err := filepath.WalkDir(sourceSkillRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() && strings.HasSuffix(d.Name(), buildSkillsTmplSuffix) {
			templates = append(templates, path)
		}
		return nil
	})
	if err != nil {
		return err
	}
	sort.Strings(templates)

	for _, tmplPath := range templates {
		rendered, err := skittemplate.RenderStructuredTemplate(tmplPath)
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(sourceSkillRoot, tmplPath)
		// Strip .tmpl suffix: design-templates.md.tmpl → design-templates.md
		relOut := strings.TrimSuffix(rel, ".tmpl")
		dstPath := filepath.Join(artifactSkillRoot, relOut)
		if err := os.MkdirAll(filepath.Dir(dstPath), 0755); err != nil {
			return err
		}
		if err := os.WriteFile(dstPath, []byte(rendered), 0644); err != nil {
			return err
		}
	}
	return nil
}

func validateArtifactRoot(artifactRoot string) error {
	// Single walk: check for leaked source-only files and unresolved template tokens.
	var leakedPaths, tokenPaths []string
	err := filepath.WalkDir(artifactRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		name := d.Name()
		if buildSkillsShouldIgnore(name) {
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
		return buildErr("artifact tree contains source-only files: %s", strings.Join(leakedPaths, ", "))
	}
	if len(tokenPaths) > 0 {
		sort.Strings(tokenPaths)
		return buildErr("artifact tree contains unresolved template tokens: %s", strings.Join(tokenPaths, ", "))
	}

	// Validate individual skill dirs.
	skillDirs, err := iterSkillDirs(artifactRoot)
	if err != nil {
		return err
	}
	for _, skillRoot := range skillDirs {
		if err := validateReferencedScripts(skillRoot); err != nil {
			return err
		}
		if err := validateNoForbiddenPaths(skillRoot); err != nil {
			return err
		}
		if err := validateExplicitSkillRootPaths(skillRoot); err != nil {
			return err
		}
	}
	return nil
}
