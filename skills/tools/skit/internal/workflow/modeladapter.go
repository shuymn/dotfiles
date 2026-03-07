package workflow

import (
	"regexp"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/model"
)

var adapterDepsRe = regexp.MustCompile(`[;,]`)

func parseAcceptanceCriteriaRows(section string) []model.AcceptanceCriteriaRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.AcceptanceCriteriaRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.AcceptanceCriteriaRow{
			AcID:                coalesce(row["AC ID"], row["ac_id"]),
			EarsType:            coalesce(row["EARS Type"], row["ears_type"]),
			ContractType:        coalesce(row["Contract Type"], row["contract_type"]),
			RequirementSentence: coalesce(row["Requirement Sentence"], row["requirement_sentence"]),
			VerificationIntent:  coalesce(row["Verification Intent"], row["verification_intent"]),
			VerificationCommand: coalesce(row["Verification Command"], row["verification_command"], row["Verification"]),
		})
	}
	return rows
}

func parseRiskClassificationRows(section string) []model.RiskClassificationRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.RiskClassificationRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.RiskClassificationRow{
			Area:            coalesce(row["Area"], row["area"]),
			RiskTier:        coalesce(row["Risk Tier"], row["risk_tier"]),
			ChangeRationale: coalesce(row["Change Rationale"], row["change_rationale"]),
		})
	}
	return rows
}

func parseBoundaryInventoryRows(section string) []model.BoundaryInventoryRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.BoundaryInventoryRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.BoundaryInventoryRow{
			Boundary:                   coalesce(row["Boundary"], row["boundary"]),
			OwnsRequirementsAC:         coalesce(row["Owns Requirements/AC"], row["owns_requirements_ac"]),
			PrimaryVerificationSurface: coalesce(row["Primary Verification Surface"], row["primary_verification_surface"]),
			TempLifecycleGroup:         coalesce(row["TEMP Lifecycle Group"], row["temp_lifecycle_group"]),
			ParallelStream:             coalesce(row["Parallel Stream"], row["parallel_stream"]),
			DependsOn:                  parseDelimitedValues(coalesce(row["Depends On"], row["depends_on"]), adapterDepsRe, defaultNoneTokens),
		})
	}
	return rows
}

func parseSubDocIndexRows(section string) []model.SubDocIndexRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.SubDocIndexRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.SubDocIndexRow{
			SubID:              coalesce(row["Sub ID"], row["sub_id"]),
			File:               coalesce(row["File"], row["file"]),
			OwnedBoundary:      coalesce(row["Owned Boundary"], row["owned_boundary"]),
			OwnsRequirementsAC: coalesce(row["Owns Requirements/AC"], row["owns_requirements_ac"]),
		})
	}
	return rows
}

func parseTemporaryMechanismIndexRows(section string) []model.TemporaryMechanismIndexRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.TemporaryMechanismIndexRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.TemporaryMechanismIndexRow{
			ID:              coalesce(row["ID"], row["id"], row["Temp ID"], row["TEMP ID"], row["TempID"]),
			Mechanism:       coalesce(row["Mechanism"], row["mechanism"]),
			LifecycleRecord: coalesce(row["Lifecycle Record"], row["lifecycle_record"], row["Lifecycle"], row["ADR/Ledger"]),
			Status:          coalesce(row["Status"], row["status"]),
		})
	}
	return rows
}

func parseSunsetClosureChecklistRows(section string) []model.SunsetClosureChecklistRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.SunsetClosureChecklistRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.SunsetClosureChecklistRow{
			ID:                     coalesce(row["ID"], row["id"], row["Temp ID"], row["TEMP ID"], row["TempID"]),
			IntroducedFor:          coalesce(row["Introduced for"], row["Introduced For"], row["introduced_for"]),
			RetirementTrigger:      coalesce(row["Retirement Trigger"], row["retirement_trigger"], row["Trigger"]),
			RetirementVerification: coalesce(row["Retirement Verification"], row["retirement_verification"], row["Verification"]),
			RemovalScope:           coalesce(row["Removal Scope"], row["removal_scope"], row["Scope"]),
		})
	}
	return rows
}

func parseAcOwnershipMapRows(section string) []model.AcOwnershipMapRow {
	rawRows := parseGenericTable(section)
	rows := make([]model.AcOwnershipMapRow, 0, len(rawRows))
	for _, row := range rawRows {
		rows = append(rows, model.AcOwnershipMapRow{
			AcID:         coalesce(row["AC ID"], row["ac_id"]),
			OwnerTask:    coalesce(row["Owner Task"], row["owner_task"]),
			Contributors: coalesce(row["Contributors"], row["contributors"]),
			HasRedForAC:  coalesce(row["Has Red For AC"], row["has_red_for_ac"]),
		})
	}
	return rows
}

func parseDelimitedValues(value string, splitter *regexp.Regexp, noneTokens map[string]struct{}) []string {
	if isNoneToken(value, noneTokens) {
		return nil
	}

	parts := splitter.Split(value, -1)
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		part = coalesce(part)
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}
