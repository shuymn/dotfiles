package skillbuild

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseSyncIgnore_FileNotExist(t *testing.T) {
	dir := t.TempDir()
	got, err := ParseSyncIgnore(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("expected empty map, got %v", got)
	}
}

func TestParseSyncIgnore_EntriesCommentsBlankLines(t *testing.T) {
	dir := t.TempDir()
	content := `# Skills listed here are excluded from build/sync.

skill-a
# this is a comment
skill-b

`
	if err := os.WriteFile(filepath.Join(dir, ".syncignore"), []byte(content), 0o644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	got, err := ParseSyncIgnore(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !got["skill-a"] {
		t.Error("expected skill-a to be in result")
	}
	if !got["skill-b"] {
		t.Error("expected skill-b to be in result")
	}
	if len(got) != 2 {
		t.Errorf("expected 2 entries, got %d: %v", len(got), got)
	}
}

func TestParseSyncIgnore_TrimsWhitespace(t *testing.T) {
	dir := t.TempDir()
	content := "  skill-with-spaces  \n\t skill-with-tab\t\n"
	if err := os.WriteFile(filepath.Join(dir, ".syncignore"), []byte(content), 0o644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	got, err := ParseSyncIgnore(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !got["skill-with-spaces"] {
		t.Error("expected skill-with-spaces (trimmed) to be in result")
	}
	if !got["skill-with-tab"] {
		t.Error("expected skill-with-tab (trimmed) to be in result")
	}
	if len(got) != 2 {
		t.Errorf("expected 2 entries, got %d: %v", len(got), got)
	}
}
