package pathutil

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// DisplayPath returns a human-friendly display path.
// Priority: git-root relative -> CWD relative -> HOME relative -> absolute.
func DisplayPath(rawPath string) string {
	if rawPath == "" {
		return ""
	}
	if !filepath.IsAbs(rawPath) {
		return rawPath
	}

	physical := canonicalize(rawPath)
	physicalCwd, _ := filepath.EvalSymlinks(".")
	if physicalCwd == "" {
		physicalCwd, _ = os.Getwd()
	}

	// Try git root relative.
	baseDir := physical
	if info, err := os.Stat(baseDir); err != nil || !info.IsDir() {
		baseDir = filepath.Dir(physical)
	}
	if gitRoot, err := gitToplevel(baseDir); err == nil && gitRoot != "" {
		if physical == gitRoot {
			return "."
		}
		if rel, ok := trimPrefix(physical, gitRoot); ok {
			return rel
		}
	}

	// Try CWD relative.
	if physicalCwd != "" {
		if physical == physicalCwd {
			return "."
		}
		if rel, ok := trimPrefix(physical, physicalCwd); ok {
			return rel
		}
	}

	// Try HOME relative.
	if home := os.Getenv("HOME"); home != "" {
		if physical == home {
			return "~"
		}
		if rel, ok := trimPrefix(physical, home); ok {
			return "~/" + rel
		}
	}

	return physical
}

func canonicalize(rawPath string) string {
	if rawPath == "" || !filepath.IsAbs(rawPath) {
		return rawPath
	}
	dir := filepath.Dir(rawPath)
	base := filepath.Base(rawPath)

	if info, err := os.Stat(rawPath); err == nil && info.IsDir() {
		if resolved, err := filepath.EvalSymlinks(rawPath); err == nil {
			return resolved
		}
		return rawPath
	}

	if resolved, err := filepath.EvalSymlinks(dir); err == nil {
		return filepath.Join(resolved, base)
	}
	return rawPath
}

func gitToplevel(dir string) (string, error) {
	cmd := exec.Command("git", "-C", dir, "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func trimPrefix(path, prefix string) (string, bool) {
	if strings.HasPrefix(path, prefix+"/") {
		return path[len(prefix)+1:], true
	}
	return "", false
}
