package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func runSplitCheckCmd(t *testing.T, args ...string) (int, map[string]any) {
	t.Helper()
	var buf bytes.Buffer
	rc := runSplitCheck(&buf, args)
	var result map[string]any
	if line := strings.TrimSpace(buf.String()); line != "" {
		if err := json.Unmarshal([]byte(line), &result); err != nil {
			return rc, map[string]any{"_raw": line, "_err": err.Error()}
		}
	}
	return rc, result
}

// writeSplitCheckFile writes content to rootDir/relativePath (POSIX slash path).
func writeSplitCheckFile(t *testing.T, rootDir, relativePath, content string) string {
	t.Helper()
	full := filepath.Join(rootDir, filepath.FromSlash(relativePath))
	if err := os.MkdirAll(filepath.Dir(full), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(full, []byte(strings.TrimSpace(content)+"\n"), 0644); err != nil {
		t.Fatal(err)
	}
	return full
}

// --- fixture helpers ---

func scSingleDesign() string {
	return `
# Topic - Design

## Decomposition Strategy

- Split Decision: single
- Decision Basis: One owned boundary; verification stays unified.
- Root Scope: Single CLI boundary.

### Boundary Inventory

| Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
|----------|----------------------|------------------------------|----------------------|-----------------|------------|
| CLI Runtime | REQ01; AC01 | cli-smoke | none | no | none |

## Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| AC01 | Ubiquitous | behavioral | The CLI shall execute the sync path. | CLI smoke returns success. | ` + "`make list`" + ` |
`
}

func scSingleButShouldSplit() string {
	return `
# Topic - Design

## Decomposition Strategy

- Split Decision: single
- Decision Basis: Placeholder rationale.
- Root Scope: API and worker boundaries.

### Boundary Inventory

| Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
|----------|----------------------|------------------------------|----------------------|-----------------|------------|
| Public API | REQ01; AC01 | api-contract | none | yes | none |
| Worker | REQ02; AC02 | integration-job | none | yes | Public API |

## Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| AC01 | Ubiquitous | api-contract | The API shall accept jobs. | Contract test passes. | ` + "`make list`" + ` |
| AC02 | Ubiquitous | behavioral | The worker shall process jobs. | Worker smoke passes. | ` + "`make list`" + ` |
`
}

func scRootSubDesign() string {
	return `
# Topic - Design

## Decomposition Strategy

- Split Decision: root-sub
- Decision Basis: Two owned boundaries with distinct verification surfaces.
- Root Scope: Shared constraints and integration-only responsibilities.

### Boundary Inventory

| Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
|----------|----------------------|------------------------------|----------------------|-----------------|------------|
| Public API | REQ-API; AC-API | api-contract | none | yes | none |
| Worker | REQ-WORKER; AC-WORKER | job-integration | none | yes | Public API |
| Integration | Integration-only | end-to-end | none | no | Public API, Worker |

### Sub-Doc Index

| Sub ID | File | Owned Boundary | Owns Requirements/AC |
|--------|------|----------------|----------------------|
| SUB-API | docs/plans/topic/api-design.md | Public API | REQ-API; AC-API |
| SUB-WORKER | docs/plans/topic/worker-design.md | Worker | REQ-WORKER; AC-WORKER |

### Root Coverage

| Root Requirement/AC | Covered By (Sub ID or Integration) | Notes |
|---------------------|------------------------------------|-------|
| ROOT-AC-01 | Integration | end-to-end |

## Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| ROOT-AC-01 | Event-Driven | behavioral | When the API accepts a job, the system shall complete the job through the worker. | End-to-end flow passes. | ` + "`make list`" + ` |
`
}

func scAPISubdoc() string {
	return `
# Topic - API Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-API
- Root Design: ` + "`docs/plans/topic/design.md`" + `
- Owned Boundary: Public API

## Local Requirements

- REQ-API: Accept job submission.

## Local Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| AC-API | Ubiquitous | api-contract | The API shall validate and enqueue jobs. | API contract passes. | ` + "`make list`" + ` |
`
}

func scWorkerSubdoc() string {
	return `
# Topic - Worker Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-WORKER
- Root Design: ` + "`docs/plans/topic/design.md`" + `
- Owned Boundary: Worker

## Local Requirements

- REQ-WORKER: Process enqueued jobs.

## Local Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| AC-WORKER | Ubiquitous | behavioral | The worker shall process queued jobs. | Worker integration passes. | ` + "`make list`" + ` |
`
}

func scWorkerSubdocNoAC() string {
	return `
# Topic - Worker Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-WORKER
- Root Design: ` + "`docs/plans/topic/design.md`" + `
- Owned Boundary: Worker

## Local Requirements

- REQ-WORKER: Process enqueued jobs.

## Local Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
`
}

func scAdvisoryRootSubDesign() string {
	return `
# Topic - Design

## Decomposition Strategy

- Split Decision: root-sub
- Decision Basis: Distinct API and worker boundaries.
- Root Scope: Shared coordination and integration behavior.

### Boundary Inventory

| Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
|----------|----------------------|------------------------------|----------------------|-----------------|------------|
| Public API | REQ-API; AC-API-* | api-contract | none | yes | Worker |
| Worker | REQ-WORKER; AC-WORKER | job-integration | none | yes | Public API |

### Sub-Doc Index

| Sub ID | File | Owned Boundary | Owns Requirements/AC |
|--------|------|----------------|----------------------|
| SUB-API | docs/plans/topic/api-design.md | Public API | REQ-API; AC-API-* |
| SUB-WORKER | docs/plans/topic/worker-design.md | Worker | REQ-WORKER; AC-WORKER |

### Root Coverage

| Root Requirement/AC | Covered By (Sub ID or Integration) | Notes |
|---------------------|------------------------------------|-------|
| ROOT-AC-01 | Integration | coordination |

## Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| ROOT-AC-01 | Event-Driven | behavioral | When the API schedules work, the system shall complete the worker flow. | End-to-end passes. | ` + "`make list`" + ` |
| ROOT-AC-02 | Event-Driven | behavioral | When retries occur, the integrated flow shall remain observable. | End-to-end passes. | ` + "`make list`" + ` |
| ROOT-AC-03 | Event-Driven | behavioral | When jobs fail, integration alerts shall trigger. | End-to-end passes. | ` + "`make list`" + ` |
| ROOT-AC-04 | Event-Driven | behavioral | When jobs succeed, integration telemetry shall emit. | End-to-end passes. | ` + "`make list`" + ` |
`
}

func scAdvisoryAPISubdoc() string {
	return `
# Topic - API Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-API
- Root Design: ` + "`docs/plans/topic/design.md`" + `
- Owned Boundary: Public API

## Local Requirements

- REQ-API: Accept jobs.

## Local Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| AC-API-01 | Ubiquitous | api-contract | The API shall validate jobs. | API contract passes. | ` + "`make list`" + ` |
| AC-API-02 | Ubiquitous | api-contract | The API shall persist jobs. | API contract passes. | ` + "`make list`" + ` |
| AC-API-03 | Ubiquitous | api-contract | The API shall expose retry metadata. | API contract passes. | ` + "`make list`" + ` |
`
}

func scAdvisoryWorkerSubdoc() string {
	return `
# Topic - Worker Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-WORKER
- Root Design: ` + "`docs/plans/topic/design.md`" + `
- Owned Boundary: Worker

## Local Requirements

- REQ-WORKER: Process jobs.

## Local Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|----------------------|---------------------|----------------------|
| AC-WORKER | Ubiquitous | behavioral | The worker shall complete queued jobs. | Worker integration passes. | ` + "`make list`" + ` |
`
}

// --- tests ---

func TestSplitCheck_ValidSinglePasses(t *testing.T) {
	tmp := t.TempDir()
	designPath := writeSplitCheckFile(t, tmp, "docs/plans/topic/design.md", scSingleDesign())

	rc, out := runSplitCheckCmd(t, designPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.owned_boundary_count"] != "1" {
		t.Errorf("expected signal.owned_boundary_count=1, got %v", out["signal.owned_boundary_count"])
	}
	if out["advisory.count"] != float64(0) {
		t.Errorf("expected advisory.count=0, got %v", out["advisory.count"])
	}
}

func TestSplitCheck_SingleBlocksWhenRootSubRequired(t *testing.T) {
	tmp := t.TempDir()
	designPath := writeSplitCheckFile(t, tmp, "docs/plans/topic/design.md", scSingleButShouldSplit())

	rc, out := runSplitCheckCmd(t, designPath)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	blocker1, _ := out["blocker.1"].(string)
	if !strings.Contains(blocker1, "Split Decision: single") {
		t.Errorf("expected blocker about 'Split Decision: single', got %v", blocker1)
	}
}

func TestSplitCheck_ValidRootSubPasses(t *testing.T) {
	tmp := t.TempDir()
	designPath := writeSplitCheckFile(t, tmp, "docs/plans/topic/design.md", scRootSubDesign())
	writeSplitCheckFile(t, tmp, "docs/plans/topic/api-design.md", scAPISubdoc())
	writeSplitCheckFile(t, tmp, "docs/plans/topic/worker-design.md", scWorkerSubdoc())

	rc, out := runSplitCheckCmd(t, designPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.effective_subdoc_count"] != "2" {
		t.Errorf("expected signal.effective_subdoc_count=2, got %v", out["signal.effective_subdoc_count"])
	}
	if out["advisory.count"] != float64(0) {
		t.Errorf("expected advisory.count=0, got %v", out["advisory.count"])
	}
}

func TestSplitCheck_RootSubBlocksWhenOnlyOneSubdocEffective(t *testing.T) {
	tmp := t.TempDir()
	designPath := writeSplitCheckFile(t, tmp, "docs/plans/topic/design.md", scRootSubDesign())
	writeSplitCheckFile(t, tmp, "docs/plans/topic/api-design.md", scAPISubdoc())
	writeSplitCheckFile(t, tmp, "docs/plans/topic/worker-design.md", scWorkerSubdocNoAC())

	rc, out := runSplitCheckCmd(t, designPath)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	blocker1, _ := out["blocker.1"].(string)
	if !strings.Contains(blocker1, "effective sub-docs") {
		t.Errorf("expected blocker about 'effective sub-docs', got %v", blocker1)
	}
}

func TestSplitCheck_RootSubEmitsAdvisoriesWithoutFailing(t *testing.T) {
	tmp := t.TempDir()
	designPath := writeSplitCheckFile(t, tmp, "docs/plans/topic/design.md", scAdvisoryRootSubDesign())
	writeSplitCheckFile(t, tmp, "docs/plans/topic/api-design.md", scAdvisoryAPISubdoc())
	writeSplitCheckFile(t, tmp, "docs/plans/topic/worker-design.md", scAdvisoryWorkerSubdoc())

	rc, out := runSplitCheckCmd(t, designPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	advisoryCount, _ := out["advisory.count"].(float64)
	if int(advisoryCount) < 2 {
		t.Errorf("expected at least 2 advisories, got %v", advisoryCount)
	}
	// Must include the root integration AC advisory.
	foundRootACAdvisory := false
	for i := 1; i <= int(advisoryCount); i++ {
		key := "advisory." + strconv.Itoa(i)
		if v, ok := out[key].(string); ok && strings.Contains(v, "Root integration AC count") {
			foundRootACAdvisory = true
			break
		}
	}
	if !foundRootACAdvisory {
		t.Errorf("expected advisory containing 'Root integration AC count', got advisories: %v", out)
	}
}

func TestSplitCheck_DesignFileNotFound(t *testing.T) {
	rc, out := runSplitCheckCmd(t, "/nonexistent/path/design.md")
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

func TestSplitCheck_NoArgs(t *testing.T) {
	rc, _ := runSplitCheckCmd(t)
	// --help/-h returns 0, no args should show usage (also returns 0 per current impl).
	// Verify it doesn't panic.
	if rc != 0 {
		t.Errorf("expected rc=0 for no args (help), got %d", rc)
	}
}

func TestSplitCheck_TooManyArgs(t *testing.T) {
	rc, out := runSplitCheckCmd(t, "a.md", "b.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "INVALID_ARGUMENT_COUNT" {
		t.Errorf("expected code=INVALID_ARGUMENT_COUNT, got %v", out["code"])
	}
}
