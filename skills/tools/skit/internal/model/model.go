package model

import (
	"fmt"
	"strings"
)

// Literal value constants used in template fragments.
const (
	PassFailTemplate                = "PASS | FAIL"
	PassFailNaTemplate              = "PASS | FAIL | N/A"
	RiskClassificationGuardTemplate = "PASS | FAIL | N/A (greenfield without Critical-domain changes)"
)

// validateNonEmpty returns an error if value is empty.
func validateNonEmpty(fieldName, value string) error {
	if value == "" {
		return fmt.Errorf("%s must be a non-empty string", fieldName)
	}
	return nil
}

// validateNonEmptyStringList checks that a list is non-empty (unless allowEmpty)
// and that every item is a non-empty string.
func validateNonEmptyStringList(fieldName string, values []string, allowEmpty bool) error {
	if len(values) == 0 && !allowEmpty {
		return fmt.Errorf("%s must contain at least one item", fieldName)
	}
	for _, v := range values {
		if v == "" {
			return fmt.Errorf("%s must contain only non-empty strings", fieldName)
		}
	}
	return nil
}

// ---- Design template row models ----

type ClarificationRow struct {
	Question          string `json:"question"`
	AnswerOrAssumption string `json:"answer_or_assumption"`
	Impact            string `json:"impact"`
	Status            string `json:"status"`
}

func (r *ClarificationRow) Validate() error {
	r.Question = strings.TrimSpace(r.Question)
	r.AnswerOrAssumption = strings.TrimSpace(r.AnswerOrAssumption)
	r.Impact = strings.TrimSpace(r.Impact)
	r.Status = strings.TrimSpace(r.Status)
	if err := validateNonEmpty("question", r.Question); err != nil {
		return err
	}
	if err := validateNonEmpty("answer_or_assumption", r.AnswerOrAssumption); err != nil {
		return err
	}
	if err := validateNonEmpty("impact", r.Impact); err != nil {
		return err
	}
	if r.Status != "resolved" && r.Status != "assumed" {
		return fmt.Errorf(`status must be "resolved" or "assumed", got %q`, r.Status)
	}
	return nil
}

type ExistingCodebaseConstraintRow struct {
	ConstraintID        string `json:"constraint_id"`
	Source              string `json:"source"`
	Constraint          string `json:"constraint"`
	ImpactOnDesign      string `json:"impact_on_design"`
	RequiredVerification string `json:"required_verification"`
}

func (r *ExistingCodebaseConstraintRow) Validate() error {
	r.ConstraintID = strings.TrimSpace(r.ConstraintID)
	r.Source = strings.TrimSpace(r.Source)
	r.Constraint = strings.TrimSpace(r.Constraint)
	r.ImpactOnDesign = strings.TrimSpace(r.ImpactOnDesign)
	r.RequiredVerification = strings.TrimSpace(r.RequiredVerification)
	for _, f := range []struct{ name, val string }{
		{"constraint_id", r.ConstraintID},
		{"source", r.Source},
		{"constraint", r.Constraint},
		{"impact_on_design", r.ImpactOnDesign},
		{"required_verification", r.RequiredVerification},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type RiskClassificationRow struct {
	Area             string `json:"area"`
	RiskTier         string `json:"risk_tier"`
	ChangeRationale  string `json:"change_rationale"`
}

func (r *RiskClassificationRow) Validate() error {
	r.Area = strings.TrimSpace(r.Area)
	r.RiskTier = strings.TrimSpace(r.RiskTier)
	r.ChangeRationale = strings.TrimSpace(r.ChangeRationale)
	if err := validateNonEmpty("area", r.Area); err != nil {
		return err
	}
	if r.RiskTier != "Critical" && r.RiskTier != "Sensitive" && r.RiskTier != "Standard" {
		return fmt.Errorf(`risk_tier must be "Critical", "Sensitive", or "Standard", got %q`, r.RiskTier)
	}
	if err := validateNonEmpty("change_rationale", r.ChangeRationale); err != nil {
		return err
	}
	return nil
}

type BoundaryInventoryRow struct {
	Boundary                   string   `json:"boundary"`
	OwnsRequirementsAC         string   `json:"owns_requirements_ac"`
	PrimaryVerificationSurface string   `json:"primary_verification_surface"`
	TempLifecycleGroup         string   `json:"temp_lifecycle_group"`
	ParallelStream             string   `json:"parallel_stream"`
	DependsOn                  []string `json:"depends_on"`
}

func (r *BoundaryInventoryRow) Validate() error {
	r.Boundary = strings.TrimSpace(r.Boundary)
	r.OwnsRequirementsAC = strings.TrimSpace(r.OwnsRequirementsAC)
	r.PrimaryVerificationSurface = strings.TrimSpace(r.PrimaryVerificationSurface)
	r.TempLifecycleGroup = strings.TrimSpace(r.TempLifecycleGroup)
	r.ParallelStream = strings.ToLower(strings.TrimSpace(r.ParallelStream))

	for _, f := range []struct{ name, val string }{
		{"boundary", r.Boundary},
		{"owns_requirements_ac", r.OwnsRequirementsAC},
		{"primary_verification_surface", r.PrimaryVerificationSurface},
		{"temp_lifecycle_group", r.TempLifecycleGroup},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	if r.ParallelStream != "yes" && r.ParallelStream != "no" {
		return fmt.Errorf("parallel_stream must be yes or no, got %q", r.ParallelStream)
	}
	return nil
}

// DependsOnDisplay returns a display string for DependsOn.
func (r *BoundaryInventoryRow) DependsOnDisplay() string {
	if len(r.DependsOn) == 0 {
		return "none"
	}
	return strings.Join(r.DependsOn, ", ")
}

type SubDocIndexRow struct {
	SubID              string `json:"sub_id"`
	File               string `json:"file"`
	OwnedBoundary      string `json:"owned_boundary"`
	OwnsRequirementsAC string `json:"owns_requirements_ac"`
}

func (r *SubDocIndexRow) Validate() error {
	r.SubID = strings.TrimSpace(r.SubID)
	r.File = strings.TrimSpace(r.File)
	r.OwnedBoundary = strings.TrimSpace(r.OwnedBoundary)
	r.OwnsRequirementsAC = strings.TrimSpace(r.OwnsRequirementsAC)
	for _, f := range []struct{ name, val string }{
		{"sub_id", r.SubID},
		{"file", r.File},
		{"owned_boundary", r.OwnedBoundary},
		{"owns_requirements_ac", r.OwnsRequirementsAC},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type RootCoverageRow struct {
	RootRequirementAC string `json:"root_requirement_ac"`
	CoveredBy         string `json:"covered_by"`
	Notes             string `json:"notes"`
}

func (r *RootCoverageRow) Validate() error {
	r.RootRequirementAC = strings.TrimSpace(r.RootRequirementAC)
	r.CoveredBy = strings.TrimSpace(r.CoveredBy)
	r.Notes = strings.TrimSpace(r.Notes)
	for _, f := range []struct{ name, val string }{
		{"root_requirement_ac", r.RootRequirementAC},
		{"covered_by", r.CoveredBy},
		{"notes", r.Notes},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type TemporaryMechanismIndexRow struct {
	ID              string `json:"id"`
	Mechanism       string `json:"mechanism"`
	LifecycleRecord string `json:"lifecycle_record"`
	Status          string `json:"status"`
}

func (r *TemporaryMechanismIndexRow) Validate() error {
	r.ID = strings.TrimSpace(r.ID)
	r.Mechanism = strings.TrimSpace(r.Mechanism)
	r.LifecycleRecord = strings.TrimSpace(r.LifecycleRecord)
	r.Status = strings.TrimSpace(r.Status)
	for _, f := range []struct{ name, val string }{
		{"id", r.ID},
		{"mechanism", r.Mechanism},
		{"lifecycle_record", r.LifecycleRecord},
		{"status", r.Status},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type SunsetClosureChecklistRow struct {
	ID                     string `json:"id"`
	IntroducedFor          string `json:"introduced_for"`
	RetirementTrigger      string `json:"retirement_trigger"`
	RetirementVerification string `json:"retirement_verification"`
	RemovalScope           string `json:"removal_scope"`
}

func (r *SunsetClosureChecklistRow) Validate() error {
	r.ID = strings.TrimSpace(r.ID)
	r.IntroducedFor = strings.TrimSpace(r.IntroducedFor)
	r.RetirementTrigger = strings.TrimSpace(r.RetirementTrigger)
	r.RetirementVerification = strings.TrimSpace(r.RetirementVerification)
	r.RemovalScope = strings.TrimSpace(r.RemovalScope)
	for _, f := range []struct{ name, val string }{
		{"id", r.ID},
		{"introduced_for", r.IntroducedFor},
		{"retirement_trigger", r.RetirementTrigger},
		{"retirement_verification", r.RetirementVerification},
		{"removal_scope", r.RemovalScope},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type DecisionLogRow struct {
	ADR      string `json:"adr"`
	Decision string `json:"decision"`
	Status   string `json:"status"`
}

func (r *DecisionLogRow) Validate() error {
	r.ADR = strings.TrimSpace(r.ADR)
	r.Decision = strings.TrimSpace(r.Decision)
	r.Status = strings.TrimSpace(r.Status)
	for _, f := range []struct{ name, val string }{
		{"adr", r.ADR},
		{"decision", r.Decision},
		{"status", r.Status},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type AcceptanceCriteriaRow struct {
	AcID                string `json:"ac_id"`
	EarsType            string `json:"ears_type"`
	ContractType        string `json:"contract_type"`
	RequirementSentence string `json:"requirement_sentence"`
	VerificationIntent  string `json:"verification_intent"`
	VerificationCommand string `json:"verification_command"`
}

func (r *AcceptanceCriteriaRow) Validate() error {
	r.AcID = strings.TrimSpace(r.AcID)
	r.EarsType = strings.TrimSpace(r.EarsType)
	r.ContractType = strings.TrimSpace(r.ContractType)
	r.RequirementSentence = strings.TrimSpace(r.RequirementSentence)
	r.VerificationIntent = strings.TrimSpace(r.VerificationIntent)
	r.VerificationCommand = strings.TrimSpace(r.VerificationCommand)
	for _, f := range []struct{ name, val string }{
		{"ac_id", r.AcID},
		{"ears_type", r.EarsType},
		{"contract_type", r.ContractType},
		{"requirement_sentence", r.RequirementSentence},
		{"verification_intent", r.VerificationIntent},
		{"verification_command", r.VerificationCommand},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type QualityGateRow struct {
	Category string `json:"category"`
	Command  string `json:"command"`
}

func (r *QualityGateRow) Validate() error {
	r.Category = strings.TrimSpace(r.Category)
	r.Command = strings.TrimSpace(r.Command)
	if err := validateNonEmpty("category", r.Category); err != nil {
		return err
	}
	if err := validateNonEmpty("command", r.Command); err != nil {
		return err
	}
	return nil
}

// ---- Plan template models ----

type CheckpointSummaryTemplate struct {
	AlignmentVerdict  string `json:"alignment_verdict"`
	ScopeContractGuard string `json:"scope_contract_guard"`
	QualityGateGuard  string `json:"quality_gate_guard"`
	ReviewArtifact    string `json:"review_artifact"`
	TracePack         string `json:"trace_pack"`
	ComposePack       string `json:"compose_pack"`
	UpdatedAt         string `json:"updated_at"`
}

func (c *CheckpointSummaryTemplate) Validate() error {
	passFail := []struct{ name, val string }{
		{"alignment_verdict", c.AlignmentVerdict},
		{"scope_contract_guard", c.ScopeContractGuard},
		{"quality_gate_guard", c.QualityGateGuard},
	}
	for _, f := range passFail {
		if f.val != PassFailTemplate {
			return fmt.Errorf("%s must be %q, got %q", f.name, PassFailTemplate, f.val)
		}
	}
	if err := validateNonEmpty("review_artifact", c.ReviewArtifact); err != nil {
		return err
	}
	if err := validateNonEmpty("trace_pack", c.TracePack); err != nil {
		return err
	}
	if err := validateNonEmpty("compose_pack", c.ComposePack); err != nil {
		return err
	}
	return validateNonEmpty("updated_at", c.UpdatedAt)
}

// ---- Trace template models ----

type DecisionTraceRow struct {
	DesignAtom string `json:"design_atom"`
	Target     string `json:"target"`
}

func (r *DecisionTraceRow) Validate() error { return nil }

type TaskTraceRow struct {
	DesignAtom string   `json:"design_atom"`
	Tasks      []string `json:"tasks"`
}

func (r *TaskTraceRow) Validate() error {
	return validateNonEmptyStringList("tasks", r.Tasks, false)
}

type TaskComposeRow struct {
	Task    string   `json:"task"`
	Anchors []string `json:"anchors"`
}

func (r *TaskComposeRow) Validate() error {
	return validateNonEmptyStringList("anchors", r.Anchors, false)
}

type TemporaryMechanismTraceRow struct {
	TempID                  string   `json:"temp_id"`
	IntroducedBy            []string `json:"introduced_by"`
	RetiredBy               []string `json:"retired_by"`
	RetirementTrigger       string   `json:"retirement_trigger"`
	RetirementVerification  string   `json:"retirement_verification"`
	RemovalScope            string   `json:"removal_scope"`
	ClosureSource           string   `json:"closure_source"`
	RecordSource            string   `json:"record_source"`
	Status                  string   `json:"status"`
}

func (r *TemporaryMechanismTraceRow) Validate() error {
	if err := validateNonEmptyStringList("introduced_by", r.IntroducedBy, false); err != nil {
		return err
	}
	return validateNonEmptyStringList("retired_by", r.RetiredBy, false)
}

type AcOwnershipMapRow struct {
	AcID       string `json:"ac_id"`
	OwnerTask  string `json:"owner_task"`
	Contributors string `json:"contributors"`
	HasRedForAC string `json:"has_red_for_ac"`
}

func (r *AcOwnershipMapRow) Validate() error {
	r.AcID = strings.TrimSpace(r.AcID)
	r.OwnerTask = strings.TrimSpace(r.OwnerTask)
	r.Contributors = strings.TrimSpace(r.Contributors)
	r.HasRedForAC = strings.TrimSpace(r.HasRedForAC)
	for _, f := range []struct{ name, val string }{
		{"ac_id", r.AcID},
		{"owner_task", r.OwnerTask},
		{"contributors", r.Contributors},
		{"has_red_for_ac", r.HasRedForAC},
	} {
		if err := validateNonEmpty(f.name, f.val); err != nil {
			return err
		}
	}
	return nil
}

type BehavioralLockMapRow struct {
	LockID                 string   `json:"lock_id"`
	Anchors                []string `json:"anchors"`
	Intent                 string   `json:"intent"`
	NegativeChecks         []string `json:"negative_checks"`
	PositiveBoundaryChecks []string `json:"positive_boundary_checks"`
}

func (r *BehavioralLockMapRow) Validate() error {
	if err := validateNonEmptyStringList("anchors", r.Anchors, false); err != nil {
		return err
	}
	if err := validateNonEmptyStringList("negative_checks", r.NegativeChecks, false); err != nil {
		return err
	}
	return validateNonEmptyStringList("positive_boundary_checks", r.PositiveBoundaryChecks, false)
}

type CoverageCounts struct {
	Covered string `json:"covered"`
	Total   string `json:"total"`
}

type ForwardFidelitySection struct {
	RequirementsACCoverage   CoverageCounts `json:"requirements_ac_coverage"`
	DecisionCoverage         CoverageCounts `json:"decision_coverage"`
	InvalidDecToADRMappings  []string       `json:"invalid_dec_to_adr_mappings"`
	MissingDesignAtoms       []string       `json:"missing_design_atoms"`
}

func (s *ForwardFidelitySection) Validate() error {
	if err := validateNonEmptyStringList("invalid_dec_to_adr_mappings", s.InvalidDecToADRMappings, false); err != nil {
		return err
	}
	return validateNonEmptyStringList("missing_design_atoms", s.MissingDesignAtoms, false)
}

type ReverseFidelitySection struct {
	OrphanTasks                       []string `json:"orphan_tasks"`
	TasksMissingSatisfiedRequirements []string `json:"tasks_missing_satisfied_requirements"`
	AlignmentVerdict                  string   `json:"alignment_verdict"`
	GapsAndActions                    []string `json:"gaps_and_actions"`
}

func (s *ReverseFidelitySection) Validate() error {
	for _, f := range []struct {
		name   string
		values []string
	}{
		{"orphan_tasks", s.OrphanTasks},
		{"tasks_missing_satisfied_requirements", s.TasksMissingSatisfiedRequirements},
		{"gaps_and_actions", s.GapsAndActions},
	} {
		if err := validateNonEmptyStringList(f.name, f.values, false); err != nil {
			return err
		}
	}
	if s.AlignmentVerdict != PassFailTemplate {
		return fmt.Errorf("alignment_verdict must be %q, got %q", PassFailTemplate, s.AlignmentVerdict)
	}
	return nil
}

type NonGoalGuardSection struct {
	ViolationsAgainstNonGoals []string `json:"violations_against_non_goals"`
}

func (s *NonGoalGuardSection) Validate() error {
	return validateNonEmptyStringList("violations_against_non_goals", s.ViolationsAgainstNonGoals, false)
}

type DodSemanticsGuardSection struct {
	TasksWithOrLikeDodWording             []string `json:"tasks_with_or_like_dod_wording"`
	DodItemsMissingIndependentVerification []string `json:"dod_items_missing_independent_verification"`
}

func (s *DodSemanticsGuardSection) Validate() error {
	for _, f := range []struct {
		name   string
		values []string
	}{
		{"tasks_with_or_like_dod_wording", s.TasksWithOrLikeDodWording},
		{"dod_items_missing_independent_verification", s.DodItemsMissingIndependentVerification},
	} {
		if err := validateNonEmptyStringList(f.name, f.values, false); err != nil {
			return err
		}
	}
	return nil
}

type BehavioralLockGuardSection struct {
	LockAtomsMissingNegativeExecutableChecks                    []string `json:"lock_atoms_missing_negative_executable_checks"`
	RuntimeBoundaryLockAtomsMissingBoundaryLevelVerification    []string `json:"runtime_boundary_lock_atoms_missing_boundary_level_verification"`
	Verdict                                                     string   `json:"verdict"`
}

func (s *BehavioralLockGuardSection) Validate() error {
	for _, f := range []struct {
		name   string
		values []string
	}{
		{"lock_atoms_missing_negative_executable_checks", s.LockAtomsMissingNegativeExecutableChecks},
		{"runtime_boundary_lock_atoms_missing_boundary_level_verification", s.RuntimeBoundaryLockAtomsMissingBoundaryLevelVerification},
	} {
		if err := validateNonEmptyStringList(f.name, f.values, false); err != nil {
			return err
		}
	}
	if s.Verdict != PassFailTemplate {
		return fmt.Errorf("verdict must be %q, got %q", PassFailTemplate, s.Verdict)
	}
	return nil
}

type TemporalCompletenessGuardSection struct {
	TempEntriesMissingIntroducingTasks                    []string `json:"temp_entries_missing_introducing_tasks"`
	TempEntriesMissingRetiringTasks                       []string `json:"temp_entries_missing_retiring_tasks"`
	RetireTasksMissingNegativeFallbackRemovalVerification []string `json:"retire_tasks_missing_negative_fallback_removal_verification"`
	TempEntriesMissingInDocClosureSummary                 []string `json:"temp_entries_missing_in_doc_closure_summary"`
	TempEntriesMissingClosureTupleFields                  []string `json:"temp_entries_missing_closure_tuple_fields"`
	OpenTempEntriesWithoutWaiverMetadata                  []string `json:"open_temp_entries_without_waiver_metadata"`
}

func (s *TemporalCompletenessGuardSection) Validate() error {
	for _, f := range []struct {
		name   string
		values []string
	}{
		{"temp_entries_missing_introducing_tasks", s.TempEntriesMissingIntroducingTasks},
		{"temp_entries_missing_retiring_tasks", s.TempEntriesMissingRetiringTasks},
		{"retire_tasks_missing_negative_fallback_removal_verification", s.RetireTasksMissingNegativeFallbackRemovalVerification},
		{"temp_entries_missing_in_doc_closure_summary", s.TempEntriesMissingInDocClosureSummary},
		{"temp_entries_missing_closure_tuple_fields", s.TempEntriesMissingClosureTupleFields},
		{"open_temp_entries_without_waiver_metadata", s.OpenTempEntriesWithoutWaiverMetadata},
	} {
		if err := validateNonEmptyStringList(f.name, f.values, false); err != nil {
			return err
		}
	}
	return nil
}

type QualityGateGuardSection struct {
	QualityGatesDetectedInStep17    string   `json:"quality_gates_detected_in_step_1_7"`
	QualityGatesPresentInPlan       string   `json:"quality_gates_present_in_plan"`
	TasksMissingQualityGateDodLine  []string `json:"tasks_missing_quality_gate_dod_line"`
}

func (s *QualityGateGuardSection) Validate() error {
	return validateNonEmptyStringList("tasks_missing_quality_gate_dod_line", s.TasksMissingQualityGateDodLine, false)
}

type ComposeReconstructedDesignSummarySection struct {
	Bullets []string `json:"bullets"`
}

func (s *ComposeReconstructedDesignSummarySection) Validate() error {
	return validateNonEmptyStringList("bullets", s.Bullets, false)
}

type ComposeScopeDiffSection struct {
	MissingFromTasks       []string `json:"missing_from_tasks"`
	ExtraInTasks           []string `json:"extra_in_tasks"`
	AmbiguousMappings      []string `json:"ambiguous_mappings"`
	OpenTemporaryMechanisms []string `json:"open_temporary_mechanisms"`
}

func (s *ComposeScopeDiffSection) Validate() error {
	for _, f := range []struct {
		name   string
		values []string
	}{
		{"missing_from_tasks", s.MissingFromTasks},
		{"extra_in_tasks", s.ExtraInTasks},
		{"ambiguous_mappings", s.AmbiguousMappings},
		{"open_temporary_mechanisms", s.OpenTemporaryMechanisms},
	} {
		if err := validateNonEmptyStringList(f.name, f.values, false); err != nil {
			return err
		}
	}
	return nil
}

type ComposeAlignmentVerdictSection struct {
	Verdict      string   `json:"verdict"`
	RequiredFixes []string `json:"required_fixes"`
}

func (s *ComposeAlignmentVerdictSection) Validate() error {
	if s.Verdict != PassFailTemplate {
		return fmt.Errorf("verdict must be %q, got %q", PassFailTemplate, s.Verdict)
	}
	return validateNonEmptyStringList("required_fixes", s.RequiredFixes, false)
}

// ---- Aggregate source models ----

type DesignTemplateSource struct {
	Clarifications              []ClarificationRow              `json:"clarifications"`
	ExistingCodebaseConstraints []ExistingCodebaseConstraintRow `json:"existing_codebase_constraints"`
	RiskClassification          []RiskClassificationRow         `json:"risk_classification"`
	BoundaryInventory           []BoundaryInventoryRow          `json:"boundary_inventory"`
	SubDocIndex                 []SubDocIndexRow                `json:"sub_doc_index"`
	RootCoverage                []RootCoverageRow               `json:"root_coverage"`
	TemporaryMechanismIndex     []TemporaryMechanismIndexRow    `json:"temporary_mechanism_index"`
	SunsetClosureChecklist      []SunsetClosureChecklistRow     `json:"sunset_closure_checklist"`
	DecisionLog                 []DecisionLogRow                `json:"decision_log"`
	AcceptanceCriteria          []AcceptanceCriteriaRow         `json:"acceptance_criteria"`
	SubLocalAcceptanceCriteria  []AcceptanceCriteriaRow         `json:"sub_local_acceptance_criteria"`
}

func (d *DesignTemplateSource) Validate() error {
	for i := range d.Clarifications {
		if err := d.Clarifications[i].Validate(); err != nil {
			return fmt.Errorf("clarifications[%d]: %w", i, err)
		}
	}
	for i := range d.ExistingCodebaseConstraints {
		if err := d.ExistingCodebaseConstraints[i].Validate(); err != nil {
			return fmt.Errorf("existing_codebase_constraints[%d]: %w", i, err)
		}
	}
	for i := range d.RiskClassification {
		if err := d.RiskClassification[i].Validate(); err != nil {
			return fmt.Errorf("risk_classification[%d]: %w", i, err)
		}
	}
	for i := range d.BoundaryInventory {
		if err := d.BoundaryInventory[i].Validate(); err != nil {
			return fmt.Errorf("boundary_inventory[%d]: %w", i, err)
		}
	}
	for i := range d.SubDocIndex {
		if err := d.SubDocIndex[i].Validate(); err != nil {
			return fmt.Errorf("sub_doc_index[%d]: %w", i, err)
		}
	}
	for i := range d.RootCoverage {
		if err := d.RootCoverage[i].Validate(); err != nil {
			return fmt.Errorf("root_coverage[%d]: %w", i, err)
		}
	}
	for i := range d.TemporaryMechanismIndex {
		if err := d.TemporaryMechanismIndex[i].Validate(); err != nil {
			return fmt.Errorf("temporary_mechanism_index[%d]: %w", i, err)
		}
	}
	for i := range d.SunsetClosureChecklist {
		if err := d.SunsetClosureChecklist[i].Validate(); err != nil {
			return fmt.Errorf("sunset_closure_checklist[%d]: %w", i, err)
		}
	}
	for i := range d.DecisionLog {
		if err := d.DecisionLog[i].Validate(); err != nil {
			return fmt.Errorf("decision_log[%d]: %w", i, err)
		}
	}
	for i := range d.AcceptanceCriteria {
		if err := d.AcceptanceCriteria[i].Validate(); err != nil {
			return fmt.Errorf("acceptance_criteria[%d]: %w", i, err)
		}
	}
	for i := range d.SubLocalAcceptanceCriteria {
		if err := d.SubLocalAcceptanceCriteria[i].Validate(); err != nil {
			return fmt.Errorf("sub_local_acceptance_criteria[%d]: %w", i, err)
		}
	}
	return nil
}

type PlanTemplateSource struct {
	QualityGates      []QualityGateRow          `json:"quality_gates"`
	CheckpointSummary CheckpointSummaryTemplate  `json:"checkpoint_summary"`
}

func (p *PlanTemplateSource) Validate() error {
	for i := range p.QualityGates {
		if err := p.QualityGates[i].Validate(); err != nil {
			return fmt.Errorf("quality_gates[%d]: %w", i, err)
		}
	}
	return p.CheckpointSummary.Validate()
}

type TraceTemplateSource struct {
	DecisionTrace                       []DecisionTraceRow                       `json:"decision_trace"`
	DesignTaskTraceMatrix               []TaskTraceRow                           `json:"design_task_trace_matrix"`
	TaskDesignComposeMatrix             []TaskComposeRow                         `json:"task_design_compose_matrix"`
	TemporaryMechanismTrace             []TemporaryMechanismTraceRow             `json:"temporary_mechanism_trace"`
	AcOwnershipMap                      []AcOwnershipMapRow                      `json:"ac_ownership_map"`
	BehavioralLockMap                   []BehavioralLockMapRow                   `json:"behavioral_lock_map"`
	ForwardFidelity                     ForwardFidelitySection                   `json:"forward_fidelity"`
	ReverseFidelity                     ReverseFidelitySection                   `json:"reverse_fidelity"`
	NonGoalGuard                        NonGoalGuardSection                      `json:"non_goal_guard"`
	DodSemanticsGuard                   DodSemanticsGuardSection                 `json:"dod_semantics_guard"`
	BehavioralLockGuard                 BehavioralLockGuardSection               `json:"behavioral_lock_guard"`
	TemporalCompletenessGuard           TemporalCompletenessGuardSection         `json:"temporal_completeness_guard"`
	QualityGateGuard                    QualityGateGuardSection                  `json:"quality_gate_guard"`
	ComposeReconstructedDesignSummary   ComposeReconstructedDesignSummarySection `json:"compose_reconstructed_design_summary"`
	ComposeScopeDiff                    ComposeScopeDiffSection                  `json:"compose_scope_diff"`
	ComposeAlignmentVerdict             ComposeAlignmentVerdictSection           `json:"compose_alignment_verdict"`
}

func (t *TraceTemplateSource) Validate() error {
	// Required non-empty bullet sections.
	requiredLists := []struct {
		name string
		n    int
	}{
		{"decision_trace", len(t.DecisionTrace)},
		{"design_task_trace_matrix", len(t.DesignTaskTraceMatrix)},
		{"task_design_compose_matrix", len(t.TaskDesignComposeMatrix)},
		{"temporary_mechanism_trace", len(t.TemporaryMechanismTrace)},
		{"behavioral_lock_map", len(t.BehavioralLockMap)},
	}
	for _, l := range requiredLists {
		if l.n == 0 {
			return fmt.Errorf("%s must contain at least one item", l.name)
		}
	}

	for i := range t.DecisionTrace {
		if err := t.DecisionTrace[i].Validate(); err != nil {
			return fmt.Errorf("decision_trace[%d]: %w", i, err)
		}
	}
	for i := range t.DesignTaskTraceMatrix {
		if err := t.DesignTaskTraceMatrix[i].Validate(); err != nil {
			return fmt.Errorf("design_task_trace_matrix[%d]: %w", i, err)
		}
	}
	for i := range t.TaskDesignComposeMatrix {
		if err := t.TaskDesignComposeMatrix[i].Validate(); err != nil {
			return fmt.Errorf("task_design_compose_matrix[%d]: %w", i, err)
		}
	}
	for i := range t.TemporaryMechanismTrace {
		if err := t.TemporaryMechanismTrace[i].Validate(); err != nil {
			return fmt.Errorf("temporary_mechanism_trace[%d]: %w", i, err)
		}
	}
	for i := range t.AcOwnershipMap {
		if err := t.AcOwnershipMap[i].Validate(); err != nil {
			return fmt.Errorf("ac_ownership_map[%d]: %w", i, err)
		}
	}
	for i := range t.BehavioralLockMap {
		if err := t.BehavioralLockMap[i].Validate(); err != nil {
			return fmt.Errorf("behavioral_lock_map[%d]: %w", i, err)
		}
	}
	if err := t.ForwardFidelity.Validate(); err != nil {
		return fmt.Errorf("forward_fidelity: %w", err)
	}
	if err := t.ReverseFidelity.Validate(); err != nil {
		return fmt.Errorf("reverse_fidelity: %w", err)
	}
	if err := t.NonGoalGuard.Validate(); err != nil {
		return fmt.Errorf("non_goal_guard: %w", err)
	}
	if err := t.DodSemanticsGuard.Validate(); err != nil {
		return fmt.Errorf("dod_semantics_guard: %w", err)
	}
	if err := t.BehavioralLockGuard.Validate(); err != nil {
		return fmt.Errorf("behavioral_lock_guard: %w", err)
	}
	if err := t.TemporalCompletenessGuard.Validate(); err != nil {
		return fmt.Errorf("temporal_completeness_guard: %w", err)
	}
	if err := t.QualityGateGuard.Validate(); err != nil {
		return fmt.Errorf("quality_gate_guard: %w", err)
	}
	if err := t.ComposeReconstructedDesignSummary.Validate(); err != nil {
		return fmt.Errorf("compose_reconstructed_design_summary: %w", err)
	}
	if err := t.ComposeScopeDiff.Validate(); err != nil {
		return fmt.Errorf("compose_scope_diff: %w", err)
	}
	if err := t.ComposeAlignmentVerdict.Validate(); err != nil {
		return fmt.Errorf("compose_alignment_verdict: %w", err)
	}
	return nil
}
