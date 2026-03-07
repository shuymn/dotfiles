package cmd

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"regexp"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const accToolName = "adversarial-coverage-check"

var (
	accRequiredTagRe     = regexp.MustCompile(`(?i)\[required\]`)
	accCategoryHeadingRe = regexp.MustCompile(`(?m)^##\s+\d+\.\s+(.+)$`)
	accVectorLineRe      = regexp.MustCompile(`(?m)^-\s+\*\*([^*]+)\*\*[^:]*:`)
	accSectionHeaderRe   = regexp.MustCompile(`(?i)(?:Selected(?:\s+Attack)?\s+Categor(?:y|ies)|Attack\s+Categor(?:y|ies))\s*:?$`)
)

type accVector struct {
	Name     string
	Required bool
}

// AdversarialCoverageCheck returns the adversarial-coverage-check subcommand.
func AdversarialCoverageCheck() *cli.Command {
	return &cli.Command{
		Name:        "adversarial-coverage-check",
		Description: "Check that all [required] attack vectors within selected categories are covered",
		Run: func(args []string) int {
			return runAdversarialCoverageCheck(os.Stdout, args)
		},
	}
}

func runAdversarialCoverageCheck(w io.Writer, args []string) int {
	var positional []string
	tier := ""

	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch {
		case arg == "--help" || arg == "-h":
			fmt.Fprintln(os.Stderr, "usage: skit adversarial-coverage-check <report-file> <attack-vectors-file> --tier Critical|Sensitive|Standard")
			return 0
		case arg == "--tier":
			if i+1 >= len(args) {
				fmt.Fprintln(os.Stderr, "error: --tier requires a value")
				return 1
			}
			i++
			tier = args[i]
		case strings.HasPrefix(arg, "--tier="):
			tier = strings.TrimPrefix(arg, "--tier=")
		case strings.HasPrefix(arg, "-"):
			fmt.Fprintf(os.Stderr, "error: unknown flag %q\n", arg)
			return 1
		default:
			positional = append(positional, arg)
		}
	}

	if len(positional) < 2 {
		fmt.Fprintln(os.Stderr, "usage: skit adversarial-coverage-check <report-file> <attack-vectors-file> --tier Critical|Sensitive|Standard")
		return 1
	}

	if tier == "" {
		fmt.Fprintln(os.Stderr, "error: --tier is required (Critical|Sensitive|Standard)")
		return 1
	}

	switch tier {
	case "Critical", "Sensitive", "Standard":
	default:
		fmt.Fprintf(os.Stderr, "error: invalid tier %q (must be Critical, Sensitive, or Standard)\n", tier)
		return 1
	}

	reportPath := positional[0]
	vectorsPath := positional[1]

	reportData, err := os.ReadFile(reportPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    accToolName,
			Status:  "FAIL",
			Code:    "REPORT_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Report file not found: %s", reportPath),
		}, slog.Any("fix", []string{"FIX_FILE_PATH"}))
		return 1
	}

	vectorsData, err := os.ReadFile(vectorsPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    accToolName,
			Status:  "FAIL",
			Code:    "ATTACK_VECTORS_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Attack vectors file not found: %s", vectorsPath),
		}, slog.Any("fix", []string{"FIX_FILE_PATH"}))
		return 1
	}

	if tier == "Standard" {
		log.Emit(w, log.Result{
			Tool:    accToolName,
			Status:  "SKIP",
			Code:    "STANDARD_TIER_NO_REQUIRED_COVERAGE",
			Summary: "Standard tier: no [required] vector coverage obligation.",
		})
		return 0
	}

	reportText := string(reportData)
	vectorsText := string(vectorsData)

	attackVectors := accParseAttackVectors(vectorsText)
	summaryRows := accParseAttackSummary(reportText)
	selected := accParseSelectedCategories(reportText, attackVectors)

	if len(selected) == 0 {
		log.Emit(w, log.Result{
			Tool:    accToolName,
			Status:  "SKIP",
			Code:    "NO_SELECTED_CATEGORIES",
			Summary: "Could not determine selected attack categories from Attack Summary.",
		})
		return 0
	}

	issues := accCheckCoverage(selected, attackVectors, summaryRows, tier)

	status := "PASS"
	code := "ALL_REQUIRED_VECTORS_COVERED"
	var summary string
	if len(issues) > 0 {
		status = "FAIL"
		code = "REQUIRED_VECTORS_NOT_COVERED"
		summary = fmt.Sprintf("%d [required] vector(s) uncovered for tier=%s.", len(issues), tier)
	} else {
		summary = fmt.Sprintf("All [required] vectors covered across %d selected categories (tier=%s).", len(selected), tier)
	}

	attrs := []slog.Attr{
		slog.String("signal.tier", tier),
		slog.Int("signal.selected_categories", len(selected)),
		slog.Int("signal.issues", len(issues)),
	}
	for i, cat := range selected {
		attrs = append(attrs, slog.String(fmt.Sprintf("category.%d", i+1), cat))
	}
	for i, issue := range issues {
		attrs = append(attrs, slog.String(fmt.Sprintf("issue.%d", i+1), issue))
	}
	if len(issues) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{"FIX_ADD_MISSING_PROBE_OR_DOCUMENT_NA_RATIONALE"}))
	}

	log.Emit(w, log.Result{
		Tool:    accToolName,
		Status:  status,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if status == "FAIL" {
		return 1
	}
	return 0
}

// accNormalize lowercases and collapses whitespace.
func accNormalize(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ToLower(s)
	return strings.Join(strings.Fields(s), " ")
}

// accParseAttackVectors parses attack-vectors.md.
// Returns map of {category_name: [{Name, Required}]}.
func accParseAttackVectors(text string) map[string][]accVector {
	result := make(map[string][]accVector)
	locs := accCategoryHeadingRe.FindAllStringSubmatchIndex(text, -1)
	for i, loc := range locs {
		cat := strings.TrimSpace(text[loc[2]:loc[3]])
		start := loc[1]
		var end int
		if i+1 < len(locs) {
			end = locs[i+1][0]
		} else {
			end = len(text)
		}
		sectionText := text[start:end]

		var vectors []accVector
		for _, vm := range accVectorLineRe.FindAllStringSubmatchIndex(sectionText, -1) {
			name := strings.TrimSpace(sectionText[vm[2]:vm[3]])
			lineStart := vm[0]
			lineEnd := strings.Index(sectionText[lineStart:], "\n")
			var line string
			if lineEnd < 0 {
				line = sectionText[lineStart:]
			} else {
				line = sectionText[lineStart : lineStart+lineEnd]
			}
			vectors = append(vectors, accVector{
				Name:     name,
				Required: accRequiredTagRe.MatchString(line),
			})
		}
		if len(vectors) > 0 {
			result[cat] = vectors
		}
	}
	return result
}

// accParseAttackSummary parses the ## Attack Summary table from the report.
func accParseAttackSummary(text string) []map[string]string {
	section := extractSection(text, "Attack Summary")
	if section == "" {
		return nil
	}
	return parseGenericTable(section)
}

// accParseSelectedCategories infers selected categories from the Attack Summary
// Category column, and optionally from an explicit category selection section.
func accParseSelectedCategories(text string, knownCats map[string][]accVector) []string {
	summaryRows := accParseAttackSummary(text)
	var found []string
	seen := make(map[string]bool)

	for _, row := range summaryRows {
		catText := accNormalize(row["Category"])
		for catName := range knownCats {
			catNorm := accNormalize(catName)
			if strings.Contains(catText, catNorm) || strings.Contains(catNorm, catText) {
				if !seen[catName] {
					seen[catName] = true
					found = append(found, catName)
				}
				break
			}
		}
	}

	// Also scan for an explicit category selection section.
	lines := strings.Split(text, "\n")
	inSection := false
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if inSection {
			if strings.HasPrefix(trimmed, "#") {
				break
			}
			stripped := strings.TrimLeft(trimmed, "-* ")
			for catName := range knownCats {
				if strings.Contains(accNormalize(stripped), accNormalize(catName)) {
					if !seen[catName] {
						seen[catName] = true
						found = append(found, catName)
					}
				}
			}
		}
		if accSectionHeaderRe.MatchString(trimmed) {
			inSection = true
		}
	}

	return found
}

// accIsCovered checks whether a vector name is present in the covered set,
// using partial string matching to tolerate minor naming variations.
func accIsCovered(name string, covered map[string]struct{}) bool {
	norm := accNormalize(name)
	for candidate := range covered {
		if strings.Contains(norm, candidate) || strings.Contains(candidate, norm) {
			return true
		}
	}
	return false
}

// accCheckCoverage returns a list of coverage issues.
// Only Critical/Sensitive tiers have [required] coverage obligations.
func accCheckCoverage(selected []string, vectors map[string][]accVector, rows []map[string]string, tier string) []string {
	if tier == "Standard" {
		return nil
	}

	covered := make(map[string]struct{})

	for _, row := range rows {
		vecName := accNormalize(row["Attack Vector"])
		if vecName == "" {
			continue
		}
		// A vector counts as covered whether probed (any result) or documented N/A.
		covered[vecName] = struct{}{}
	}

	var issues []string
	for _, cat := range selected {
		for _, v := range vectors[cat] {
			if !v.Required {
				continue
			}
			if !accIsCovered(v.Name, covered) {
				issues = append(issues, fmt.Sprintf(
					"[required] vector not covered in %q: %q — execute a probe or document non-applicability with rationale",
					cat, v.Name,
				))
			}
		}
	}
	return issues
}
