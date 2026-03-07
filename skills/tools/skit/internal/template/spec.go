package template

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	gotemplate "text/template"

	"skit/internal/model"
)

// TemplateRenderError is returned when a structured template cannot be rendered.
type TemplateRenderError struct {
	msg string
}

func (e *TemplateRenderError) Error() string { return e.msg }

func renderError(format string, args ...any) *TemplateRenderError {
	return &TemplateRenderError{msg: fmt.Sprintf(format, args...)}
}

// templateSpec holds the rendering logic for a single template file.
type templateSpec struct {
	// render produces the map[string]string of rendered fragments from the
	// decoded+validated model loaded from .fragments.json.
	render func(fragmentsPath string) (map[string]string, error)
}

var templateSpecs = map[string]templateSpec{
	"design-templates.md.tmpl": {
		render: renderDesignTemplateFragments,
	},
	"plan-templates.md.tmpl": {
		render: renderPlanTemplateFragments,
	},
	"trace-templates.md.tmpl": {
		render: renderTraceTemplateFragments,
	},
}

func renderDesignTemplateFragments(fragmentsPath string) (map[string]string, error) {
	data, err := os.ReadFile(fragmentsPath)
	if err != nil {
		return nil, renderError("missing fragments file: %s", fragmentsPath)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var m model.DesignTemplateSource
	if err := dec.Decode(&m); err != nil {
		return nil, renderError("invalid JSON in %s: %v", fragmentsPath, err)
	}
	if err := m.Validate(); err != nil {
		return nil, renderError("invalid fragments for design-templates.md.tmpl: %v", err)
	}
	return map[string]string{
		"clarifications":               renderClarifications(m.Clarifications),
		"existing_codebase_constraints": renderExistingCodebaseConstraints(m.ExistingCodebaseConstraints),
		"risk_classification":          renderRiskClassification(m.RiskClassification),
		"boundary_inventory":           renderBoundaryInventory(m.BoundaryInventory),
		"sub_doc_index":                renderSubDocIndex(m.SubDocIndex),
		"root_coverage":                renderRootCoverage(m.RootCoverage),
		"temporary_mechanism_index":    renderTemporaryMechanismIndex(m.TemporaryMechanismIndex),
		"sunset_closure_checklist":     renderSunsetClosureChecklist(m.SunsetClosureChecklist),
		"decision_log":                 renderDecisionLog(m.DecisionLog),
		"acceptance_criteria":          renderAcceptanceCriteriaRows(m.AcceptanceCriteria),
		"sub_local_acceptance_criteria": renderAcceptanceCriteriaRows(m.SubLocalAcceptanceCriteria),
	}, nil
}

func renderPlanTemplateFragments(fragmentsPath string) (map[string]string, error) {
	data, err := os.ReadFile(fragmentsPath)
	if err != nil {
		return nil, renderError("missing fragments file: %s", fragmentsPath)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var m model.PlanTemplateSource
	if err := dec.Decode(&m); err != nil {
		return nil, renderError("invalid JSON in %s: %v", fragmentsPath, err)
	}
	if err := m.Validate(); err != nil {
		return nil, renderError("invalid fragments for plan-templates.md.tmpl: %v", err)
	}
	return map[string]string{
		"quality_gates":      renderQualityGates(m.QualityGates),
		"checkpoint_summary": renderCheckpointSummary(m.CheckpointSummary),
	}, nil
}

func renderTraceTemplateFragments(fragmentsPath string) (map[string]string, error) {
	data, err := os.ReadFile(fragmentsPath)
	if err != nil {
		return nil, renderError("missing fragments file: %s", fragmentsPath)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var m model.TraceTemplateSource
	if err := dec.Decode(&m); err != nil {
		return nil, renderError("invalid JSON in %s: %v", fragmentsPath, err)
	}
	if err := m.Validate(); err != nil {
		return nil, renderError("invalid fragments for trace-templates.md.tmpl: %v", err)
	}
	return map[string]string{
		"decision_trace":                      renderDecisionTrace(m.DecisionTrace),
		"design_task_trace_matrix":            renderDesignTaskTraceMatrix(m.DesignTaskTraceMatrix),
		"task_design_compose_matrix":          renderTaskDesignComposeMatrix(m.TaskDesignComposeMatrix),
		"temporary_mechanism_trace":           renderTemporaryMechanismTrace(m.TemporaryMechanismTrace),
		"ac_ownership_map":                    renderAcOwnershipMap(m.AcOwnershipMap),
		"behavioral_lock_map":                 renderBehavioralLockMap(m.BehavioralLockMap),
		"forward_fidelity":                    renderForwardFidelity(m.ForwardFidelity),
		"reverse_fidelity":                    renderReverseFidelity(m.ReverseFidelity),
		"non_goal_guard":                      renderNonGoalGuard(m.NonGoalGuard),
		"dod_semantics_guard":                 renderDodSemanticsGuard(m.DodSemanticsGuard),
		"behavioral_lock_guard":               renderBehavioralLockGuard(m.BehavioralLockGuard),
		"temporal_completeness_guard":         renderTemporalCompletenessGuard(m.TemporalCompletenessGuard),
		"quality_gate_guard":                  renderQualityGateGuard(m.QualityGateGuard),
		"compose_reconstructed_design_summary": renderComposeReconstructedDesignSummary(m.ComposeReconstructedDesignSummary),
		"compose_scope_diff":                  renderComposeScopeDiff(m.ComposeScopeDiff),
		"compose_alignment_verdict":           renderComposeAlignmentVerdict(m.ComposeAlignmentVerdict),
	}, nil
}

// FragmentsPathForTemplate returns the .fragments.json path for a .md.tmpl template.
func FragmentsPathForTemplate(templatePath string) (string, error) {
	name := filepath.Base(templatePath)
	if !strings.HasSuffix(name, ".md.tmpl") {
		return "", renderError("expected .md.tmpl template: %s", templatePath)
	}
	stem := strings.TrimSuffix(name, ".md.tmpl")
	return filepath.Join(filepath.Dir(templatePath), stem+".fragments.json"), nil
}

// LoadFragments reads and validates the .fragments.json for templatePath,
// returning a map[string]string of rendered section slugs.
func LoadFragments(templatePath string) (map[string]string, error) {
	name := filepath.Base(templatePath)
	spec, ok := templateSpecs[name]
	if !ok {
		return nil, renderError("unsupported template: %s", name)
	}
	fragmentsPath, err := FragmentsPathForTemplate(templatePath)
	if err != nil {
		return nil, err
	}
	return spec.render(fragmentsPath)
}

// RenderStructuredTemplate renders a .md.tmpl file using its .fragments.json.
// The output always ends with a newline.
func RenderStructuredTemplate(templatePath string) (string, error) {
	name := filepath.Base(templatePath)
	if _, ok := templateSpecs[name]; !ok {
		return "", renderError("unsupported template: %s", name)
	}

	renderedFragments, err := LoadFragments(templatePath)
	if err != nil {
		return "", err
	}

	content, err := os.ReadFile(templatePath)
	if err != nil {
		return "", renderError("cannot read template %s: %v", templatePath, err)
	}

	tmpl, err := gotemplate.New(name).Parse(string(content))
	if err != nil {
		return "", renderError("cannot parse template %s: %v", templatePath, err)
	}

	var buf strings.Builder
	if err := tmpl.Execute(&buf, renderedFragments); err != nil {
		return "", renderError("cannot render template %s: %v", templatePath, err)
	}

	result := buf.String()
	if !strings.HasSuffix(result, "\n") {
		result += "\n"
	}
	return result, nil
}
