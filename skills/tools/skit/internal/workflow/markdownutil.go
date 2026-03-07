package workflow

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	mdSeparatorCellRe = regexp.MustCompile(`^:?-{2,}:?$`)
	mdBulletLineRe    = regexp.MustCompile(`^-\s+\S`)
)

func extractSection(text, title string) string {
	return extractSectionLevel(text, title, 2)
}

func extractSectionLevel(text, title string, level int) string {
	if level <= 0 {
		level = 2
	}

	hashes := strings.Repeat("#", level)
	pattern := regexp.MustCompile(`(?m)^` + regexp.QuoteMeta(hashes) + `\s+` + regexp.QuoteMeta(title) + `\s*$`)
	loc := pattern.FindStringIndex(text)
	if loc == nil {
		return ""
	}

	rest := text[loc[1]:]
	stopRe := regexp.MustCompile(fmt.Sprintf(`(?m)^#{1,%d}\s`, level))
	if endLoc := stopRe.FindStringIndex(rest); endLoc != nil {
		return strings.TrimSpace(rest[:endLoc[0]])
	}
	return strings.TrimSpace(rest)
}

func parseGenericTable(section string) []map[string]string {
	var tableLines []string
	for _, line := range strings.Split(section, "\n") {
		if trimmed := strings.TrimSpace(line); strings.HasPrefix(trimmed, "|") {
			tableLines = append(tableLines, trimmed)
		}
	}
	if len(tableLines) < 2 {
		return nil
	}

	rawHeaders := parseCells(tableLines[0])
	headers := make([]string, len(rawHeaders))
	for i, h := range rawHeaders {
		headers[i] = strings.TrimSpace(h)
	}

	if !isSeparatorRow(parseCells(tableLines[1])) {
		return nil
	}

	var rows []map[string]string
	for _, line := range tableLines[2:] {
		cells := parseCells(line)
		if len(cells) != len(headers) {
			continue
		}
		row := make(map[string]string, len(headers))
		for i, h := range headers {
			row[h] = strings.TrimSpace(cells[i])
		}
		rows = append(rows, row)
	}
	return rows
}

func parseTableHeaders(section string) []string {
	for _, line := range strings.Split(section, "\n") {
		trimmed := strings.TrimSpace(line)
		if !strings.HasPrefix(trimmed, "|") {
			continue
		}
		cells := parseCells(trimmed)
		headers := make([]string, len(cells))
		for i, c := range cells {
			headers[i] = strings.TrimSpace(c)
		}
		return headers
	}
	return nil
}

func parseCells(line string) []string {
	trimmed := strings.Trim(strings.TrimSpace(line), "|")
	parts := strings.Split(trimmed, "|")
	for i := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}
	return parts
}

func isSeparatorRow(cells []string) bool {
	if len(cells) == 0 {
		return false
	}
	for _, cell := range cells {
		if !mdSeparatorCellRe.MatchString(strings.TrimSpace(cell)) {
			return false
		}
	}
	return true
}

func parseKeyValueBullets(text string) map[string]string {
	result := make(map[string]string)
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, "-") {
			continue
		}
		payload := strings.TrimSpace(strings.TrimPrefix(line, "-"))
		idx := strings.Index(payload, ":")
		if idx < 0 {
			continue
		}
		key := strings.ReplaceAll(strings.TrimSpace(payload[:idx]), "**", "")
		value := strings.TrimSpace(payload[idx+1:])
		if key != "" {
			result[key] = value
		}
	}
	return result
}

func countBulletItems(text string) int {
	count := 0
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "<!--") {
			continue
		}
		if mdBulletLineRe.MatchString(line) {
			count++
		}
	}
	return count
}

func allEmpty(cells []string) bool {
	for _, c := range cells {
		if strings.TrimSpace(c) != "" {
			return false
		}
	}
	return true
}
