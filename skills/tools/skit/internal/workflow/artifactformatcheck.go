package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"regexp"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const artifactFormatCheckToolName = "artifact-format-check"

var validArtifactTypes = []string{
	"design", "plan", "trace", "compose", "review", "dod-recheck", "adversarial", "completion-audit",
}

var requiredSections = map[string][]string{
	"design":      {"Goals", "Acceptance Criteria", "Decomposition Strategy"},
	"plan":        {"Checkpoint Summary", "Task Dependency Graph"},
	"trace":       {"Design -> Task Trace Matrix", "AC Ownership Map"},
	"compose":     {},
	"review":      {},
	"dod-recheck": {},
	"adversarial": {"Attack Summary"},
	"completion-audit": {"Product-Path Smoke", "Open Completion Gaps", "Decision"},
}

var requiresOverallVerdict = map[string]bool{
	"review":      true,
	"dod-recheck": true,
	"adversarial": true,
	"completion-audit": true,
}

var (
	sectionRe        = regexp.MustCompile(`(?m)^(#{1,3})\s+(.+)$`)
	overallVerdictRe = regexp.MustCompile(`(?m)^[- ]*\*{0,2}Overall Verdict\*{0,2}\s*:\s*(\w+)`)
	sepCellRe        = regexp.MustCompile(`^:?-{2,}:?$`)
	idColumnRe       = regexp.MustCompile(`(?i)^(?:AC\s*ID|GOAL\s*ID|REQ\s*ID|DEC\s*ID|TEMP\s*ID|id)$`)
	invalidIDRe      = regexp.MustCompile(`^[A-Z]{2,}[0-9]$`)
)

type tableRow struct {
	lineno int
	line   string
}

// ArtifactFormatCheck returns the artifact-format-check subcommand.
func ArtifactFormatCheck() *cli.Command {
	c := cli.NewCommand("artifact-format-check", "Validate structural format of skill workflow artifacts")
	var artifactType string
	var artifactPath string
	c.StringVar(&artifactType, "type", "", "", "artifact type (design|plan|trace|compose|review|dod-recheck|adversarial) (required)")
	c.StringArg(&artifactPath, "artifact-file", "Artifact file to validate")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if artifactType == "" {
			return fmt.Errorf("--type is required")
		}

		validType := false
		for _, t := range validArtifactTypes {
			if artifactType == t {
				validType = true
				break
			}
		}
		if !validType {
			return fmt.Errorf("invalid --type %q; must be one of: %s", artifactType, strings.Join(validArtifactTypes, "|"))
		}

		return exitCode(runArtifactFormatCheck(s.Stdout, artifactType, artifactPath))
	}
	return c
}

func runArtifactFormatCheck(w io.Writer, artifactType, artifactPath string) int {
	data, err := os.ReadFile(artifactPath)
	if err != nil {
		summary := fmt.Sprintf("Artifact file not found: %s", artifactPath)
		if !os.IsNotExist(err) {
			summary = fmt.Sprintf("Cannot read artifact file: %s", artifactPath)
		}
		log.Emit(w, log.Result{
			Tool:    artifactFormatCheckToolName,
			Status:  "FAIL",
			Code:    "ARTIFACT_FILE_NOT_FOUND",
			Summary: summary,
		},
			slog.Any("fix", []string{"FIX_ARTIFACT_FILE_PATH"}),
		)
		return 1
	}

	text := string(data)
	if strings.TrimSpace(text) == "" {
		log.Emit(w, log.Result{
			Tool:    artifactFormatCheckToolName,
			Status:  "FAIL",
			Code:    "ARTIFACT_FILE_EMPTY",
			Summary: fmt.Sprintf("Artifact file is empty: %s", artifactPath),
		},
			slog.Any("fix", []string{"FIX_WRITE_ARTIFACT_CONTENT"}),
		)
		return 1
	}

	lines := strings.Split(text, "\n")
	var issues []string

	// 1. Required sections
	for _, missing := range checkRequiredSections(lines, artifactType) {
		issues = append(issues, fmt.Sprintf("missing required section: ## %s", missing))
	}

	// 2. Overall Verdict (for applicable types)
	if requiresOverallVerdict[artifactType] {
		issues = append(issues, checkOverallVerdict(text)...)
	}

	// 3. Table structure
	issues = append(issues, checkTableStructure(lines)...)

	// 4. ID format
	issues = append(issues, checkIDFormat(lines)...)

	overall := "PASS"
	code := "ARTIFACT_FORMAT_VALID"
	summary := fmt.Sprintf("%s artifact passed all format checks.", artifactType)

	if len(issues) > 0 {
		overall = "FAIL"
		code = "ARTIFACT_FORMAT_VIOLATIONS"
		summary = fmt.Sprintf("%d format violation(s) in %s artifact.", len(issues), artifactType)
	}

	attrs := []slog.Attr{
		slog.String("signal.artifact_type", artifactType),
		slog.Int("signal.issues", len(issues)),
	}
	for i, issue := range issues {
		attrs = append(attrs, slog.String(fmt.Sprintf("issue.%d", i+1), issue))
	}
	if len(issues) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_ADD_MISSING_SECTION_HEADINGS",
			"FIX_REPAIR_TABLE_SEPARATOR_OR_COLUMN_COUNT",
			"FIX_USE_TWO_DIGIT_ID_SUFFIX",
		}))
	}

	log.Emit(w, log.Result{
		Tool:    artifactFormatCheckToolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(issues) > 0 {
		return 1
	}
	return 0
}

func checkRequiredSections(lines []string, artifactType string) []string {
	required := requiredSections[artifactType]
	if len(required) == 0 {
		return nil
	}

	var found []string
	for _, line := range lines {
		if m := sectionRe.FindStringSubmatch(line); m != nil {
			found = append(found, strings.ToLower(strings.TrimSpace(m[2])))
		}
	}

	var missing []string
	for _, req := range required {
		reqLower := strings.ToLower(req)
		matched := false
		for _, heading := range found {
			if strings.Contains(heading, reqLower) {
				matched = true
				break
			}
		}
		if !matched {
			missing = append(missing, req)
		}
	}
	return missing
}

func checkOverallVerdict(text string) []string {
	m := overallVerdictRe.FindStringSubmatch(text)
	if m == nil {
		return []string{"missing 'Overall Verdict: PASS | FAIL' metadata line"}
	}
	val := strings.ToUpper(m[1])
	if val != "PASS" && val != "FAIL" {
		return []string{fmt.Sprintf("Overall Verdict has invalid value: %q (must be PASS or FAIL)", val)}
	}
	return nil
}

func checkTableStructure(lines []string) []string {
	var issues []string
	var block []tableRow

	flush := func() {
		if len(block) >= 2 {
			issues = append(issues, validateTableBlock(block)...)
		}
		block = nil
	}

	for i, line := range lines {
		stripped := strings.TrimSpace(line)
		if strings.HasPrefix(stripped, "|") {
			block = append(block, tableRow{lineno: i + 1, line: stripped})
		} else {
			flush()
		}
	}
	flush()

	return issues
}

func validateTableBlock(block []tableRow) []string {
	if len(block) < 2 {
		return nil
	}

	firstLineno := block[0].lineno
	headerCols := len(parseCells(block[0].line))

	if !isSeparatorRow(parseCells(block[1].line)) {
		return []string{fmt.Sprintf(
			"table at line %d: row 2 is not a valid separator (got: %q)",
			firstLineno, truncate60(block[1].line),
		)}
	}

	var issues []string
	for _, row := range block[2:] {
		cols := len(parseCells(row.line))
		if cols != headerCols {
			issues = append(issues, fmt.Sprintf(
				"table at line %d: row at line %d has %d columns, expected %d",
				firstLineno, row.lineno, cols, headerCols,
			))
		}
	}
	return issues
}

func checkIDFormat(lines []string) []string {
	var issues []string
	var headers []string
	inTable := false

	for i, line := range lines {
		lineno := i + 1
		stripped := strings.TrimSpace(line)
		if strings.HasPrefix(stripped, "|") {
			cells := parseCells(stripped)
			if !inTable {
				headers = cells
				inTable = true
				continue
			}
			if isSeparatorRow(cells) {
				continue
			}
			// Data row: check ID columns
			for colIdx, cell := range cells {
				if colIdx >= len(headers) {
					break
				}
				if !idColumnRe.MatchString(strings.TrimSpace(headers[colIdx])) {
					continue
				}
				cellVal := strings.TrimSpace(cell)
				if invalidIDRe.MatchString(cellVal) {
					issues = append(issues, fmt.Sprintf(
						"line %d: ID %q in column %q uses 1-digit suffix; stable IDs require 2+ digits (e.g., AC01)",
						lineno, cellVal, strings.TrimSpace(headers[colIdx]),
					))
				}
			}
		} else {
			inTable = false
			headers = nil
		}
	}
	return issues
}

func truncate60(s string) string {
	if len(s) <= 60 {
		return s
	}
	return s[:60]
}
