package cmd

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const tempLifecycleCheckToolName = "temp-lifecycle-check"

var (
	tlcTempIDRe  = regexp.MustCompile(`\bTEMP[A-Za-z0-9_-]*[0-9]+\b`)
	tlcADRPathRe = regexp.MustCompile(`docs/adr/[^\s)\]>]+\.md`)

	tlcNoneTokens = map[string]bool{
		"":            true,
		"-":           true,
		"none":        true,
		"n/a":         true,
		"na":          true,
		"tbd":         true,
		"tbd-at-plan": true,
	}

	// Column name variants
	tlcIDCols           = []string{"ID", "id", "Temp ID", "TEMP ID", "TempID"}
	tlcLifecycleCols    = []string{"Lifecycle Record", "lifecycle_record", "Lifecycle", "ADR/Ledger"}
	tlcTriggerCols      = []string{"Retirement Trigger", "retirement_trigger", "Trigger"}
	tlcVerificationCols = []string{"Retirement Verification", "retirement_verification", "Verification"}
	tlcScopeCols        = []string{"Removal Scope", "removal_scope", "Scope"}
)

// TempLifecycleCheck returns the temp-lifecycle-check subcommand.
func TempLifecycleCheck() *cli.Command {
	c := cli.NewCommand("temp-lifecycle-check", "Verify TEMPxx lifecycle structure completeness in a design document")
	var baseDir string
	c.StringVar(&baseDir, "base-dir", "", "", "Base directory for ADR file resolution (default: design file's directory)")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if len(s.Args) < 1 {
			return fmt.Errorf("usage: skit temp-lifecycle-check <design-file> [--base-dir <dir>]")
		}
		return exitCode(runTempLifecycleCheck(os.Stdout, baseDir, s.Args[0]))
	}
	return c
}

func runTempLifecycleCheck(w io.Writer, baseDir, designFile string) int {
	data, err := os.ReadFile(designFile)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    tempLifecycleCheckToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s", designFile),
		}, slog.String("fix.1", "FIX_DESIGN_FILE_PATH"))
		return 1
	}

	resolvedBaseDir := baseDir
	if resolvedBaseDir == "" {
		resolvedBaseDir = filepath.Dir(designFile)
	}

	text := string(data)
	compat := tlcFindCompatSection(text)
	if compat == "" {
		log.Emit(w, log.Result{
			Tool:    tempLifecycleCheckToolName,
			Status:  "SKIP",
			Code:    "NO_COMPATIBILITY_SUNSET_SECTION",
			Summary: "No ## Compatibility & Sunset section found. TEMPxx lifecycle check skipped.",
		})
		return 0
	}

	indexSection := tlcFindSubsection(compat, tlcIndexRe)
	checklistSection := tlcFindSubsection(compat, tlcChecklistRe)

	indexRows := tlcExtractTempRows(coalesce(indexSection, compat))
	checklistRows := tlcExtractTempRows(coalesce(checklistSection, compat))

	if len(indexRows) == 0 && len(checklistRows) == 0 {
		log.Emit(w, log.Result{
			Tool:    tempLifecycleCheckToolName,
			Status:  "SKIP",
			Code:    "NO_TEMP_IDS_FOUND",
			Summary: "No TEMPxx IDs found in ## Compatibility & Sunset section.",
		})
		return 0
	}

	var issues []string

	// Cross-check: IDs in Index but not Checklist
	indexOnly := tlcSetDiff(indexRows, checklistRows)
	checklistOnly := tlcSetDiff(checklistRows, indexRows)

	for _, tid := range indexOnly {
		issues = append(issues, fmt.Sprintf("%s: in Temporary Mechanism Index but missing from Sunset Closure Checklist", tid))
	}
	for _, tid := range checklistOnly {
		issues = append(issues, fmt.Sprintf("%s: in Sunset Closure Checklist but missing from Temporary Mechanism Index", tid))
	}

	// Required field checks on checklist rows
	for _, tid := range tlcSortedKeys(checklistRows) {
		row := checklistRows[tid]
		for _, field := range []struct {
			label string
			cols  []string
		}{
			{"Retirement Trigger", tlcTriggerCols},
			{"Retirement Verification", tlcVerificationCols},
			{"Removal Scope", tlcScopeCols},
		} {
			val := strings.ToLower(tlcGetCol(row, field.cols))
			if tlcNoneTokens[val] {
				issues = append(issues, fmt.Sprintf("%s: required field '%s' is empty or TBD", tid, field.label))
			}
		}
	}

	// ADR file existence check
	indexKeys := tlcSortedKeys(indexRows)
	for _, tid := range indexKeys {
		row := indexRows[tid]
		lifecycle := tlcGetCol(row, tlcLifecycleCols)
		if lifecycle == "" {
			continue
		}
		for _, match := range tlcADRPathRe.FindAllString(lifecycle, -1) {
			adrPath := filepath.Join(resolvedBaseDir, match)
			if _, err := os.Stat(adrPath); os.IsNotExist(err) {
				issues = append(issues, fmt.Sprintf("%s: lifecycle ADR file not found: %s", tid, match))
			}
		}
	}

	overall := "PASS"
	code := "ALL_TEMP_LIFECYCLE_VALID"
	summary := fmt.Sprintf("All %d TEMPxx mechanism(s) have valid lifecycle records.", len(indexRows))
	if len(issues) > 0 {
		overall = "FAIL"
		code = "TEMP_LIFECYCLE_VIOLATIONS"
		summary = fmt.Sprintf("%d TEMPxx lifecycle issue(s) found.", len(issues))
	}

	attrs := []slog.Attr{
		slog.Int("signal.index_count", len(indexRows)),
		slog.Int("signal.checklist_count", len(checklistRows)),
		slog.Int("signal.issues", len(issues)),
	}
	for i, issue := range issues {
		attrs = append(attrs, slog.String(fmt.Sprintf("issue.%d", i+1), issue))
	}
	if len(issues) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_ADD_MISSING_TEMP_CHECKLIST_ROW",
			"FIX_POPULATE_REQUIRED_LIFECYCLE_FIELDS",
			"FIX_RESOLVE_ADR_PATH",
		}))
	}

	log.Emit(w, log.Result{
		Tool:    tempLifecycleCheckToolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(issues) > 0 {
		return 1
	}
	return 0
}

// tlcFindCompatSection searches for the Compatibility & Sunset section under several title variants.
func tlcFindCompatSection(text string) string {
	for _, title := range []string{"Compatibility & Sunset", "Compatibility and Sunset", "Compatibility"} {
		if s := extractSection(text, title); s != "" {
			return s
		}
	}
	return ""
}

var (
	// tlcNextSubsectionRe terminates a subsection at the next ##/###/#### heading.
	tlcNextSubsectionRe = regexp.MustCompile(`(?m)^#{2,4}\s`)
	// Pre-compiled subsection header patterns for the known title sets.
	tlcIndexRe     = regexp.MustCompile(`(?m)^#{3,4}\s+(?:Temporary Mechanism Index|Temporary Mechanism Ledger)\s*$`)
	tlcChecklistRe = regexp.MustCompile(`(?m)^#{3,4}\s+Sunset Closure Checklist\s*$`)
)

// tlcFindSubsection extracts the content of the first matching ### or #### subsection from parent text.
func tlcFindSubsection(parent string, sectionRe *regexp.Regexp) string {
	loc := sectionRe.FindStringIndex(parent)
	if loc == nil {
		return ""
	}
	rest := parent[loc[1]:]
	endLoc := tlcNextSubsectionRe.FindStringIndex(rest)
	var content string
	if endLoc != nil {
		content = strings.TrimSpace(rest[:endLoc[0]])
	} else {
		content = strings.TrimSpace(rest)
	}
	return content
}

// tlcExtractTempRows parses a markdown table in text and returns {temp_id: row} for rows with TEMP IDs.
func tlcExtractTempRows(text string) map[string]map[string]string {
	result := make(map[string]map[string]string)
	rows := parseGenericTable(text)
	for _, row := range rows {
		idVal := tlcGetCol(row, tlcIDCols)
		ids := tlcTempIDRe.FindAllString(idVal, -1)
		if len(ids) > 0 {
			result[ids[0]] = row
		}
	}
	return result
}

// tlcGetCol returns the first non-empty value for any of the given column name variants.
func tlcGetCol(row map[string]string, variants []string) string {
	for _, col := range variants {
		if val := row[col]; val != "" {
			return strings.TrimSpace(val)
		}
	}
	return ""
}

// tlcSetDiff returns sorted keys in a that are not in b.
func tlcSetDiff(a, b map[string]map[string]string) []string {
	var result []string
	for k := range a {
		if _, ok := b[k]; !ok {
			result = append(result, k)
		}
	}
	sort.Strings(result)
	return result
}

// tlcSortedKeys returns sorted keys of the map.
func tlcSortedKeys(m map[string]map[string]string) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
