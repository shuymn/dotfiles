package workflow

import "testing"

func TestExtractSectionLevel_Level3(t *testing.T) {
	text := `
# Design

## Decomposition Strategy

### Boundary Inventory

| Boundary | Owns Requirements/AC |
|----------|----------------------|
| CLI | AC01 |

### Next

after
`
	got := extractSectionLevel(text, "Boundary Inventory", 3)
	if got == "" || parseGenericTable(got) == nil {
		t.Fatalf("expected level 3 section content, got %q", got)
	}
	if contains := extractSectionLevel(text, "Missing", 3); contains != "" {
		t.Fatalf("expected empty section, got %q", contains)
	}
}

func TestParseAcceptanceCriteriaRows_FallbackVerificationColumn(t *testing.T) {
	section := `| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification |
|-------|-----------|---------------|----------------------|---------------------|--------------|
| AC01 | Ubiquitous | behavioral | The CLI shall run. | Smoke test passes. | go test ./... |`

	rows := parseAcceptanceCriteriaRows(section)
	if len(rows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(rows))
	}
	if rows[0].VerificationCommand != "go test ./..." {
		t.Fatalf("expected fallback verification command, got %q", rows[0].VerificationCommand)
	}
}

func TestParseBoundaryInventoryRows_DependsOnSplit(t *testing.T) {
	section := `| Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
|----------|----------------------|------------------------------|----------------------|-----------------|------------|
| Worker | REQ01; AC01 | integration | none | yes | API, Queue |`

	rows := parseBoundaryInventoryRows(section)
	if len(rows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(rows))
	}
	if len(rows[0].DependsOn) != 2 {
		t.Fatalf("expected 2 dependencies, got %#v", rows[0].DependsOn)
	}
	if rows[0].DependsOn[0] != "API" || rows[0].DependsOn[1] != "Queue" {
		t.Fatalf("unexpected dependencies: %#v", rows[0].DependsOn)
	}
}

func TestParseTemporaryRows_ColumnAliases(t *testing.T) {
	indexSection := `| TEMP ID | Mechanism | ADR/Ledger | Status |
|---------|-----------|------------|--------|
| TEMP01 | shim | docs/adr/topic/adr.md | active |`
	checklistSection := `| Temp ID | Introduced For | Trigger | Verification | Scope |
|---------|----------------|---------|--------------|-------|
| TEMP01 | migration | cutover | go test ./... | old path |`

	indexRows := parseTemporaryMechanismIndexRows(indexSection)
	if len(indexRows) != 1 || indexRows[0].LifecycleRecord != "docs/adr/topic/adr.md" {
		t.Fatalf("unexpected index rows: %#v", indexRows)
	}

	checklistRows := parseSunsetClosureChecklistRows(checklistSection)
	if len(checklistRows) != 1 {
		t.Fatalf("expected 1 checklist row, got %d", len(checklistRows))
	}
	if checklistRows[0].RetirementTrigger != "cutover" || checklistRows[0].RemovalScope != "old path" {
		t.Fatalf("unexpected checklist row: %#v", checklistRows[0])
	}
}
