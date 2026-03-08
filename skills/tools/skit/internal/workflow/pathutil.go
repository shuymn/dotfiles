package workflow

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func ensureDir(path string) string {
	if info, err := os.Stat(path); err != nil || !info.IsDir() {
		return filepath.Dir(path)
	}
	return path
}

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

func resolveRepoRelativePath(anchorPath, relativePath string) string {
	if filepath.IsAbs(relativePath) {
		return relativePath
	}

	dir := ensureDir(anchorPath)

	seen := make(map[string]bool)
	repoRoot := repoRootFromPath(anchorPath)
	lastRepoCandidate := ""
	for {
		if seen[dir] {
			break
		}
		seen[dir] = true

		candidate := filepath.Join(dir, relativePath)
		if repoRoot != "" && dir == repoRoot {
			lastRepoCandidate = candidate
		}
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}

		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	if lastRepoCandidate != "" {
		return lastRepoCandidate
	}
	return filepath.Join(filepath.Dir(anchorPath), relativePath)
}

func repoRootFromPath(anchorPath string) string {
	if anchorPath == "" {
		return ""
	}
	dir := ensureDir(anchorPath)
	root, err := gitToplevelFn(dir)
	if err != nil || root == "" {
		return ""
	}
	return root
}

func resolveArtifactSourcePath(artifactPath, sourceFileHint, baseDir, sourceArtifact string) string {
	if filepath.IsAbs(sourceArtifact) {
		return sourceArtifact
	}

	var candidates []string
	if sourceFileHint != "" {
		candidates = append(candidates,
			sourceFileHint,
			filepath.Join(filepath.Dir(sourceFileHint), sourceArtifact),
			resolveRepoRelativePath(sourceFileHint, sourceArtifact),
		)
	}
	if baseDir != "" {
		candidates = append(candidates, filepath.Join(baseDir, sourceArtifact))
	}
	candidates = append(candidates,
		resolveRepoRelativePath(artifactPath, sourceArtifact),
		filepath.Join(filepath.Dir(artifactPath), sourceArtifact),
	)
	return resolveExistingPath(candidates...)
}

var gitToplevelFn = gitToplevelImpl

func gitToplevelImpl(dir string) (string, error) {
	cmd := exec.Command("git", "-C", dir, "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}
