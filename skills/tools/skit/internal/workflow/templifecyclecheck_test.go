package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runTempLifecycleCheckCmd(t *testing.T, args ...string) (int, map[string]any) {
	t.Helper()
	rc, stdout, _, err := runCommandOutput(TempLifecycleCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeTempDesignFile(t *testing.T, content string) string {
	t.Helper()
	tmp := t.TempDir()
	p := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(p, []byte(strings.TrimSpace(content)+"\n"), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

// --- SKIP cases ---

func TestTempLifecycleCheck_NoCompatSection(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Goals
- Do something
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_COMPATIBILITY_SUNSET_SECTION" {
		t.Errorf("expected code=NO_COMPATIBILITY_SUNSET_SECTION, got %v", out["code"])
	}
}

func TestTempLifecycleCheck_NoTempIDs(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

No temporary mechanisms needed.
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_TEMP_IDS_FOUND" {
		t.Errorf("expected code=NO_TEMP_IDS_FOUND, got %v", out["code"])
	}
}

// --- PASS case ---

func TestTempLifecycleCheck_ValidLifecycle(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim layer | ADR-001 |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | v2.0 release | CI green | Remove shim |
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "ALL_TEMP_LIFECYCLE_VALID" {
		t.Errorf("expected code=ALL_TEMP_LIFECYCLE_VALID, got %v", out["code"])
	}
	if out["signal.index_count"] != float64(1) {
		t.Errorf("expected signal.index_count=1, got %v", out["signal.index_count"])
	}
	if out["signal.issues"] != float64(0) {
		t.Errorf("expected signal.issues=0, got %v", out["signal.issues"])
	}
}

// --- FAIL: mismatch between Index and Checklist ---

func TestTempLifecycleCheck_IndexOnlyMissing(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim | ADR-001 |
| TEMP2 | Flag | ADR-002 |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | v2.0 release | CI green | Remove shim |
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	issue1, _ := out["issue.1"].(string)
	if !strings.Contains(issue1, "TEMP2") || !strings.Contains(issue1, "missing from Sunset Closure Checklist") {
		t.Errorf("expected issue about TEMP2 missing from Checklist, got %v", issue1)
	}
}

func TestTempLifecycleCheck_ChecklistOnlyMissing(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim | ADR-001 |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | v2.0 | CI green | Remove shim |
| TEMP2 | v3.0 | CI green | Remove flag |
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	issue1, _ := out["issue.1"].(string)
	if !strings.Contains(issue1, "TEMP2") || !strings.Contains(issue1, "missing from Temporary Mechanism Index") {
		t.Errorf("expected issue about TEMP2 missing from Index, got %v", issue1)
	}
}

// --- FAIL: required field empty/TBD ---

func TestTempLifecycleCheck_RequiredFieldEmpty(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim | ADR-001 |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | - | CI green | Remove shim |
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	issue1, _ := out["issue.1"].(string)
	if !strings.Contains(issue1, "Retirement Trigger") {
		t.Errorf("expected issue about Retirement Trigger, got %v", issue1)
	}
}

func TestTempLifecycleCheck_RequiredFieldTBD(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim | ADR-001 |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | v2.0 | TBD | Remove shim |
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	issue1, _ := out["issue.1"].(string)
	if !strings.Contains(issue1, "Retirement Verification") {
		t.Errorf("expected issue about Retirement Verification, got %v", issue1)
	}
}

// --- FAIL: ADR file not found ---

func TestTempLifecycleCheck_ADRFileNotFound(t *testing.T) {
	p := writeTempDesignFile(t, `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim | docs/adr/0001/adr-001.md |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | v2.0 | CI green | Remove shim |
`)
	rc, out := runTempLifecycleCheckCmd(t, p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	issue1, _ := out["issue.1"].(string)
	if !strings.Contains(issue1, "ADR file not found") {
		t.Errorf("expected issue about ADR file not found, got %v", issue1)
	}
}

func TestTempLifecycleCheck_ADRFileExists(t *testing.T) {
	tmp := t.TempDir()
	// Create ADR file
	adrDir := filepath.Join(tmp, "docs", "adr", "0001")
	if err := os.MkdirAll(adrDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(adrDir, "adr-001.md"), []byte("# ADR\n"), 0644); err != nil {
		t.Fatal(err)
	}
	// Write design file
	designPath := filepath.Join(tmp, "design.md")
	content := `# Design

## Compatibility & Sunset

### Temporary Mechanism Index

| ID | Mechanism | Lifecycle Record |
|----|-----------|-----------------|
| TEMP1 | Shim | docs/adr/0001/adr-001.md |

### Sunset Closure Checklist

| ID | Retirement Trigger | Retirement Verification | Removal Scope |
|----|-------------------|------------------------|---------------|
| TEMP1 | v2.0 | CI green | Remove shim |
`
	if err := os.WriteFile(designPath, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runTempLifecycleCheckCmd(t, designPath, "--base-dir", tmp)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

// --- FAIL: design file not found ---

func TestTempLifecycleCheck_DesignFileNotFound(t *testing.T) {
	rc, out := runTempLifecycleCheckCmd(t, "/nonexistent/path/design.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "DESIGN_FILE_NOT_FOUND" {
		t.Errorf("expected code=DESIGN_FILE_NOT_FOUND, got %v", out["code"])
	}
}
