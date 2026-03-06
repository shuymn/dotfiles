package cmd

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"regexp"
	"strings"

	"skit/internal/cli"
	skitlog "skit/internal/log"
)

const riskFormatCheckToolName = "risk-format-check"

var (
	csRationaleRe  = regexp.MustCompile(`(?is)Defect Impact\s*:.+?/\s*Blast Radius\s*:`)
	stdRationaleRe = regexp.MustCompile(`(?is)Not Critical\s*:.+?/\s*Not Sensitive\s*:`)
)

// RiskFormatCheck returns the risk-format-check subcommand.
func RiskFormatCheck() *cli.Command {
	return &cli.Command{
		Name:        "risk-format-check",
		Description: "Validate Risk Classification table format in a design document",
		Run: func(args []string) int {
			return runRiskFormatCheck(os.Stdout, args)
		},
	}
}

func runRiskFormatCheck(w io.Writer, args []string) int {
	var positional []string

	for _, arg := range args {
		switch {
		case arg == "--help" || arg == "-h":
			fmt.Fprintln(os.Stderr, "usage: skit risk-format-check <design.md>")
			return 0
		case strings.HasPrefix(arg, "-"):
			fmt.Fprintf(os.Stderr, "error: unknown flag %q\n", arg)
			return 1
		default:
			positional = append(positional, arg)
		}
	}

	if len(positional) < 1 {
		fmt.Fprintln(os.Stderr, "usage: skit risk-format-check <design.md>")
		return 1
	}

	designPath := positional[0]

	data, err := os.ReadFile(designPath)
	if err != nil {
		skitlog.Emit(w, skitlog.Result{
			Tool:    riskFormatCheckToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s", designPath),
		},
			slog.Any("fix", []string{"FIX_DESIGN_FILE_PATH"}),
		)
		return 1
	}

	section := extractSection(string(data), "Risk Classification")
	if section == "" {
		skitlog.Emit(w, skitlog.Result{
			Tool:    riskFormatCheckToolName,
			Status:  "SKIP",
			Code:    "NO_RISK_CLASSIFICATION_SECTION",
			Summary: "No ## Risk Classification section found. Section is optional for greenfield designs without Critical domains.",
		})
		return 0
	}

	rows := parseGenericTable(section)
	if len(rows) == 0 {
		skitlog.Emit(w, skitlog.Result{
			Tool:    riskFormatCheckToolName,
			Status:  "FAIL",
			Code:    "RISK_TABLE_EMPTY",
			Summary: "## Risk Classification section exists but has no table rows.",
		},
			slog.Any("fix", []string{"FIX_ADD_RISK_TABLE_ROWS"}),
		)
		return 1
	}

	var failures []string
	for _, row := range rows {
		ok, issue := checkRiskRow(row)
		if !ok {
			failures = append(failures, issue)
		}
	}

	status := "PASS"
	code := "ALL_RISK_ROWS_VALID"
	summary := fmt.Sprintf("All %d risk row(s) have valid Change Rationale format.", len(rows))

	if len(failures) > 0 {
		status = "FAIL"
		code = "RISK_FORMAT_VIOLATIONS"
		summary = fmt.Sprintf("%d risk row(s) have format violations.", len(failures))
	}

	attrs := []slog.Attr{
		slog.Int("signal.total_rows", len(rows)),
		slog.Int("signal.failures", len(failures)),
	}
	for i, issue := range failures {
		attrs = append(attrs, slog.String(fmt.Sprintf("fail.%d", i+1), issue))
	}
	if len(failures) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_CRITICAL_SENSITIVE: use 'Defect Impact: [...] / Blast Radius: [...]'",
			"FIX_STANDARD: use 'Not Critical: [...] / Not Sensitive: [...]'",
		}))
	}

	skitlog.Emit(w, skitlog.Result{
		Tool:    riskFormatCheckToolName,
		Status:  status,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(failures) > 0 {
		return 1
	}
	return 0
}

func checkRiskRow(row map[string]string) (bool, string) {
	tier := coalesce(row["Risk Tier"], row["risk_tier"])
	rationale := coalesce(row["Change Rationale"], row["change_rationale"])
	area := coalesce(row["Area"], row["area"])
	if area == "" {
		area = "?"
	}

	switch tier {
	case "Critical", "Sensitive":
		if !csRationaleRe.MatchString(rationale) {
			return false, fmt.Sprintf(
				"%s (%s): Change Rationale must contain 'Defect Impact: [...] / Blast Radius: [...]'",
				area, tier,
			)
		}
	case "Standard":
		if !stdRationaleRe.MatchString(rationale) {
			return false, fmt.Sprintf(
				"%s (Standard): Change Rationale must contain 'Not Critical: [...] / Not Sensitive: [...]'",
				area,
			)
		}
	}
	return true, ""
}

func coalesce(vals ...string) string {
	for _, v := range vals {
		if t := strings.TrimSpace(v); t != "" {
			return t
		}
	}
	return ""
}
