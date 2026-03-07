package template

import (
	"fmt"
	"strings"

	"github.com/shuymn/dotfiles/skills/tools/skit/internal/model"
)

// RenderMarkdownTable renders a padded Markdown table from headers and rows.
func RenderMarkdownTable(headers []string, rows [][]string) string {
	widths := make([]int, len(headers))
	for i, h := range headers {
		widths[i] = len(h)
	}
	for _, row := range rows {
		for i, val := range row {
			if len(val) > widths[i] {
				widths[i] = len(val)
			}
		}
	}

	var parts []string

	// Header line.
	headerCells := make([]string, len(headers))
	for i, h := range headers {
		headerCells[i] = h + strings.Repeat(" ", widths[i]-len(h))
	}
	parts = append(parts, "| "+strings.Join(headerCells, " | ")+" |")

	// Separator line.
	sepCells := make([]string, len(headers))
	for i := range headers {
		sepCells[i] = strings.Repeat("-", widths[i])
	}
	parts = append(parts, "|-"+strings.Join(sepCells, "-|-")+"-|")

	// Body rows.
	for _, row := range rows {
		cells := make([]string, len(row))
		for i, val := range row {
			cells[i] = val + strings.Repeat(" ", widths[i]-len(val))
		}
		parts = append(parts, "| "+strings.Join(cells, " | ")+" |")
	}

	return strings.Join(parts, "\n")
}

// RenderBullets renders a bullet list from items.
func RenderBullets(items []string) string {
	lines := make([]string, len(items))
	for i, item := range items {
		lines[i] = "- " + item
	}
	return strings.Join(lines, "\n")
}

// RenderInlineList returns a comma-joined string or "none" if items is empty.
func RenderInlineList(items []string) string {
	if len(items) == 0 {
		return "none"
	}
	return strings.Join(items, ", ")
}

func renderClarifications(rows []model.ClarificationRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.Question, r.AnswerOrAssumption, r.Impact, r.Status}
	}
	return RenderMarkdownTable(
		[]string{"Question", "Answer / Assumption", "Impact", "Status"},
		data,
	)
}

func renderExistingCodebaseConstraints(rows []model.ExistingCodebaseConstraintRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.ConstraintID, r.Source, r.Constraint, r.ImpactOnDesign, r.RequiredVerification}
	}
	return RenderMarkdownTable(
		[]string{"Constraint ID", "Source (file/test)", "Constraint", "Impact on Design", "Required Verification"},
		data,
	)
}

func renderRiskClassification(rows []model.RiskClassificationRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.Area, r.RiskTier, r.ChangeRationale}
	}
	return RenderMarkdownTable(
		[]string{"Area", "Risk Tier", "Change Rationale"},
		data,
	)
}

func renderBoundaryInventory(rows []model.BoundaryInventoryRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{
			r.Boundary,
			r.OwnsRequirementsAC,
			r.PrimaryVerificationSurface,
			r.TempLifecycleGroup,
			r.ParallelStream,
			r.DependsOnDisplay(),
		}
	}
	return RenderMarkdownTable(
		[]string{"Boundary", "Owns Requirements/AC", "Primary Verification Surface", "TEMP Lifecycle Group", "Parallel Stream", "Depends On"},
		data,
	)
}

func renderSubDocIndex(rows []model.SubDocIndexRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.SubID, r.File, r.OwnedBoundary, r.OwnsRequirementsAC}
	}
	return RenderMarkdownTable(
		[]string{"Sub ID", "File", "Owned Boundary", "Owns Requirements/AC"},
		data,
	)
}

func renderRootCoverage(rows []model.RootCoverageRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.RootRequirementAC, r.CoveredBy, r.Notes}
	}
	return RenderMarkdownTable(
		[]string{"Root Requirement/AC", "Covered By (Sub ID or Integration)", "Notes"},
		data,
	)
}

func renderTemporaryMechanismIndex(rows []model.TemporaryMechanismIndexRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.ID, r.Mechanism, r.LifecycleRecord, r.Status}
	}
	return RenderMarkdownTable(
		[]string{"ID", "Mechanism", "Lifecycle Record", "Status"},
		data,
	)
}

func renderSunsetClosureChecklist(rows []model.SunsetClosureChecklistRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.ID, r.IntroducedFor, r.RetirementTrigger, r.RetirementVerification, r.RemovalScope}
	}
	return RenderMarkdownTable(
		[]string{"ID", "Introduced For", "Retirement Trigger", "Retirement Verification", "Removal Scope"},
		data,
	)
}

func renderDecisionLog(rows []model.DecisionLogRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.ADR, r.Decision, r.Status}
	}
	return RenderMarkdownTable(
		[]string{"ADR", "Decision", "Status"},
		data,
	)
}

func renderAcceptanceCriteriaRows(rows []model.AcceptanceCriteriaRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.AcID, r.EarsType, r.ContractType, r.RequirementSentence, r.VerificationIntent, r.VerificationCommand}
	}
	return RenderMarkdownTable(
		[]string{"AC ID", "EARS Type", "Contract Type", "Requirement Sentence", "Verification Intent", "Verification Command"},
		data,
	)
}

func renderQualityGates(rows []model.QualityGateRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.Category, r.Command}
	}
	return RenderMarkdownTable(
		[]string{"Category", "Command"},
		data,
	)
}

func renderCheckpointSummary(section model.CheckpointSummaryTemplate) string {
	return RenderBullets([]string{
		"Alignment Verdict: " + section.AlignmentVerdict,
		"Forward Fidelity: " + section.ForwardFidelity,
		"Reverse Fidelity: " + section.ReverseFidelity,
		"Non-Goal Guard: " + section.NonGoalGuard,
		"Behavioral Lock Guard: " + section.BehavioralLockGuard,
		"Temporal Completeness Guard: " + section.TemporalCompletenessGuard,
		"Quality Gate Guard: " + section.QualityGateGuard,
		"Integration Coverage Guard: " + section.IntegrationCoverageGuard,
		"Risk Classification Guard: " + section.RiskClassificationGuard,
		"TEMP Summary: " + section.TempSummary,
		"Trace Pack: `" + section.TracePack + "`",
		"Compose Pack: `" + section.ComposePack + "`",
		"Updated At: `" + section.UpdatedAt + "`",
	})
}

func renderDecisionTrace(rows []model.DecisionTraceRow) string {
	items := make([]string, len(rows))
	for i, r := range rows {
		items[i] = r.DesignAtom + " -> " + r.Target
	}
	return RenderBullets(items)
}

func renderDesignTaskTraceMatrix(rows []model.TaskTraceRow) string {
	items := make([]string, len(rows))
	for i, r := range rows {
		items[i] = r.DesignAtom + ": " + strings.Join(r.Tasks, ", ")
	}
	return RenderBullets(items)
}

func renderTaskDesignComposeMatrix(rows []model.TaskComposeRow) string {
	items := make([]string, len(rows))
	for i, r := range rows {
		items[i] = r.Task + ": " + strings.Join(r.Anchors, ", ")
	}
	return RenderBullets(items)
}

func renderTemporaryMechanismTrace(rows []model.TemporaryMechanismTraceRow) string {
	items := make([]string, len(rows))
	for i, r := range rows {
		items[i] = fmt.Sprintf(
			"%s: introduced_by=[%s], retired_by=[%s], retirement_trigger=[%s], retirement_verification=[%s], removal_scope=[%s], closure_source=%s, record_source=%s, status=%s",
			r.TempID,
			strings.Join(r.IntroducedBy, ", "),
			strings.Join(r.RetiredBy, ", "),
			r.RetirementTrigger,
			r.RetirementVerification,
			r.RemovalScope,
			r.ClosureSource,
			r.RecordSource,
			r.Status,
		)
	}
	return RenderBullets(items)
}

func renderAcOwnershipMap(rows []model.AcOwnershipMapRow) string {
	data := make([][]string, len(rows))
	for i, r := range rows {
		data[i] = []string{r.AcID, r.OwnerTask, r.Contributors, r.HasRedForAC}
	}
	return RenderMarkdownTable(
		[]string{"AC ID", "Owner Task", "Contributors", "Has RED for AC"},
		data,
	)
}

func renderBehavioralLockMap(rows []model.BehavioralLockMapRow) string {
	items := make([]string, len(rows))
	for i, r := range rows {
		anchors := make([]string, len(r.Anchors))
		for j, a := range r.Anchors {
			anchors[j] = "`" + a + "`"
		}
		items[i] = fmt.Sprintf(
			"%s (%s): intent=%q, negative_checks=[%s], positive_boundary_checks=[%s]",
			r.LockID,
			strings.Join(anchors, ", "),
			r.Intent,
			strings.Join(r.NegativeChecks, ", "),
			strings.Join(r.PositiveBoundaryChecks, ", "),
		)
	}
	return RenderBullets(items)
}

func renderForwardFidelity(s model.ForwardFidelitySection) string {
	return RenderBullets([]string{
		"Coverage ratio (`REQ+AC covered / total REQ+AC`): `" + s.RequirementsACCoverage.Covered + " / " + s.RequirementsACCoverage.Total + "`",
		"Coverage ratio (`DEC covered / total DEC`): `" + s.DecisionCoverage.Covered + " / " + s.DecisionCoverage.Total + "`",
		"Invalid DEC-to-ADR mappings: " + RenderInlineList(s.InvalidDecToADRMappings),
		"Missing design atoms: " + RenderInlineList(s.MissingDesignAtoms),
	})
}

func renderReverseFidelity(s model.ReverseFidelitySection) string {
	return RenderBullets([]string{
		"Orphan tasks (no valid anchors): " + RenderInlineList(s.OrphanTasks),
		"Tasks missing `REQxx/ACxx` in `Satisfied Requirements`: " + RenderInlineList(s.TasksMissingSatisfiedRequirements),
		"Alignment verdict: " + s.AlignmentVerdict,
		"Gaps and actions: " + RenderInlineList(s.GapsAndActions),
	})
}

func renderNonGoalGuard(s model.NonGoalGuardSection) string {
	return RenderBullets([]string{
		"Violations against `NONGOALxx`: " + RenderInlineList(s.ViolationsAgainstNonGoals),
	})
}

func renderDodSemanticsGuard(s model.DodSemanticsGuardSection) string {
	return RenderBullets([]string{
		"Tasks with OR-like DoD wording: " + RenderInlineList(s.TasksWithOrLikeDodWording),
		"DoD items missing independent verification: " + RenderInlineList(s.DodItemsMissingIndependentVerification),
	})
}

func renderBehavioralLockGuard(s model.BehavioralLockGuardSection) string {
	return RenderBullets([]string{
		"Lock atoms missing negative executable checks: " + RenderInlineList(s.LockAtomsMissingNegativeExecutableChecks),
		"Runtime-boundary lock atoms missing boundary-level verification: " + RenderInlineList(s.RuntimeBoundaryLockAtomsMissingBoundaryLevelVerification),
		"Verdict: " + s.Verdict,
	})
}

func renderTemporalCompletenessGuard(s model.TemporalCompletenessGuardSection) string {
	return RenderBullets([]string{
		"TEMP entries missing introducing tasks: " + RenderInlineList(s.TempEntriesMissingIntroducingTasks),
		"TEMP entries missing retiring tasks: " + RenderInlineList(s.TempEntriesMissingRetiringTasks),
		"Retire tasks missing negative fallback-removal verification: " + RenderInlineList(s.RetireTasksMissingNegativeFallbackRemovalVerification),
		"TEMP entries missing in-doc closure summary (checklist/ledger row): " + RenderInlineList(s.TempEntriesMissingInDocClosureSummary),
		"TEMP entries missing closure tuple fields (trigger/verification/removal_scope): " + RenderInlineList(s.TempEntriesMissingClosureTupleFields),
		"Open TEMP entries without waiver metadata (`reason`, `deadline`, `owner?`): " + RenderInlineList(s.OpenTempEntriesWithoutWaiverMetadata),
	})
}

func renderQualityGateGuard(s model.QualityGateGuardSection) string {
	return RenderBullets([]string{
		"Quality gates detected in Step 1.7: " + s.QualityGatesDetectedInStep17,
		"`## Quality Gates` present in plan.md: " + s.QualityGatesPresentInPlan,
		"Tasks missing quality gate DoD line: " + RenderInlineList(s.TasksMissingQualityGateDodLine),
	})
}

func renderComposeReconstructedDesignSummary(s model.ComposeReconstructedDesignSummarySection) string {
	return RenderBullets(s.Bullets)
}

func renderComposeScopeDiff(s model.ComposeScopeDiffSection) string {
	return RenderBullets([]string{
		"Missing from tasks: " + RenderInlineList(s.MissingFromTasks),
		"Extra in tasks: " + RenderInlineList(s.ExtraInTasks),
		"Ambiguous mappings: " + RenderInlineList(s.AmbiguousMappings),
		"Open temporary mechanisms (`TEMPxx`): " + RenderInlineList(s.OpenTemporaryMechanisms),
	})
}

func renderComposeAlignmentVerdict(s model.ComposeAlignmentVerdictSection) string {
	return RenderBullets([]string{
		s.Verdict,
		"Required fixes: " + RenderInlineList(s.RequiredFixes),
	})
}
