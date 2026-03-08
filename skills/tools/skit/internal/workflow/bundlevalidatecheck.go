package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const bundleValidateCheckToolName = "bundle-validate-check"

var kvRe = regexp.MustCompile(`^\s*-?\s*\*\*([^*]+)\*\*\s*:\s*(.*)$`)

var bundleRequiredKeys = []string{
	"Alignment Verdict",
	"Scope Contract Guard",
	"Quality Gate Guard",
	"Review Artifact",
	"Trace Pack",
	"Compose Pack",
	"Updated At",
}

// BundleValidateCheck returns the bundle-validate-check subcommand.
func BundleValidateCheck() *cli.Command {
	c := cli.NewCommand("bundle-validate-check", "Validate plan.md bundle consistency before task execution")
	var planFile string
	c.StringArg(&planFile, "plan-file", "Plan bundle file")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runBundleValidateCheck(s.Stdout, planFile))
	}
	return c
}

func runBundleValidateCheck(w io.Writer, planPath string) int {
	data, err := os.ReadFile(planPath)
	if err != nil {
		log.Emit(w, log.Result{
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
		log.Emit(w, log.Result{
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

	// 2. Required PASS verdicts.
	requiredPass := []string{"Alignment Verdict", "Scope Contract Guard", "Quality Gate Guard"}
	for _, key := range requiredPass {
		if strings.TrimSpace(kv[key]) != "PASS" {
			issues = append(issues, fmt.Sprintf("%s must be exactly PASS, got: %q", key, kv[key]))
		}
	}

	// 3. Review / Trace / Compose artifacts must exist. Trace and Compose must also match header links.
	for _, key := range []string{"Review Artifact", "Trace Pack", "Compose Pack"} {
		headerVal := normalizeBundleRef(headerLinks[key])
		summaryVal := normalizeBundleRef(kv[key])
		if (key == "Trace Pack" || key == "Compose Pack") && headerVal != "" && summaryVal != "" && headerVal != summaryVal {
			issues = append(issues, fmt.Sprintf("%s: header=%q != checkpoint=%q", key, headerVal, summaryVal))
		}
		ref := normalizeBundleRef(coalesce(kv[key], headerLinks[key]))
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
	summary := "Bundle valid: required checkpoint keys are present, guards PASS, and artifacts exist."

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
			"FIX_SET_REQUIRED_GUARDS_PASS",
			"FIX_RECONCILE_ARTIFACT_LINKS_AND_FILES",
		}))
	}

	log.Emit(w, log.Result{
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

func normalizeBundleRef(raw string) string {
	return strings.Trim(strings.TrimSpace(raw), "`")
}

func parseKV(text string) map[string]string {
	return parseKeyValueBullets(text)
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
