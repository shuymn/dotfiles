package manifest

import (
	"encoding/json"
	"fmt"
	"os"
)

// ManagedSkillsManifest represents the managed skills manifest JSON.
type ManagedSkillsManifest struct {
	Version    int      `json:"version"`
	SourceRoot string   `json:"source_root"`
	Skills     []string `json:"skills"`
}

// Load reads and parses the manifest JSON at path.
// Unknown fields are rejected. Empty strings in skills are rejected.
func Load(path string) (*ManagedSkillsManifest, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	dec := json.NewDecoder(f)
	dec.DisallowUnknownFields()

	var m ManagedSkillsManifest
	if err := dec.Decode(&m); err != nil {
		return nil, fmt.Errorf("manifest format error: %w", err)
	}

	for _, s := range m.Skills {
		if s == "" {
			return nil, fmt.Errorf("skills must contain only non-empty strings")
		}
	}

	return &m, nil
}
