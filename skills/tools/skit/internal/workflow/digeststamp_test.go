package workflow

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runDigestStampCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(DigestStamp(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func TestDigestStampSuccess(t *testing.T) {
	tmp := t.TempDir()
	content := []byte("# Test Plan\n")
	f := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(f, content, 0644); err != nil {
		t.Fatal(err)
	}

	for _, mode := range []string{"design-review", "plan-review", "dod-recheck", "adversarial-verify"} {
		t.Run(mode, func(t *testing.T) {
			rc, result := runDigestStampCmd(mode, f)
			if rc != 0 {
				t.Fatalf("expected exit 0, got %d", rc)
			}
			if result["status"] != "PASS" {
				t.Errorf("expected PASS, got %v", result["status"])
			}
			if result["mode"] != mode {
				t.Errorf("expected mode %s, got %v", mode, result["mode"])
			}
			expectedDigest := fmt.Sprintf("%x", sha256.Sum256(content))
			if result["source_digest"] != expectedDigest {
				t.Errorf("expected digest %s, got %v", expectedDigest, result["source_digest"])
			}
			if _, ok := result["reviewed_at"]; !ok {
				t.Error("expected reviewed_at field")
			}
			if _, ok := result["markdown"]; !ok {
				t.Error("expected markdown field")
			}
		})
	}
}

func TestDigestStampFileNotFound(t *testing.T) {
	rc, result := runDigestStampCmd("plan-review", "/nonexistent/file.md")
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["status"] != "FAIL" {
		t.Errorf("expected FAIL, got %v", result["status"])
	}
	if result["code"] != "SOURCE_FILE_NOT_FOUND" {
		t.Errorf("expected SOURCE_FILE_NOT_FOUND, got %v", result["code"])
	}
}

func TestDigestStampInvalidMode(t *testing.T) {
	tmp := t.TempDir()
	f := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(f, []byte("test"), 0644); err != nil {
		t.Fatal(err)
	}

	rc, result := runDigestStampCmd("invalid-mode", f)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "INVALID_MODE" {
		t.Errorf("expected INVALID_MODE, got %v", result["code"])
	}
}

func TestDigestStampInvalidArgCount(t *testing.T) {
	rc, result := runDigestStampCmd("plan-review")
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "MISSING_REQUIRED_ARGUMENT" {
		t.Errorf("expected MISSING_REQUIRED_ARGUMENT, got %v", result["code"])
	}
}

func TestDsGenerateStampCoreFunction(t *testing.T) {
	tmp := t.TempDir()
	content := []byte("hello world")
	f := filepath.Join(tmp, "test.md")
	if err := os.WriteFile(f, content, 0644); err != nil {
		t.Fatal(err)
	}

	stamp, err := DsGenerateStamp("plan-review", f)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if stamp.Mode != "plan-review" {
		t.Errorf("expected plan-review, got %s", stamp.Mode)
	}
	expectedDigest := fmt.Sprintf("%x", sha256.Sum256(content))
	if stamp.SourceDigest != expectedDigest {
		t.Errorf("expected digest %s, got %s", expectedDigest, stamp.SourceDigest)
	}
	md := stamp.RenderMarkdown()
	if !strings.Contains(md, "**Mode**: plan-review") {
		t.Errorf("markdown missing mode: %s", md)
	}
}

func TestDsGenerateStampInvalidMode(t *testing.T) {
	_, err := DsGenerateStamp("bad", "/tmp/whatever")
	if err == nil {
		t.Error("expected error for invalid mode")
	}
}

func TestDsGenerateStampMissingFile(t *testing.T) {
	_, err := DsGenerateStamp("plan-review", "/nonexistent/file.md")
	if err == nil {
		t.Error("expected error for missing file")
	}
}
