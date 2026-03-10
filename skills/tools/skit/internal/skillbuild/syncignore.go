package skillbuild

import (
	"bufio"
	"errors"
	"os"
	"path/filepath"
	"strings"
)

// ParseSyncIgnore reads <sourceRoot>/.syncignore and returns a set of skill names to exclude.
// If the file does not exist, an empty map is returned without error.
func ParseSyncIgnore(sourceRoot string) (map[string]bool, error) {
	path := filepath.Join(sourceRoot, ".syncignore")
	f, err := os.Open(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return map[string]bool{}, nil
		}
		return nil, err
	}
	defer f.Close()

	result := map[string]bool{}
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		result[line] = true
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return result, nil
}
