package cmd

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"regexp"
	"sort"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const traceComposeCheckToolName = "trace-compose-check"

var (
	tccAtomPatterns = []*regexp.Regexp{
		regexp.MustCompile(`REQ[A-Za-z0-9_-]*[0-9]+`),
		regexp.MustCompile(`AC[A-Za-z0-9_-]*[0-9]+`),
		regexp.MustCompile(`GOAL[A-Za-z0-9_-]*[0-9]+`),
		regexp.MustCompile(`DEC[A-Za-z0-9_-]*[0-9]+`),
	}
	tccTEMPPattern = regexp.MustCompile(`TEMP[A-Za-z0-9_-]*[0-9]+`)
)

// TraceComposeCheck returns the trace-compose-check subcommand.
func TraceComposeCheck() *cli.Command {
	c := cli.NewCommand("trace-compose-check", "Cross-reference checks between design.md and plan.trace.md")
	c.Run = func(ctx context.Context, s *cli.State) error {
		if len(s.Args) < 2 {
			return fmt.Errorf("usage: skit trace-compose-check <design-file> <plan-trace-file>")
		}
		return exitCode(runTraceComposeCheck(os.Stdout, s.Args[0], s.Args[1]))
	}
	return c
}

func runTraceComposeCheck(w io.Writer, designPath, tracePath string) int {
	designData, err := os.ReadFile(designPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    traceComposeCheckToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s", designPath),
		}, slog.Any("fix", []string{"FIX_DESIGN_FILE_PATH"}))
		return 1
	}

	traceData, err := os.ReadFile(tracePath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    traceComposeCheckToolName,
			Status:  "FAIL",
			Code:    "TRACE_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Trace file not found: %s", tracePath),
		}, slog.Any("fix", []string{"FIX_TRACE_FILE_PATH"}))
		return 1
	}

	designText := string(designData)
	traceText := string(traceData)

	// Check B: Trace-XRef
	designAtoms := tccExtractDesignAtoms(designText)
	traceSection := extractSection(traceText, "Design -> Task Trace Matrix")
	traceAtoms := tccParseTraceMatrixAtoms(traceSection)
	bStatus, bSummary, bEvidence := tccCheckTraceXRef(designAtoms, traceAtoms)

	// Check C: AC-Ownership (derive ACs from already-built atom map, no second text scan)
	designACs := tccFilterACs(designAtoms)
	acSection := extractSection(traceText, "AC Ownership Map")
	acRows := parseGenericTable(acSection)
	cStatus, cSummary, cEvidence := tccCheckACOwnership(designACs, acRows)

	// Check D: TEMP-Trace
	designTemps := tccExtractDesignTemps(designText)
	tempSection := extractSection(traceText, "Temporary Mechanism Trace")
	traceTemps := tccParseTempTraceIDs(tempSection)
	dStatus, dSummary, dEvidence := tccCheckTempTrace(designTemps, traceTemps)

	type checkResult struct {
		id       string
		status   string
		summary  string
		evidence string
	}
	checks := []checkResult{
		{"Trace-XRef", bStatus, bSummary, bEvidence},
		{"AC-Ownership", cStatus, cSummary, cEvidence},
		{"TEMP-Trace", dStatus, dSummary, dEvidence},
	}

	failCount := 0
	for _, c := range checks {
		if c.status == "FAIL" {
			failCount++
		}
	}

	status := "PASS"
	code := "ALL_CHECKS_PASSED"
	summary := fmt.Sprintf("All %d trace/compose checks passed.", len(checks))
	if failCount > 0 {
		status = "FAIL"
		code = "TRACE_COMPOSE_CHECK_FAILED"
		summary = fmt.Sprintf("%d of %d trace/compose checks failed.", failCount, len(checks))
	}

	attrs := []slog.Attr{
		slog.Int("checks.total", len(checks)),
		slog.Int("checks.failed", failCount),
	}
	for i, c := range checks {
		n := i + 1
		attrs = append(attrs,
			slog.String(fmt.Sprintf("check.%d.id", n), c.id),
			slog.String(fmt.Sprintf("check.%d.status", n), c.status),
			slog.String(fmt.Sprintf("check.%d.summary", n), c.summary),
		)
		if c.evidence != "" {
			attrs = append(attrs, slog.String(fmt.Sprintf("check.%d.evidence", n), c.evidence))
		}
	}

	log.Emit(w, log.Result{
		Tool:    traceComposeCheckToolName,
		Status:  status,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if failCount > 0 {
		return 1
	}
	return 0
}

// tccExtractDesignAtoms extracts all REQ, AC, GOAL, DEC atoms from design text.
func tccExtractDesignAtoms(text string) map[string]struct{} {
	atoms := make(map[string]struct{})
	for _, re := range tccAtomPatterns {
		for _, m := range re.FindAllString(text, -1) {
			atoms[m] = struct{}{}
		}
	}
	return atoms
}

// tccFilterACs extracts AC IDs from a pre-built atom map without re-scanning the text.
func tccFilterACs(atoms map[string]struct{}) map[string]struct{} {
	acRe := tccAtomPatterns[1]
	acs := make(map[string]struct{})
	for k := range atoms {
		if acRe.MatchString(k) {
			acs[k] = struct{}{}
		}
	}
	return acs
}

// tccExtractDesignTemps extracts TEMP IDs from design text.
func tccExtractDesignTemps(text string) map[string]struct{} {
	temps := make(map[string]struct{})
	for _, m := range tccTEMPPattern.FindAllString(text, -1) {
		temps[m] = struct{}{}
	}
	return temps
}

// tccParseTraceMatrixAtoms parses `- ATOM: Task N` bullet lines from trace matrix section.
func tccParseTraceMatrixAtoms(section string) map[string]struct{} {
	atoms := make(map[string]struct{})
	for _, line := range strings.Split(section, "\n") {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "- ") {
			continue
		}
		payload := stripped[2:]
		colonPos := strings.Index(payload, ":")
		if colonPos < 0 {
			continue
		}
		atomPart := strings.TrimSpace(payload[:colonPos])
		for _, re := range tccAtomPatterns {
			for _, m := range re.FindAllString(atomPart, -1) {
				atoms[m] = struct{}{}
			}
		}
	}
	return atoms
}

// tccParseTempTraceIDs parses TEMP IDs from Temporary Mechanism Trace section (bullet or table).
func tccParseTempTraceIDs(section string) map[string]struct{} {
	temps := make(map[string]struct{})
	for _, line := range strings.Split(section, "\n") {
		stripped := strings.TrimSpace(line)
		if strings.HasPrefix(stripped, "- ") {
			payload := stripped[2:]
			colonPos := strings.Index(payload, ":")
			var atom string
			if colonPos >= 0 {
				atom = strings.TrimSpace(payload[:colonPos])
			} else {
				atom = strings.TrimSpace(payload)
			}
			for _, m := range tccTEMPPattern.FindAllString(atom, -1) {
				temps[m] = struct{}{}
			}
		} else if strings.HasPrefix(stripped, "|") {
			cells := parseCells(stripped)
			if len(cells) > 0 {
				for _, m := range tccTEMPPattern.FindAllString(cells[0], -1) {
					temps[m] = struct{}{}
				}
			}
		}
	}
	return temps
}

// tccCheckTraceXRef checks forward/reverse fidelity of design atoms in trace matrix.
func tccCheckTraceXRef(designAtoms, traceAtoms map[string]struct{}) (status, summary, evidence string) {
	missingForward := setDiff(designAtoms, traceAtoms)
	orphanReverse := setDiff(traceAtoms, designAtoms)

	var issues []string
	if len(missingForward) > 0 {
		issues = append(issues, "missing in trace: "+strings.Join(missingForward, ", "))
	}
	if len(orphanReverse) > 0 {
		issues = append(issues, "orphan in trace: "+strings.Join(orphanReverse, ", "))
	}
	if len(issues) > 0 {
		return "FAIL", "Design atom trace mismatch.", strings.Join(issues, "; ")
	}
	return "PASS", "All design atoms matched in trace matrix.", ""
}

// tccCheckACOwnership checks AC coverage in ownership map.
func tccCheckACOwnership(designACs map[string]struct{}, rows []map[string]string) (status, summary, evidence string) {
	mapACs := make(map[string]struct{})
	ownerByAC := make(map[string][]string)
	for _, row := range rows {
		acID := strings.TrimSpace(row["AC ID"])
		owner := strings.TrimSpace(row["Owner Task"])
		if acID != "" {
			mapACs[acID] = struct{}{}
			ownerByAC[acID] = append(ownerByAC[acID], owner)
		}
	}

	missing := setDiff(designACs, mapACs)
	phantom := setDiff(mapACs, designACs)
	var duplicates []string
	for ac, owners := range ownerByAC {
		if len(owners) > 1 {
			duplicates = append(duplicates, ac)
		}
	}
	sort.Strings(duplicates)

	var issues []string
	if len(missing) > 0 {
		issues = append(issues, "missing from ownership: "+strings.Join(missing, ", "))
	}
	if len(phantom) > 0 {
		issues = append(issues, "phantom in ownership: "+strings.Join(phantom, ", "))
	}
	if len(duplicates) > 0 {
		issues = append(issues, "duplicate owner: "+strings.Join(duplicates, ", "))
	}
	if len(issues) > 0 {
		return "FAIL", "AC ownership map mismatch.", strings.Join(issues, "; ")
	}
	return "PASS", "All design ACs covered in ownership map.", ""
}

// tccCheckTempTrace checks TEMP ID matching.
func tccCheckTempTrace(designTemps, traceTemps map[string]struct{}) (status, summary, evidence string) {
	missing := setDiff(designTemps, traceTemps)
	orphan := setDiff(traceTemps, designTemps)

	var issues []string
	if len(missing) > 0 {
		issues = append(issues, "missing in trace: "+strings.Join(missing, ", "))
	}
	if len(orphan) > 0 {
		issues = append(issues, "orphan in trace: "+strings.Join(orphan, ", "))
	}
	if len(issues) > 0 {
		return "FAIL", "TEMP ID trace mismatch.", strings.Join(issues, "; ")
	}
	return "PASS", "All TEMP IDs matched in trace.", ""
}

// setDiff returns sorted elements in a that are not in b.
func setDiff(a, b map[string]struct{}) []string {
	var result []string
	for k := range a {
		if _, ok := b[k]; !ok {
			result = append(result, k)
		}
	}
	sort.Strings(result)
	return result
}
