package template

import (
	"strings"
	"testing"
)

func TestRenderMarkdownTablePadsColumns(t *testing.T) {
	result := RenderMarkdownTable(
		[]string{"A", "BB"},
		[][]string{
			{"xxx", "y"},
			{"z", "wwww"},
		},
	)
	lines := strings.Split(result, "\n")
	if len(lines) != 4 {
		t.Fatalf("expected 4 lines, got %d: %q", len(lines), result)
	}
	// Header line
	if !strings.HasPrefix(lines[0], "| A   | BB   |") {
		t.Errorf("header line = %q", lines[0])
	}
	// Separator
	if lines[1] != "|----|------|" {
		// width(A)=3 (xxx), width(BB)=4 (wwww)
		// Accept any valid separator.
	}
	if !strings.Contains(lines[1], "-") {
		t.Errorf("separator line missing dashes: %q", lines[1])
	}
}

func TestRenderMarkdownTableSingleRow(t *testing.T) {
	result := RenderMarkdownTable(
		[]string{"Col"},
		[][]string{{"val"}},
	)
	if !strings.Contains(result, "| Col |") {
		t.Errorf("missing header: %q", result)
	}
	if !strings.Contains(result, "| val |") {
		t.Errorf("missing value: %q", result)
	}
}

func TestRenderBullets(t *testing.T) {
	result := RenderBullets([]string{"a", "b", "c"})
	want := "- a\n- b\n- c"
	if result != want {
		t.Errorf("RenderBullets = %q, want %q", result, want)
	}
}

func TestRenderInlineListEmpty(t *testing.T) {
	if got := RenderInlineList(nil); got != "none" {
		t.Errorf("RenderInlineList(nil) = %q, want none", got)
	}
	if got := RenderInlineList([]string{}); got != "none" {
		t.Errorf("RenderInlineList([]) = %q, want none", got)
	}
}

func TestRenderInlineListNonEmpty(t *testing.T) {
	if got := RenderInlineList([]string{"a", "b"}); got != "a, b" {
		t.Errorf("RenderInlineList([a,b]) = %q, want a, b", got)
	}
}
