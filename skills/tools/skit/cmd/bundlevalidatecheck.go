package cmd

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	skitlog "github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const bundleValidateCheckToolName = "bundle-validate-check"

var kvRe = regexp.MustCompile(`^\s*-?\s*\*\*([^*]+)\*\*\s*:\s*(.*)$`)

var bundleRequiredKeys = []string{
	"Alignment Verdict",
	"Forward Fidelity",
	"Reverse Fidelity",
	"Non-Goal Guard",
	"Behavioral Lock Guard",
	"Temporal Completeness Guard",
	"Quality Gate Guard",
	"Integration Coverage Guard",
	"Risk Classification Guard",
	"Trace Pack",
	"Compose Pack",
	"Updated At",
}

// BundleValidateCheck returns the bundle-validate-check subcommand.
func BundleValidateCheck() *cli.Command {
	return &cli.Command{
		Name:        "bundle-validate-check",
		Description: "Validate plan.md bundle consistency before task execution",
		Run: func(args []string) int {
			return runBundleValidateCheck(os.Stdout, args)
		},
	}
}

func runBundleValidateCheck(w io.Writer, args []string) int {
	var positional []string

	for _, arg := range args {
		switch {
		case arg == "--help" || arg == "-h":
			fmt.Fprintln(os.Stderr, "usage: skit bundle-validate-check <plan.md>")
			return 0
		case strings.HasPrefix(arg, "-"):
			fmt.Fprintf(os.Stderr, "error: unknown flag %q\n", arg)
			return 1
		default:
			positional = append(positional, arg)
		}
	}

	if len(positional) < 1 {
		fmt.Fprintln(os.Stderr, "usage: skit bundle-validate-check <plan.md>")
		return 1
	}

	planPath := positional[0]

	data, err := os.ReadFile(planPath)
	if err != nil {
		skitlog.Emit(w, skitlog.Result{
			Tool:    bundleValidateCheckToolName,
			Status:  "FAIL",
			Code:    "PLAN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Plan file not found: %s", planPath),
		},
			slog.Any("fix", []string{"FIX_PLAN_FILE_PATH"}),
		)
		return 1
	}

	text := string(data)
	baseDir := filepath.Dir(planPath)

	checkpointSection := extractSection(text, "Checkpoint Summary")
	if checkpointSection == "" {
		skitlog.Emit(w, skitlog.Result{
			Tool:    bundleValidateCheckToolName,
			Status:  "FAIL",
			Code:    "NO_CHECKPOINT_SUMMARY",
			Summary: "No ## Checkpoint Summary section found in plan.md.",
		},
			slog.Any("fix", []string{"FIX_ADD_CHECKPOINT_SUMMARY_SECTION"}),
		)
		return 1
	}

	kv := parseKV(checkpointSection)
	headerLinks := extractHeaderLinks(text)

	var issues []string

	// 1. Required keys
	var missing []string
	for _, k := range bundleRequiredKeys {
		if _, ok := kv[k]; !ok {
			missing = append(missing, k)
		}
	}
	if len(missing) > 0 {
		issues = append(issues, fmt.Sprintf("missing required keys: %s", strings.Join(missing, ", ")))
	}

	// 2. Alignment Verdict must be PASS
	alignment := kv["Alignment Verdict"]
	if alignment != "PASS" {
		issues = append(issues, fmt.Sprintf("Alignment Verdict must be exactly PASS, got: %q", alignment))
	}

	// 3+4. Trace Pack / Compose Pack: consistency and sidecar existence
	for _, key := range []string{"Trace Pack", "Compose Pack"} {
		headerVal := strings.TrimSpace(headerLinks[key])
		summaryVal := strings.TrimSpace(kv[key])
		if headerVal != "" && summaryVal != "" && headerVal != summaryVal {
			issues = append(issues, fmt.Sprintf("%s: header=%q != checkpoint=%q", key, headerVal, summaryVal))
		}
		ref := strings.TrimSpace(coalesce(kv[key], headerLinks[key]))
		if ref == "" {
			continue
		}
		refPath := ref
		if !filepath.IsAbs(ref) {
			refPath = filepath.Join(baseDir, ref)
		}
		if _, statErr := os.Stat(refPath); os.IsNotExist(statErr) {
			issues = append(issues, fmt.Sprintf("%s file not found: %s", key, ref))
		}
	}

	status := "PASS"
	code := "BUNDLE_VALID"
	summary := "Bundle valid: all required keys present, Alignment Verdict PASS, sidecars exist."

	if len(issues) > 0 {
		status = "FAIL"
		code = "BUNDLE_VALIDATION_FAILED"
		summary = fmt.Sprintf("%d bundle validation issue(s) found.", len(issues))
	}

	attrs := []slog.Attr{
		slog.Int("signal.checkpoint_keys_found", len(kv)),
		slog.Int("signal.issues", len(issues)),
	}
	for i, issue := range issues {
		attrs = append(attrs, slog.String(fmt.Sprintf("issue.%d", i+1), issue))
	}
	if len(issues) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_ADD_MISSING_CHECKPOINT_KEYS",
			"FIX_SET_ALIGNMENT_VERDICT_PASS",
			"FIX_RECONCILE_PACK_LINKS_AND_FILES",
		}))
	}

	skitlog.Emit(w, skitlog.Result{
		Tool:    bundleValidateCheckToolName,
		Status:  status,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(issues) > 0 {
		return 1
	}
	return 0
}

func parseKV(text string) map[string]string {
	result := make(map[string]string)
	for _, line := range strings.Split(text, "\n") {
		m := kvRe.FindStringSubmatch(line)
		if m != nil {
			result[strings.TrimSpace(m[1])] = strings.TrimSpace(m[2])
		}
	}
	return result
}

func extractHeaderLinks(text string) map[string]string {
	result := make(map[string]string)
	lines := strings.Split(text, "\n")
	limit := 40
	if len(lines) < limit {
		limit = len(lines)
	}
	for _, line := range lines[:limit] {
		m := kvRe.FindStringSubmatch(line)
		if m != nil {
			key := strings.TrimSpace(m[1])
			if key == "Trace Pack" || key == "Compose Pack" {
				result[key] = strings.TrimSpace(m[2])
			}
		}
	}
	return result
}
