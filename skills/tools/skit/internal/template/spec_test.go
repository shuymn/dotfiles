package template

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// skillsSrcPath returns the path to skills/src/ relative to this test file's package.
// go test runs with CWD = package directory (internal/template/).
func skillsSrcPath(parts ...string) string {
	base := filepath.Join("..", "..", "..", "..", "src")
	return filepath.Join(append([]string{base}, parts...)...)
}

func skillsTemplatePath(parts ...string) string {
	return skillsSrcPath(parts...)
}

func TestTraceTemplateRenderIsDeterministic(t *testing.T) {
	tmplPath := skillsTemplatePath("decompose-plan", "references", "trace-templates.md.tmpl")

	first, err := RenderStructuredTemplate(tmplPath)
	if err != nil {
		t.Fatalf("first render: %v", err)
	}
	second, err := RenderStructuredTemplate(tmplPath)
	if err != nil {
		t.Fatalf("second render: %v", err)
	}

	if first != second {
		t.Error("rendering is not deterministic")
	}

	// No unresolved template tokens.
	if strings.Contains(first, "{{ .") {
		t.Error("rendered output contains unresolved template token '{{ .'")
	}

	// Specific content checks from Python tests.
	if !strings.Contains(first, "Coverage ratio (`REQ+AC covered / total REQ+AC`): `X / Y`") {
		t.Error("missing expected coverage ratio line")
	}
	if !strings.Contains(first, "Required fixes: [if FAIL]") {
		t.Error("missing expected required fixes line")
	}
	if !strings.Contains(first, "retirement_trigger=[objective condition]") {
		t.Error("missing expected retirement_trigger")
	}
	if !strings.Contains(first, "retirement_verification=[verification command/test]") {
		t.Error("missing expected retirement_verification")
	}
	if !strings.Contains(first, "removal_scope=[what is deleted/disabled]") {
		t.Error("missing expected removal_scope")
	}
}

func TestCheckpointSummaryRendersSemanticVerdictPlaceholders(t *testing.T) {
	tmplPath := skillsTemplatePath("decompose-plan", "references", "plan-templates.md.tmpl")

	rendered, err := RenderStructuredTemplate(tmplPath)
	if err != nil {
		t.Fatalf("render: %v", err)
	}

	checks := []string{
		"- Alignment Verdict: PASS | FAIL",
		"- Integration Coverage Guard: PASS | FAIL | N/A",
		"- Risk Classification Guard: PASS | FAIL | N/A (greenfield without Critical-domain changes)",
		"- Trace Pack: `docs/plans/<topic>/plan.trace.md`",
		"- Compose Pack: `docs/plans/<topic>/plan.compose.md`",
		"- Updated At: `YYYY-MM-DD`",
	}
	for _, want := range checks {
		if !strings.Contains(rendered, want) {
			t.Errorf("missing expected line: %q", want)
		}
	}
	// Double-backtick regression check.
	if strings.Contains(rendered, "``docs/plans/") {
		t.Error("double-backtick found in rendered output")
	}
}

func TestDesignTemplateRenderIsDeterministic(t *testing.T) {
	tmplPath := skillsTemplatePath("design-doc", "references", "design-templates.md.tmpl")

	first, err := RenderStructuredTemplate(tmplPath)
	if err != nil {
		t.Fatalf("first render: %v", err)
	}
	second, err := RenderStructuredTemplate(tmplPath)
	if err != nil {
		t.Fatalf("second render: %v", err)
	}
	if first != second {
		t.Error("rendering is not deterministic")
	}
	if strings.Contains(first, "{{ .") {
		t.Error("unresolved template token in output")
	}
	if !strings.Contains(first, "## Clarifications") {
		t.Error("missing ## Clarifications heading")
	}
	if !strings.Contains(first, "| Question") {
		t.Error("missing | Question header")
	}
}

func TestLoadFragmentsRejectsInvalidPayload(t *testing.T) {
	// Build a temp dir with a modified design-templates.fragments.json.
	tmp := t.TempDir()

	origFragments := skillsSrcPath("design-doc", "references", "design-templates.fragments.json")
	data, err := os.ReadFile(origFragments)
	if err != nil {
		t.Fatal(err)
	}
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	acs := raw["acceptance_criteria"].([]any)
	acs[0].(map[string]any)["ac_id"] = ""
	modified, _ := json.Marshal(raw)

	fragPath := filepath.Join(tmp, "design-templates.fragments.json")
	if err := os.WriteFile(fragPath, modified, 0644); err != nil {
		t.Fatal(err)
	}

	_, err = LoadFragments(filepath.Join(tmp, "design-templates.md.tmpl"))
	if err == nil {
		t.Fatal("expected error for invalid fragments, got nil")
	}
	if !strings.Contains(err.Error(), "invalid fragments") {
		t.Errorf("expected 'invalid fragments' in error, got: %v", err)
	}
}

func TestRenderStructuredTemplateRejectsUnsupported(t *testing.T) {
	_, err := RenderStructuredTemplate("/some/path/unknown-template.md.tmpl")
	if err == nil {
		t.Fatal("expected error for unsupported template, got nil")
	}
}

func TestFragmentsPathForTemplate(t *testing.T) {
	path, err := FragmentsPathForTemplate("/path/to/design-templates.md.tmpl")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if want := "/path/to/design-templates.fragments.json"; path != want {
		t.Errorf("got %q, want %q", path, want)
	}

	_, err = FragmentsPathForTemplate("/path/to/not-a-template.md")
	if err == nil {
		t.Fatal("expected error for non-.md.tmpl path, got nil")
	}
}
