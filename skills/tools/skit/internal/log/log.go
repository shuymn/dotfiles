package log

import (
	"io"
	"log/slog"
)

// Result holds the common fields for a check result.
type Result struct {
	Tool    string
	Status  string // "PASS" | "FAIL" | "SKIP"
	Code    string
	Summary string
}

// Emit writes a single JSON log line for the check result.
// PASS/SKIP → INFO level, FAIL → ERROR level.
// Additional attributes are appended after the standard fields.
func Emit(w io.Writer, r Result, attrs ...slog.Attr) {
	level := slog.LevelInfo
	if r.Status == "FAIL" {
		level = slog.LevelError
	}

	handler := slog.NewJSONHandler(w, nil)
	logger := slog.New(handler)

	allAttrs := []slog.Attr{
		slog.String("tool", r.Tool),
		slog.String("status", r.Status),
		slog.String("code", r.Code),
		slog.String("summary", r.Summary),
	}
	allAttrs = append(allAttrs, attrs...)

	logger.LogAttrs(nil, level, "check-complete", allAttrs...)
}
