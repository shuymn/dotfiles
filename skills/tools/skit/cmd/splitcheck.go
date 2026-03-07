package cmd

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
)

const scToolName = "split-check"

var (
	scNoneTokens = map[string]bool{
		"":    true,
		"-":   true,
		"none": true,
		"n/a": true,
		"na":  true,
	}

	scRequiredBoundaryColumns = []string{
		"Boundary",
		"Owns Requirements/AC",
		"Primary Verification Surface",
		"TEMP Lifecycle Group",
		"Parallel Stream",
		"Depends On",
	}

	scRequiredSubdocIndexColumns = []string{
		"Sub ID",
		"File",
		"Owned Boundary",
		"Owns Requirements/AC",
	}

	scWhitespaceRe   = regexp.MustCompile(`\s+`)
	scSlugRe         = regexp.MustCompile(`[^a-z0-9]+`)
	scDepsRe         = regexp.MustCompile(`[;,]`)
	scKeyValueLineRe = regexp.MustCompile(`^-\s*([^:]+):\s*(.+)$`)
	scBulletLineRe   = regexp.MustCompile(`^-\s+\S`)

	// Pre-compiled stop-pattern regexes for scExtractSection (level 2 and 3).
	scStopLevel2Re = regexp.MustCompile(`(?m)^#{1,2}\s`)
	scStopLevel3Re = regexp.MustCompile(`(?m)^#{1,3}\s`)
)

// SplitCheck returns the split-check subcommand.
func SplitCheck() *cli.Command {
	return &cli.Command{
		Name:        "split-check",
		Description: "Validate single/root-sub split decisions from structured design signals",
		Run: func(args []string) int {
			return runSplitCheck(os.Stdout, args)
		},
	}
}

func runSplitCheck(w io.Writer, args []string) int {
	if len(args) == 0 || args[0] == "--help" || args[0] == "-h" {
		fmt.Fprintln(os.Stderr, "usage: skit split-check <design-file>")
		return 0
	}

	if len(args) != 1 {
		log.Emit(w, log.Result{
			Tool:    scToolName,
			Status:  "FAIL",
			Code:    "INVALID_ARGUMENT_COUNT",
			Summary: "Usage: skit split-check <design-file>.",
		})
		return 1
	}

	designFile := args[0]
	data, err := os.ReadFile(designFile)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    scToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: `%s`.", designFile),
		})
		return 1
	}

	d := scParseDesignDoc(designFile, string(data))
	result := scAnalyzeDesignDoc(d)

	attrs := []slog.Attr{
		slog.String("split_decision", result.SplitDecision),
		slog.String("input.design_file", designFile),
	}

	// Signals in sorted order.
	signalKeys := make([]string, 0, len(result.Signals))
	for k := range result.Signals {
		signalKeys = append(signalKeys, k)
	}
	sort.Strings(signalKeys)
	for _, k := range signalKeys {
		attrs = append(attrs, slog.String("signal."+k, result.Signals[k]))
	}

	attrs = append(attrs, slog.Int("advisory.count", len(result.Advisories)))
	for i, advisory := range result.Advisories {
		attrs = append(attrs, slog.String(fmt.Sprintf("advisory.%d", i+1), advisory))
	}

	attrs = append(attrs, slog.Int("blocker.count", len(result.Blockers)))
	for i, blocker := range result.Blockers {
		attrs = append(attrs, slog.String(fmt.Sprintf("blocker.%d", i+1), blocker))
	}

	log.Emit(w, log.Result{
		Tool:    scToolName,
		Status:  result.Status,
		Code:    result.Code,
		Summary: result.Summary,
	}, attrs...)

	if result.Status == "PASS" {
		return 0
	}
	return 1
}

// --- data types ---

type scBoundaryRow struct {
	Boundary                   string
	OwnsRequirementsAC         string
	PrimaryVerificationSurface string
	TempLifecycleGroup         string
	ParallelStream             string
	DependsOn                  []string
}

func (r scBoundaryRow) NormalizedBoundary() string { return scNormalizeToken(r.Boundary) }

func (r scBoundaryRow) IsOwned() bool {
	n := scNormalizeToken(r.OwnsRequirementsAC)
	return !scNoneTokens[n] && n != "integration-only"
}

func (r scBoundaryRow) IsParallel() bool { return r.ParallelStream == "yes" }

type scSubdocIndexRow struct {
	SubID              string
	File               string
	OwnedBoundary      string
	OwnsRequirementsAC string
}

func (r scSubdocIndexRow) NormalizedBoundary() string { return scNormalizeToken(r.OwnedBoundary) }

type scSubdocInfo struct {
	Path          string
	OwnedBoundary string
	LocalReqCount int
	LocalACCount  int
	Errors        []string
}

func (s scSubdocInfo) NormalizedBoundary() string { return scNormalizeToken(s.OwnedBoundary) }

func (s scSubdocInfo) IsEffective() bool {
	return s.LocalReqCount > 0 && s.LocalACCount > 0
}

type scDesignDocData struct {
	DesignFile      string
	SplitDecision   string
	BoundaryRows    []scBoundaryRow
	SubdocIndexRows []scSubdocIndexRow
	Subdocs         []scSubdocInfo
	RootACCount     int
	Errors          []string
}

type scCheckResult struct {
	Status        string
	Code          string
	Summary       string
	Blockers      []string
	Advisories    []string
	Signals       map[string]string
	SplitDecision string
	DesignFile    string
}

// --- helpers ---

func scNormalizeToken(s string) string {
	return strings.ToLower(strings.TrimSpace(scWhitespaceRe.ReplaceAllString(s, " ")))
}

func scSlugify(s string) string {
	slug := strings.Trim(scSlugRe.ReplaceAllString(scNormalizeToken(s), "-"), "-")
	if slug == "" {
		return "unknown"
	}
	return slug
}

// scExtractSection extracts content of a ## (level=2) or ### (level=3) heading section.
func scExtractSection(text, title string, level int) string {
	hashes := strings.Repeat("#", level)
	pattern := regexp.MustCompile(`(?m)^` + regexp.QuoteMeta(hashes) + `\s+` + regexp.QuoteMeta(title) + `\s*$`)
	loc := pattern.FindStringIndex(text)
	if loc == nil {
		return ""
	}
	rest := text[loc[1]:]
	stopRe := scStopLevel2Re
	if level == 3 {
		stopRe = scStopLevel3Re
	}
	if endLoc := stopRe.FindStringIndex(rest); endLoc != nil {
		return strings.TrimSpace(rest[:endLoc[0]])
	}
	return strings.TrimSpace(rest)
}

func scParseKeyValueBullets(text string) map[string]string {
	result := make(map[string]string)
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if m := scKeyValueLineRe.FindStringSubmatch(line); m != nil {
			result[strings.TrimSpace(m[1])] = strings.TrimSpace(m[2])
		}
	}
	return result
}

func scCountBulletItems(text string) int {
	count := 0
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "<!--") {
			continue
		}
		if scBulletLineRe.MatchString(line) {
			count++
		}
	}
	return count
}

func scParseDependencies(value string) []string {
	if scNoneTokens[scNormalizeToken(value)] {
		return nil
	}
	parts := scDepsRe.Split(value, -1)
	var result []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}

func scResolveRepoRelativePath(designFile, relativePath string) string {
	if filepath.IsAbs(relativePath) {
		return relativePath
	}
	dir := filepath.Dir(designFile)
	seen := make(map[string]bool)
	for {
		if seen[dir] {
			break
		}
		seen[dir] = true
		candidate := filepath.Join(dir, relativePath)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	cwd, _ := os.Getwd()
	return filepath.Join(cwd, relativePath)
}

// scResolveBoundaryName returns the effective boundary name from a subdoc+index row pair,
// using a priority fallback: subdoc.OwnedBoundary → row.OwnedBoundary → row.SubID.
func scResolveBoundaryName(subdoc scSubdocInfo, row scSubdocIndexRow) string {
	if subdoc.OwnedBoundary != "" {
		return subdoc.OwnedBoundary
	}
	if row.OwnedBoundary != "" {
		return row.OwnedBoundary
	}
	return row.SubID
}

func scParseTableHeaders(section string) []string {
	for _, line := range strings.Split(section, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "|") {
			cells := parseCells(trimmed)
			headers := make([]string, len(cells))
			for i, c := range cells {
				headers[i] = strings.TrimSpace(c)
			}
			return headers
		}
	}
	return nil
}

func scColumnsMatch(actual, expected []string) bool {
	if len(actual) != len(expected) {
		return false
	}
	for i, h := range actual {
		if h != expected[i] {
			return false
		}
	}
	return true
}

func scQuoteColumns(cols []string) string {
	quoted := make([]string, len(cols))
	for i, c := range cols {
		quoted[i] = fmt.Sprintf("`%s`", c)
	}
	return strings.Join(quoted, ", ")
}

// --- parsing ---

func scParseSubdoc(path string) scSubdocInfo {
	data, err := os.ReadFile(path)
	if err != nil {
		return scSubdocInfo{
			Path:   path,
			Errors: []string{fmt.Sprintf("Sub-doc file is missing: `%s`.", path)},
		}
	}
	text := string(data)
	metadata := scParseKeyValueBullets(scExtractSection(text, "Sub-Doc Metadata", 2))
	localReqs := scCountBulletItems(scExtractSection(text, "Local Requirements", 2))
	localACRows := parseGenericTable(scExtractSection(text, "Local Acceptance Criteria", 2))

	var errors []string
	ownedBoundary := metadata["Owned Boundary"]
	if ownedBoundary == "" {
		errors = append(errors, fmt.Sprintf("Sub-doc `%s` is missing `Owned Boundary` metadata.", path))
	}
	return scSubdocInfo{
		Path:          path,
		OwnedBoundary: ownedBoundary,
		LocalReqCount: localReqs,
		LocalACCount:  len(localACRows),
		Errors:        errors,
	}
}

func scParseDesignDoc(designFile, text string) scDesignDocData {
	d := scDesignDocData{DesignFile: designFile}

	decompSection := scExtractSection(text, "Decomposition Strategy", 2)
	if decompSection == "" {
		d.Errors = append(d.Errors, "Design doc is missing `## Decomposition Strategy`.")
		return d
	}

	fields := scParseKeyValueBullets(decompSection)
	d.SplitDecision = scNormalizeToken(fields["Split Decision"])
	if d.SplitDecision != "single" && d.SplitDecision != "root-sub" {
		d.Errors = append(d.Errors, "`Split Decision` must be `single` or `root-sub`.")
	}

	// Parse Boundary Inventory.
	boundarySection := scExtractSection(decompSection, "Boundary Inventory", 3)
	if boundarySection == "" {
		d.Errors = append(d.Errors, "`## Decomposition Strategy` must include `### Boundary Inventory`.")
	} else {
		headers := scParseTableHeaders(boundarySection)
		if !scColumnsMatch(headers, scRequiredBoundaryColumns) {
			d.Errors = append(d.Errors, "`### Boundary Inventory` must use columns: "+scQuoteColumns(scRequiredBoundaryColumns)+".")
		}
		seenBoundaries := make(map[string]string)
		for _, row := range parseGenericTable(boundarySection) {
			boundary := strings.TrimSpace(row["Boundary"])
			if boundary == "" {
				d.Errors = append(d.Errors, "Boundary Inventory contains a row with an empty `Boundary` value.")
				continue
			}
			normBoundary := scNormalizeToken(boundary)
			if existing, ok := seenBoundaries[normBoundary]; ok {
				d.Errors = append(d.Errors, fmt.Sprintf(
					"Boundary Inventory repeats boundary `%s` (already used by `%s`).",
					boundary, existing,
				))
				continue
			}
			seenBoundaries[normBoundary] = boundary

			parallelStream := scNormalizeToken(row["Parallel Stream"])
			if parallelStream != "yes" && parallelStream != "no" {
				d.Errors = append(d.Errors, fmt.Sprintf(
					"Boundary Inventory row `%s` is invalid: parallel_stream: parallel_stream must be yes or no.",
					boundary,
				))
				continue
			}

			ownsReqsAC := strings.TrimSpace(row["Owns Requirements/AC"])
			primaryVS := strings.TrimSpace(row["Primary Verification Surface"])
			tempLG := strings.TrimSpace(row["TEMP Lifecycle Group"])

			var rowErrors []string
			if ownsReqsAC == "" {
				rowErrors = append(rowErrors, fmt.Sprintf(
					"Boundary Inventory row `%s` is invalid: owns_requirements_ac: owns_requirements_ac must be a non-empty string.",
					boundary,
				))
			}
			if primaryVS == "" {
				rowErrors = append(rowErrors, fmt.Sprintf(
					"Boundary Inventory row `%s` is invalid: primary_verification_surface: primary_verification_surface must be a non-empty string.",
					boundary,
				))
			}
			if tempLG == "" {
				rowErrors = append(rowErrors, fmt.Sprintf(
					"Boundary Inventory row `%s` is invalid: temp_lifecycle_group: temp_lifecycle_group must be a non-empty string.",
					boundary,
				))
			}
			if len(rowErrors) > 0 {
				d.Errors = append(d.Errors, rowErrors...)
				continue
			}

			d.BoundaryRows = append(d.BoundaryRows, scBoundaryRow{
				Boundary:                   boundary,
				OwnsRequirementsAC:         ownsReqsAC,
				PrimaryVerificationSurface: primaryVS,
				TempLifecycleGroup:         tempLG,
				ParallelStream:             parallelStream,
				DependsOn:                  scParseDependencies(row["Depends On"]),
			})
		}
	}

	// Count root Acceptance Criteria.
	acRows := parseGenericTable(scExtractSection(text, "Acceptance Criteria", 2))
	d.RootACCount = len(acRows)

	if d.SplitDecision != "root-sub" {
		return d
	}

	// Parse Sub-Doc Index.
	subdocSection := scExtractSection(decompSection, "Sub-Doc Index", 3)
	if subdocSection == "" {
		d.Errors = append(d.Errors, "`Split Decision: root-sub` requires `### Sub-Doc Index`.")
		return d
	}

	subdocHeaders := scParseTableHeaders(subdocSection)
	if !scColumnsMatch(subdocHeaders, scRequiredSubdocIndexColumns) {
		d.Errors = append(d.Errors, "`### Sub-Doc Index` must use columns: "+scQuoteColumns(scRequiredSubdocIndexColumns)+".")
	}

	seenSubdocBoundaries := make(map[string]string)
	for _, row := range parseGenericTable(subdocSection) {
		subID := strings.TrimSpace(row["Sub ID"])
		fileValue := strings.TrimSpace(row["File"])
		ownedBoundary := strings.TrimSpace(row["Owned Boundary"])
		ownsReqs := strings.TrimSpace(row["Owns Requirements/AC"])

		if subID == "" || fileValue == "" || ownedBoundary == "" {
			d.Errors = append(d.Errors, "Sub-Doc Index rows must populate `Sub ID`, `File`, and `Owned Boundary`.")
			continue
		}

		normBoundary := scNormalizeToken(ownedBoundary)
		if existing, ok := seenSubdocBoundaries[normBoundary]; ok {
			d.Errors = append(d.Errors, fmt.Sprintf(
				"Sub-Doc Index repeats owned boundary `%s` (already used by `%s`).",
				ownedBoundary, existing,
			))
		} else {
			seenSubdocBoundaries[normBoundary] = subID
		}

		if ownsReqs == "" {
			d.Errors = append(d.Errors, fmt.Sprintf(
				"Sub-Doc Index row `%s` is invalid: owns_requirements_ac: owns_requirements_ac must be a non-empty string.",
				subID,
			))
			continue
		}

		indexRow := scSubdocIndexRow{
			SubID:              subID,
			File:               fileValue,
			OwnedBoundary:      ownedBoundary,
			OwnsRequirementsAC: ownsReqs,
		}
		d.SubdocIndexRows = append(d.SubdocIndexRows, indexRow)

		subdocPath := scResolveRepoRelativePath(designFile, fileValue)
		subdoc := scParseSubdoc(subdocPath)
		if len(subdoc.Errors) > 0 {
			d.Errors = append(d.Errors, subdoc.Errors...)
		}
		if subdoc.OwnedBoundary != "" && subdoc.NormalizedBoundary() != indexRow.NormalizedBoundary() {
			d.Errors = append(d.Errors, fmt.Sprintf(
				"Sub-doc `%s` declares owned boundary `%s`, but Sub-Doc Index maps it to `%s`.",
				fileValue, subdoc.OwnedBoundary, ownedBoundary,
			))
		}
		d.Subdocs = append(d.Subdocs, subdoc)
	}

	return d
}

// --- signals and analysis ---

func scBuildSignals(d scDesignDocData) map[string]string {
	var ownedBoundaries []scBoundaryRow
	knownBoundaries := make(map[string]bool)
	for _, row := range d.BoundaryRows {
		knownBoundaries[row.NormalizedBoundary()] = true
		if row.IsOwned() {
			ownedBoundaries = append(ownedBoundaries, row)
		}
	}

	verificationSurfaces := make(map[string]bool)
	tempGroups := make(map[string]bool)
	type edge [2]string
	dependencyEdges := make(map[edge]bool)

	parallelCount := 0
	for _, row := range ownedBoundaries {
		if row.IsParallel() {
			parallelCount++
		}
		vs := scNormalizeToken(row.PrimaryVerificationSurface)
		if !scNoneTokens[vs] {
			verificationSurfaces[vs] = true
		}
		tg := scNormalizeToken(row.TempLifecycleGroup)
		if !scNoneTokens[tg] {
			tempGroups[tg] = true
		}
		normBoundary := row.NormalizedBoundary()
		for _, dep := range row.DependsOn {
			normDep := scNormalizeToken(dep)
			if knownBoundaries[normDep] && normDep != normBoundary {
				dependencyEdges[edge{normBoundary, normDep}] = true
			}
		}
	}

	var effectiveSubdocCount int
	for _, s := range d.Subdocs {
		if s.IsEffective() {
			effectiveSubdocCount++
		}
	}

	// Local AC distribution, keyed by boundary name.
	localACDist := make(map[string]int)
	for i, row := range d.SubdocIndexRows {
		if i >= len(d.Subdocs) {
			break
		}
		subdoc := d.Subdocs[i]
		localACDist[scResolveBoundaryName(subdoc, row)] = subdoc.LocalACCount
	}

	localACTotal := 0
	for _, count := range localACDist {
		localACTotal += count
	}

	signals := map[string]string{
		"owned_boundary_count":          strconv.Itoa(len(ownedBoundaries)),
		"verification_surface_count":    strconv.Itoa(len(verificationSurfaces)),
		"temp_lifecycle_group_count":    strconv.Itoa(len(tempGroups)),
		"parallelizable_boundary_count": strconv.Itoa(parallelCount),
		"dependency_edge_count":         strconv.Itoa(len(dependencyEdges)),
		"effective_subdoc_count":        strconv.Itoa(effectiveSubdocCount),
		"root_integration_ac_count":     strconv.Itoa(d.RootACCount),
		"local_ac_total":                strconv.Itoa(localACTotal),
	}

	boundaries := make([]string, 0, len(localACDist))
	for boundary := range localACDist {
		boundaries = append(boundaries, boundary)
	}
	sort.Slice(boundaries, func(i, j int) bool {
		return scSlugify(boundaries[i]) < scSlugify(boundaries[j])
	})
	for _, boundary := range boundaries {
		signals[fmt.Sprintf("local_ac.%s", scSlugify(boundary))] = strconv.Itoa(localACDist[boundary])
	}

	return signals
}

func scAnalyzeDesignDoc(d scDesignDocData) scCheckResult {
	blockers := append([]string{}, d.Errors...)
	var advisories []string
	signals := scBuildSignals(d)

	ownedBoundaryCount, _ := strconv.Atoi(signals["owned_boundary_count"])
	verificationSurfaceCount, _ := strconv.Atoi(signals["verification_surface_count"])
	tempGroupCount, _ := strconv.Atoi(signals["temp_lifecycle_group_count"])
	parallelCount, _ := strconv.Atoi(signals["parallelizable_boundary_count"])
	depEdgeCount, _ := strconv.Atoi(signals["dependency_edge_count"])
	effectiveSubdocCount, _ := strconv.Atoi(signals["effective_subdoc_count"])
	rootACCount, _ := strconv.Atoi(signals["root_integration_ac_count"])
	localACTotal, _ := strconv.Atoi(signals["local_ac_total"])

	if ownedBoundaryCount == 0 {
		blockers = append(blockers, "Boundary Inventory must include at least one boundary that owns requirements/AC.")
	}

	if d.SplitDecision == "single" {
		var triggers []string
		if verificationSurfaceCount >= 2 {
			triggers = append(triggers, fmt.Sprintf("%d verification surfaces", verificationSurfaceCount))
		}
		if tempGroupCount >= 2 {
			triggers = append(triggers, fmt.Sprintf("%d TEMP lifecycle groups", tempGroupCount))
		}
		if parallelCount >= 2 {
			triggers = append(triggers, fmt.Sprintf("%d parallel streams", parallelCount))
		}
		if ownedBoundaryCount >= 2 && len(triggers) > 0 {
			blockers = append(blockers, fmt.Sprintf(
				"`Split Decision: single` is inconsistent with Boundary Inventory: %d owned boundaries and %s.",
				ownedBoundaryCount, strings.Join(triggers, ", "),
			))
		}
	}

	if d.SplitDecision == "root-sub" {
		// Check 1:1 match between owned Boundary Inventory rows and Sub-Doc Index.
		inventoryBoundaries := make(map[string]string)
		for _, row := range d.BoundaryRows {
			if row.IsOwned() {
				inventoryBoundaries[row.NormalizedBoundary()] = row.Boundary
			}
		}
		indexBoundaries := make(map[string]string)
		for _, row := range d.SubdocIndexRows {
			indexBoundaries[row.NormalizedBoundary()] = row.OwnedBoundary
		}

		var missingInIndex, extraInIndex []string
		for norm := range inventoryBoundaries {
			if _, ok := indexBoundaries[norm]; !ok {
				missingInIndex = append(missingInIndex, norm)
			}
		}
		for norm := range indexBoundaries {
			if _, ok := inventoryBoundaries[norm]; !ok {
				extraInIndex = append(extraInIndex, norm)
			}
		}
		sort.Strings(missingInIndex)
		sort.Strings(extraInIndex)

		if len(missingInIndex) > 0 || len(extraInIndex) > 0 {
			var messages []string
			if len(missingInIndex) > 0 {
				quoted := make([]string, len(missingInIndex))
				for i, norm := range missingInIndex {
					quoted[i] = fmt.Sprintf("`%s`", inventoryBoundaries[norm])
				}
				messages = append(messages, "missing in Sub-Doc Index: "+strings.Join(quoted, ", "))
			}
			if len(extraInIndex) > 0 {
				quoted := make([]string, len(extraInIndex))
				for i, norm := range extraInIndex {
					quoted[i] = fmt.Sprintf("`%s`", indexBoundaries[norm])
				}
				messages = append(messages, "extra in Sub-Doc Index: "+strings.Join(quoted, ", "))
			}
			blockers = append(blockers, "Boundary Inventory and Sub-Doc Index must match 1:1 for sub-owned boundaries ("+strings.Join(messages, "; ")+").")
		}

		if effectiveSubdocCount < 2 {
			blockers = append(blockers, "`Split Decision: root-sub` requires at least 2 effective sub-docs with both Local Requirements and Local Acceptance Criteria.")
		}

		// Advisories.
		if localACTotal > 0 {
			var largestBoundary string
			largestCount := 0
			for i, row := range d.SubdocIndexRows {
				if i >= len(d.Subdocs) {
					break
				}
				subdoc := d.Subdocs[i]
				if subdoc.LocalACCount > largestCount {
					largestCount = subdoc.LocalACCount
					largestBoundary = scResolveBoundaryName(subdoc, row)
				}
			}
			if float64(largestCount)/float64(localACTotal) > 0.70 {
				advisories = append(advisories, fmt.Sprintf(
					"Local ACs are concentrated in `%s` (%d/%d); root-sub may still be too coarse.",
					largestBoundary, largestCount, localACTotal,
				))
			}
		}

		if localACTotal > 0 && rootACCount >= localACTotal {
			advisories = append(advisories, "Root integration AC count is greater than or equal to total local AC count; integration scope may be dominating the split.")
		}

		if ownedBoundaryCount > 0 && depEdgeCount > ownedBoundaryCount {
			advisories = append(advisories, "Cross-boundary dependency edges exceed owned boundary count; the split may be too tightly coupled.")
		}
	}

	if len(blockers) > 0 {
		return scCheckResult{
			Status:        "FAIL",
			Code:          "SPLIT_CONFLICT",
			Summary:       "Split decision blockers found.",
			Blockers:      blockers,
			Advisories:    advisories,
			Signals:       signals,
			SplitDecision: coalesce(d.SplitDecision, "unknown"),
			DesignFile:    d.DesignFile,
		}
	}

	summary := "Split decision signals are consistent."
	if len(advisories) > 0 {
		summary = "Split decision passes with advisories."
	}
	return scCheckResult{
		Status:        "PASS",
		Code:          "PASS",
		Summary:       summary,
		Blockers:      nil,
		Advisories:    advisories,
		Signals:       signals,
		SplitDecision: coalesce(d.SplitDecision, "unknown"),
		DesignFile:    d.DesignFile,
	}
}
