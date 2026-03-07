package workflow

import (
	"regexp"
	"sort"
	"strings"
)

var (
	tokenWhitespaceRe = regexp.MustCompile(`\s+`)

	defaultNoneTokens = newTokenSet("", "-", "none", "n/a", "na")
	tbdNoneTokens     = newTokenSet("", "-", "none", "n/a", "na", "tbd", "tbd-at-plan")
)

func normalizeToken(s string) string {
	return strings.ToLower(strings.TrimSpace(tokenWhitespaceRe.ReplaceAllString(s, " ")))
}

func normalizeCompactToken(s string) string {
	replacer := strings.NewReplacer("-", "", "_", "", " ", "")
	return replacer.Replace(normalizeToken(s))
}

func coalesce(vals ...string) string {
	for _, v := range vals {
		if t := strings.TrimSpace(v); t != "" {
			return t
		}
	}
	return ""
}

func newTokenSet(tokens ...string) map[string]struct{} {
	result := make(map[string]struct{}, len(tokens))
	for _, token := range tokens {
		result[normalizeToken(token)] = struct{}{}
	}
	return result
}

func isNoneToken(value string, tokenSet map[string]struct{}) bool {
	_, ok := tokenSet[normalizeToken(value)]
	return ok
}

func dedupStrings(items []string) []string {
	seen := make(map[string]bool, len(items))
	var result []string
	for _, item := range items {
		if !seen[item] {
			seen[item] = true
			result = append(result, item)
		}
	}
	return result
}

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
