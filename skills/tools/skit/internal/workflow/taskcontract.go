package workflow

import (
	"crypto/sha256"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

var (
	taskEndRe          = regexp.MustCompile(`(?m)^(### Task \d+|## )`)
	taskHeadingOnlyRe  = regexp.MustCompile(`(?m)^### Task (\d+)\b[^\n]*\n`)
	taskHeadingLineRe  = regexp.MustCompile(`(?m)^### Task (\d+):\s*(.+)$`)
	taskFieldLineReTpl = `(?m)^(?:-\s+)?\*\*%s\*\*:\s*(.*)$`
)

type scopeEntry struct {
	Pattern   string
	Rationale string
}

type scopeContract struct {
	Owned      []scopeEntry
	Shared     []scopeEntry
	Prohibited []scopeEntry
}

type taskContract struct {
	ID                  int
	Block               string
	RiskTier            string
	Dependencies        []string
	Scope               scopeContract
	BoundaryVerification string
	ClosureVerification  string
}

func extractTaskBlock(planText string, taskID int) string {
	headerRe := regexp.MustCompile(`(?m)^### Task 0*` + strconv.Itoa(taskID) + `\b[^\n]*\n`)
	loc := headerRe.FindStringIndex(planText)
	if loc == nil {
		return ""
	}
	rest := planText[loc[1]:]
	endLoc := taskEndRe.FindStringIndex(rest)
	if endLoc == nil {
		return planText[loc[0]:]
	}
	return planText[loc[0] : loc[1]+endLoc[0]]
}

func extractTaskBlocks(planText string) []taskContract {
	var tasks []taskContract
	for _, m := range taskHeadingLineRe.FindAllStringSubmatch(planText, -1) {
		id, err := strconv.Atoi(m[1])
		if err != nil {
			continue
		}
		block := extractTaskBlock(planText, id)
		if block == "" {
			continue
		}
		tasks = append(tasks, parseTaskContract(id, block))
	}
	return tasks
}

func extractFieldValue(block, fieldName string) string {
	re := regexp.MustCompile(fmt.Sprintf(taskFieldLineReTpl, regexp.QuoteMeta(fieldName)))
	m := re.FindStringSubmatch(block)
	if m == nil {
		return ""
	}
	return strings.TrimSpace(m[1])
}

func extractFieldList(block, fieldName string) []string {
	re := regexp.MustCompile(`(?m)^-?\s*\*\*` + regexp.QuoteMeta(fieldName) + `\*\*:\s*\n((?:[ \t]+-[^\n]*\n?)*)`)
	m := re.FindStringSubmatch(block)
	if m == nil {
		return nil
	}
	return strings.Split(m[1], "\n")
}

func parseScopeList(block, fieldName string, rationaleRequired bool) ([]scopeEntry, []string) {
	lines := extractFieldList(block, fieldName)
	var entries []scopeEntry
	var issues []string
	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "- ") {
			continue
		}
		entry, ok := parseScopeEntry(strings.TrimSpace(stripped[2:]))
		if !ok {
			issues = append(issues, fmt.Sprintf("%s contains an invalid entry: %q", fieldName, stripped))
			continue
		}
		if rationaleRequired && entry.Rationale == "" {
			issues = append(issues, fmt.Sprintf("%s entry %q is missing a rationale", fieldName, entry.Pattern))
		}
		entries = append(entries, entry)
	}
	return entries, issues
}

func parseScopeEntry(payload string) (scopeEntry, bool) {
	payload = strings.TrimSpace(payload)
	if payload == "" {
		return scopeEntry{}, false
	}

	pattern := ""
	rest := ""
	if strings.HasPrefix(payload, "`") {
		end := strings.Index(payload[1:], "`")
		if end < 0 {
			return scopeEntry{}, false
		}
		pattern = payload[1 : end+1]
		rest = strings.TrimSpace(payload[end+2:])
	} else {
		fields := strings.Fields(payload)
		if len(fields) == 0 {
			return scopeEntry{}, false
		}
		pattern = fields[0]
		rest = strings.TrimSpace(strings.TrimPrefix(payload, pattern))
	}

	rest = strings.TrimSpace(rest)
	rationale := ""
	switch {
	case strings.HasPrefix(rest, "(") && strings.HasSuffix(rest, ")"):
		rationale = strings.TrimSpace(rest[1 : len(rest)-1])
	case strings.HasPrefix(rest, "—"):
		rationale = strings.TrimSpace(strings.TrimPrefix(rest, "—"))
	case strings.HasPrefix(rest, "-"):
		rationale = strings.TrimSpace(strings.TrimPrefix(rest, "-"))
	}

	return scopeEntry{Pattern: pattern, Rationale: rationale}, true
}

func parseScopeContract(block string) (scopeContract, []string) {
	owned, ownedIssues := parseScopeList(block, "Owned Paths", false)
	shared, sharedIssues := parseScopeList(block, "Shared Touchpoints", true)
	prohibited, prohibitedIssues := parseScopeList(block, "Prohibited Paths", false)
	return scopeContract{
		Owned:      owned,
		Shared:     shared,
		Prohibited: prohibited,
	}, append(append(ownedIssues, sharedIssues...), prohibitedIssues...)
}

func parseDependencies(block string) []string {
	value := extractFieldValue(block, "Dependencies")
	if value == "" || strings.EqualFold(value, "none") {
		return nil
	}
	var deps []string
	for _, part := range strings.Split(value, ",") {
		trimmed := strings.TrimSpace(part)
		if trimmed == "" || strings.EqualFold(trimmed, "none") {
			continue
		}
		deps = append(deps, trimmed)
	}
	return deps
}

func parseTaskContract(taskID int, block string) taskContract {
	scope, _ := parseScopeContract(block)
	return taskContract{
		ID:                   taskID,
		Block:                block,
		RiskTier:             extractFieldValue(block, "Risk Tier"),
		Dependencies:         parseDependencies(block),
		Scope:                scope,
		BoundaryVerification: extractTaskFieldBlock(block, "Boundary Verification"),
		ClosureVerification:  extractTaskFieldBlock(block, "Closure Verification"),
	}
}

func computeTaskContractDigest(block string) string {
	normalized := strings.TrimSpace(block)
	sum := sha256.Sum256([]byte(normalized))
	return fmt.Sprintf("%x", sum)
}

func parseImplementationFiles(text string) []string {
	lines := extractFieldList(text, "Implementation Files")
	if len(lines) == 0 {
		return nil
	}
	var files []string
	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if !strings.HasPrefix(stripped, "- ") {
			continue
		}
		payload := strings.TrimSpace(stripped[2:])
		if payload == "" {
			continue
		}
		if strings.HasPrefix(payload, "`") {
			if end := strings.Index(payload[1:], "`"); end >= 0 {
				files = append(files, payload[1:end+1])
				continue
			}
		}
		fields := strings.Fields(payload)
		if len(fields) > 0 {
			files = append(files, fields[0])
		}
	}
	return files
}

func extractTaskFieldBlock(block, fieldName string) string {
	lines := extractFieldList(block, fieldName)
	if len(lines) > 0 {
		var items []string
		for _, line := range lines {
			stripped := strings.TrimSpace(line)
			if stripped != "" {
				items = append(items, stripped)
			}
		}
		return strings.Join(items, "\n")
	}
	return extractFieldValue(block, fieldName)
}
