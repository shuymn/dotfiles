package workflow

import (
	"os"
	"path/filepath"
)

func resolveExistingPath(candidates ...string) string {
	last := ""
	for _, candidate := range candidates {
		if candidate == "" {
			continue
		}
		last = candidate
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return last
}

func resolvePathFromWorkingDirAndFile(anchorPath, relativePath string) string {
	if filepath.IsAbs(relativePath) {
		return relativePath
	}

	cwd, _ := os.Getwd()
	return resolveExistingPath(
		filepath.Join(cwd, relativePath),
		filepath.Join(filepath.Dir(anchorPath), relativePath),
	)
}

func resolveRepoRelativePath(anchorPath, relativePath string) string {
	if filepath.IsAbs(relativePath) {
		return relativePath
	}

	dir := filepath.Dir(anchorPath)
	seen := make(map[string]bool)
	for {
		if seen[dir] {
			break
		}
		seen[dir] = true

		candidate := filepath.Join(dir, relativePath)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}

		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}

	cwd, _ := os.Getwd()
	return filepath.Join(cwd, relativePath)
}
