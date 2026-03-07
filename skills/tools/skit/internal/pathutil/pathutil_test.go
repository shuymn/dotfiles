package pathutil

import (
	"os"
	"path/filepath"
	"testing"
)

func TestExpandAndAbsTilde(t *testing.T) {
	home := os.Getenv("HOME")
	if home == "" {
		t.Skip("HOME not set")
	}
	got := ExpandAndAbs("~/foo")
	want := filepath.Join(home, "foo")
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestExpandAndAbsAbsolute(t *testing.T) {
	got := ExpandAndAbs("/tmp/foo")
	if got != "/tmp/foo" {
		t.Errorf("got %q, want /tmp/foo", got)
	}
}

func TestDisplayPathEmpty(t *testing.T) {
	if got := DisplayPath(""); got != "" {
		t.Errorf("expected empty, got %q", got)
	}
}

func TestDisplayPathRelative(t *testing.T) {
	if got := DisplayPath("foo/bar.md"); got != "foo/bar.md" {
		t.Errorf("expected foo/bar.md, got %q", got)
	}
}

func TestDisplayPathInGitRepo(t *testing.T) {
	// Use the skit directory itself, which is inside a git repo.
	cwd, err := os.Getwd()
	if err != nil {
		t.Skip("cannot get cwd")
	}
	absPath := filepath.Join(cwd, "pathutil.go")
	got := DisplayPath(absPath)
	// Should be git-root relative, not absolute.
	if filepath.IsAbs(got) {
		t.Errorf("expected relative path, got absolute %q", got)
	}
}

func TestDisplayPathHome(t *testing.T) {
	home := os.Getenv("HOME")
	if home == "" {
		t.Skip("HOME not set")
	}
	// Use a path that exists under HOME but is unlikely to be in a git repo.
	fakePath := home + "/nonexistent-test-pathutil-xyz123"
	got := DisplayPath(fakePath)
	if got != "~/nonexistent-test-pathutil-xyz123" {
		// If the test runs inside a git repo rooted at HOME, it could be git-relative.
		// Just check it's not the raw absolute path.
		if got == fakePath {
			t.Errorf("expected shortened path, got raw absolute %q", got)
		}
	}
}

func TestCanonicalize(t *testing.T) {
	tmp := t.TempDir()
	f := filepath.Join(tmp, "test.txt")
	if err := os.WriteFile(f, []byte("hello"), 0644); err != nil {
		t.Fatal(err)
	}
	got := canonicalize(f)
	if got == "" {
		t.Error("expected non-empty canonicalized path")
	}
	// The result should be absolute.
	if !filepath.IsAbs(got) {
		t.Errorf("expected absolute, got %q", got)
	}
}

func TestTrimPrefix(t *testing.T) {
	got, ok := trimPrefix("/a/b/c", "/a/b")
	if !ok || got != "c" {
		t.Errorf("expected (c, true), got (%q, %v)", got, ok)
	}

	_, ok = trimPrefix("/a/b/c", "/x/y")
	if ok {
		t.Error("expected false for non-matching prefix")
	}
}
