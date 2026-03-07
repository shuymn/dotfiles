package workflow

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/cli"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/log"
	"github.com/shuymn/dotfiles/skills/tools/skit/internal/model"
)

const verificationCmdCheckToolName = "verification-cmd-check"

// lookPathFn is the exec.LookPath function, replaceable in tests.
var lookPathFn = exec.LookPath

// VerificationCmdCheck returns the verification-cmd-check subcommand.
func VerificationCmdCheck() *cli.Command {
	c := cli.NewCommand("verification-cmd-check", "Validate Verification Command column in Acceptance Criteria table of a design document")
	var designFile string
	c.StringArg(&designFile, "design-file", "Design document to inspect")
	c.Run = func(ctx context.Context, s *cli.State) error {
		return exitCode(runVerificationCmdCheck(s.Stdout, designFile))
	}
	return c
}

func runVerificationCmdCheck(w io.Writer, designPath string) int {
	data, err := os.ReadFile(designPath)
	if err != nil {
		log.Emit(w, log.Result{
			Tool:    verificationCmdCheckToolName,
			Status:  "FAIL",
			Code:    "DESIGN_FILE_NOT_FOUND",
			Summary: fmt.Sprintf("Design file not found: %s", designPath),
		},
			slog.Any("fix", []string{"FIX_DESIGN_FILE_PATH"}),
		)
		return 1
	}

	section := extractSection(string(data), "Acceptance Criteria")
	if section == "" {
		log.Emit(w, log.Result{
			Tool:    verificationCmdCheckToolName,
			Status:  "SKIP",
			Code:    "NO_AC_TABLE",
			Summary: "No Acceptance Criteria table found in design file.",
		})
		return 0
	}

	rows := parseAcceptanceCriteriaRows(section)
	if len(rows) == 0 {
		log.Emit(w, log.Result{
			Tool:    verificationCmdCheckToolName,
			Status:  "SKIP",
			Code:    "NO_AC_TABLE",
			Summary: "No Acceptance Criteria table found in design file.",
		})
		return 0
	}

	var failures []string
	var advisories []string

	for _, row := range rows {
		status, msg := checkVerificationRow(row)
		switch status {
		case "FAIL":
			failures = append(failures, msg)
		case "TBD":
			advisories = append(advisories, msg)
		}
	}

	overall := "PASS"
	code := "ALL_VERIFICATION_COMMANDS_OK"
	summary := fmt.Sprintf("All %d AC(s) have valid verification commands.", len(rows))

	if len(failures) > 0 {
		overall = "FAIL"
		code = "VERIFICATION_CMD_ISSUES"
		summary = fmt.Sprintf("%d AC(s) have missing or unresolvable verification command(s).", len(failures))
	}

	attrs := []slog.Attr{
		slog.Int("signal.total_acs", len(rows)),
		slog.Int("signal.failures", len(failures)),
		slog.Int("signal.advisories", len(advisories)),
	}
	for i, msg := range failures {
		attrs = append(attrs, slog.String(fmt.Sprintf("fail.%d", i+1), msg))
	}
	for i, msg := range advisories {
		attrs = append(attrs, slog.String(fmt.Sprintf("advisory.%d", i+1), msg))
	}
	if len(failures) > 0 {
		attrs = append(attrs, slog.Any("fix", []string{
			"FIX_POPULATE_VERIFICATION_COMMAND",
			"FIX_INSTALL_MISSING_COMMAND_OR_USE_TBD_AT_PLAN",
		}))
	}

	log.Emit(w, log.Result{
		Tool:    verificationCmdCheckToolName,
		Status:  overall,
		Code:    code,
		Summary: summary,
	}, attrs...)

	if len(failures) > 0 {
		return 1
	}
	return 0
}

// checkVerificationRow checks a single AC row's Verification Command.
// Returns (status, message): status is "PASS", "TBD", or "FAIL".
func checkVerificationRow(row model.AcceptanceCriteriaRow) (string, string) {
	cmd := row.VerificationCommand
	acID := row.AcID
	if acID == "" {
		acID = "?"
	}

	if isNoneToken(cmd, defaultNoneTokens) {
		return "FAIL", fmt.Sprintf("%s: verification command is empty", acID)
	}

	if normalizeCompactToken(cmd) == "tbdatplan" {
		return "TBD", fmt.Sprintf("%s: TBD-at-plan (decompose-plan must resolve)", acID)
	}

	firstToken := strings.Fields(cmd)[0]
	if _, err := lookPathFn(firstToken); err != nil {
		return "FAIL", fmt.Sprintf("%s: command not found via command -v: %q", acID, firstToken)
	}

	return "PASS", ""
}
