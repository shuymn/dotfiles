package managedskills

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/manifest"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/pathutil"
)

const (
	DefaultManifestName = ".dotfiles-managed-skills.json"
	SkillFileName       = "SKILL.md"
	ManifestVersion     = 1
	LogPrefix           = "[skills:manifest]"
)

var (
	reInvalidChars    = regexp.MustCompile(`[^a-z0-9._]+`)
	reLeadingTrailing = regexp.MustCompile(`^[.-]+|[.-]+$`)
)

const (
	refreshOpSource = "source"
	refreshOpRead   = "read"
	refreshOpJSON   = "json"
	refreshOpMkdir  = "mkdir"
	refreshOpWrite  = "write"
)

// RefreshError reports the stage that failed during manifest refresh.
type RefreshError struct {
	Op   string
	Path string
	Err  error
}

func (e *RefreshError) Error() string {
	if e.Path == "" {
		return fmt.Sprintf("%s: %v", e.Op, e.Err)
	}
	return fmt.Sprintf("%s %s: %v", e.Op, e.Path, e.Err)
}

func (e *RefreshError) Unwrap() error { return e.Err }

// RefreshOptions configures manifest generation.
type RefreshOptions struct {
	Source       string
	ManifestPath string
	Write        bool
}

// RefreshResult is the generated manifest payload and metadata.
type RefreshResult struct {
	ManifestPath  string
	Data          []byte
	ManagedSkills int
}

// RefreshManifest builds the managed skills manifest and optionally writes it.
func RefreshManifest(opts RefreshOptions) (RefreshResult, error) {
	sourceRoot := pathutil.ExpandAndAbs(opts.Source)
	info, err := os.Stat(sourceRoot)
	if err != nil {
		return RefreshResult{}, &RefreshError{Op: refreshOpSource, Path: sourceRoot, Err: err}
	}
	if !info.IsDir() {
		return RefreshResult{}, &RefreshError{Op: refreshOpSource, Path: sourceRoot, Err: errors.New("not a directory")}
	}

	outPath := ResolveManifestPath(sourceRoot, opts.ManifestPath)
	skills, err := DiscoverSkills(sourceRoot)
	if err != nil {
		return RefreshResult{}, &RefreshError{Op: refreshOpRead, Path: sourceRoot, Err: err}
	}

	payload := manifest.ManagedSkillsManifest{
		Version:    ManifestVersion,
		SourceRoot: FormatSourceRoot(sourceRoot, outPath),
		Skills:     skills,
	}

	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return RefreshResult{}, &RefreshError{Op: refreshOpJSON, Path: outPath, Err: err}
	}

	if opts.Write {
		if err := os.MkdirAll(filepath.Dir(outPath), 0755); err != nil {
			return RefreshResult{}, &RefreshError{Op: refreshOpMkdir, Path: outPath, Err: err}
		}
		if err := os.WriteFile(outPath, append(data, '\n'), 0644); err != nil {
			return RefreshResult{}, &RefreshError{Op: refreshOpWrite, Path: outPath, Err: err}
		}
	}

	return RefreshResult{
		ManifestPath:  outPath,
		Data:          data,
		ManagedSkills: len(skills),
	}, nil
}

// ResolveManifestPath expands the output path or falls back to the default.
func ResolveManifestPath(sourceRoot, manifestPath string) string {
	if manifestPath != "" {
		return pathutil.ExpandAndAbs(manifestPath)
	}
	return filepath.Join(sourceRoot, DefaultManifestName)
}

// SanitizeName normalizes a skill directory name for manifest use.
func SanitizeName(name string) string {
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

// DiscoverSkills finds skill directories under sourceRoot.
func DiscoverSkills(sourceRoot string) ([]string, error) {
	entries, err := os.ReadDir(sourceRoot)
	if err != nil {
		return nil, err
	}

	seen := make(map[string]bool)
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		skillFile := filepath.Join(sourceRoot, e.Name(), SkillFileName)
		if _, err := os.Stat(skillFile); err == nil {
			seen[SanitizeName(e.Name())] = true
		}
	}

	names := make([]string, 0, len(seen))
	for name := range seen {
		names = append(names, name)
	}
	sort.Strings(names)
	return names, nil
}

// FormatSourceRoot renders sourceRoot relative to manifestPath when possible.
func FormatSourceRoot(sourceRoot, manifestPath string) string {
	rel, err := filepath.Rel(filepath.Dir(manifestPath), sourceRoot)
	if err != nil {
		return sourceRoot
	}
	if rel == "." {
		return "."
	}
	return filepath.ToSlash(rel)
}
