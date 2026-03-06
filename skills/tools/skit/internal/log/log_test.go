package log

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"testing"
)

func TestEmitPassIsInfo(t *testing.T) {
	var buf bytes.Buffer
	Emit(&buf, Result{
		Tool:    "test-tool",
		Status:  "PASS",
		Code:    "ALL_OK",
		Summary: "All good.",
	})

	var out map[string]any
	if err := json.Unmarshal(buf.Bytes(), &out); err != nil {
		t.Fatalf("failed to parse JSON: %v\noutput: %s", err, buf.String())
	}
	if out["level"] != "INFO" {
		t.Errorf("expected level=INFO, got %v", out["level"])
	}
	if out["msg"] != "check-complete" {
		t.Errorf("expected msg=check-complete, got %v", out["msg"])
	}
	if out["tool"] != "test-tool" {
		t.Errorf("expected tool=test-tool, got %v", out["tool"])
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

func TestEmitFailIsError(t *testing.T) {
	var buf bytes.Buffer
	Emit(&buf, Result{
		Tool:    "test-tool",
		Status:  "FAIL",
		Code:    "SOME_FAIL",
		Summary: "Something failed.",
	})

	var out map[string]any
	if err := json.Unmarshal(buf.Bytes(), &out); err != nil {
		t.Fatalf("failed to parse JSON: %v\noutput: %s", err, buf.String())
	}
	if out["level"] != "ERROR" {
		t.Errorf("expected level=ERROR, got %v", out["level"])
	}
}

func TestEmitSkipIsInfo(t *testing.T) {
	var buf bytes.Buffer
	Emit(&buf, Result{
		Tool:    "test-tool",
		Status:  "SKIP",
		Code:    "NO_FILES",
		Summary: "No files found.",
	})

	var out map[string]any
	if err := json.Unmarshal(buf.Bytes(), &out); err != nil {
		t.Fatalf("failed to parse JSON: %v\noutput: %s", err, buf.String())
	}
	if out["level"] != "INFO" {
		t.Errorf("expected level=INFO, got %v", out["level"])
	}
}

func TestEmitExtraAttrs(t *testing.T) {
	var buf bytes.Buffer
	Emit(&buf, Result{
		Tool:    "test-tool",
		Status:  "PASS",
		Code:    "OK",
		Summary: "done",
	},
		slog.Int("signal.total", 3),
		slog.String("fix.1", "DO_SOMETHING"),
	)

	var out map[string]any
	if err := json.Unmarshal(buf.Bytes(), &out); err != nil {
		t.Fatalf("failed to parse JSON: %v\noutput: %s", err, buf.String())
	}
	if out["signal.total"] != float64(3) {
		t.Errorf("expected signal.total=3, got %v", out["signal.total"])
	}
	if out["fix.1"] != "DO_SOMETHING" {
		t.Errorf("expected fix.1=DO_SOMETHING, got %v", out["fix.1"])
	}
}
