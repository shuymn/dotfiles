package cli

import (
	"flag"
	"fmt"
	"strings"
)

var preEncodedFragments = []string{
	"%00", "%01", "%02", "%03", "%04", "%05", "%06", "%07",
	"%08", "%09", "%0a", "%0b", "%0c", "%0d", "%0e", "%0f",
	"%10", "%11", "%12", "%13", "%14", "%15", "%16", "%17",
	"%18", "%19", "%1a", "%1b", "%1c", "%1d", "%1e", "%1f",
	"%2e", "%2f", "%5c", "%7f",
}

func validateInputs(fs *flag.FlagSet) error {
	var firstErr error
	fs.VisitAll(func(f *flag.Flag) {
		if firstErr != nil {
			return
		}
		value := f.Value.String()
		switch {
		case containsControlChars(value):
			firstErr = fmt.Errorf("flag --%s contains control characters", f.Name)
		case containsPreEncoded(value):
			firstErr = fmt.Errorf("flag --%s contains pre-encoded control or path characters", f.Name)
		}
	})
	if firstErr != nil {
		return firstErr
	}

	for index, arg := range fs.Args() {
		switch {
		case containsControlChars(arg):
			return fmt.Errorf("argument %d contains control characters", index+1)
		case containsPreEncoded(arg):
			return fmt.Errorf("argument %d contains pre-encoded control or path characters", index+1)
		}
	}
	return nil
}

func containsControlChars(s string) bool {
	for i := 0; i < len(s); i++ {
		b := s[i]
		if b == '\t' || b == '\n' || b == '\r' {
			continue
		}
		if b < 0x20 || b == 0x7f {
			return true
		}
	}
	return false
}

func containsPreEncoded(s string) bool {
	lower := strings.ToLower(s)
	for _, fragment := range preEncodedFragments {
		if strings.Contains(lower, fragment) {
			return true
		}
	}
	return false
}

func containsHelpArg(args []string) bool {
	for _, arg := range args {
		if arg == "--" {
			return false
		}
		if isHelpToken(arg) {
			return true
		}
	}
	return false
}

func splitFlagToken(token string) (name, value string, hasValue bool) {
	name, value, hasValue = strings.Cut(token, "=")
	return name, value, hasValue
}

func isFlagLike(arg string) bool {
	return strings.HasPrefix(arg, "-") && arg != ""
}

func isHelpToken(arg string) bool {
	return arg == "--help" || arg == "-h"
}
