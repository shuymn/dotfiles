---
name: audit-agents-md
description: Audits and refines a CLAUDE.md or AGENTS.md file for instruction density, staleness, and effectiveness. Use when reviewing or improving an agent instruction file, after significant project changes (skills, architecture, or tooling), when agent behavior suggests instructions are ignored or misinterpreted, when the file feels bloated or repetitive, or when the user says "review my AGENTS.md" or "audit agent instructions".
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

<!-- do not edit: generated from skills/src/audit-agents-md/SKILL.md; edit source and rebuild -->


# Audit Agent Instruction Files

Audit a CLAUDE.md or AGENTS.md file against established best practices for agent instruction files, then propose concrete improvements.

## Background

Agent instruction files go by different names depending on the tool:

- **AGENTS.md** — tool-agnostic convention
- **CLAUDE.md** — Claude Code specific
- **COPILOT.md**, **CURSOR.md**, etc. — other tool-specific variants

The editable source of truth may be a plain file, a symlink target, or a managed source that is copied into tool-specific locations. Do not assume the canonical file by name alone; resolve it from the actual environment before proposing edits.

## Arguments

- Default (no args): auto-discovers likely instruction files in the current project root, then resolves sibling variants, symlinks, and obvious managed-copy relationships before deciding which file is editable.
- Path argument: audits the specified file (e.g., `/audit-agents-md ~/.codex/AGENTS.md`) and resolves whether it is the source of truth, a symlink, or a generated copy.

## Source Resolution

Before auditing, resolve how the file is managed:

1. Check whether the target is a symlink (`readlink` / `ls -la`)
2. Check for obvious managed-copy relationships (sync scripts, copy targets, "do not edit" notes, build/install tooling)
3. Identify the editable source of truth; if none is found, treat the target as the editable canonical file
4. Audit may inspect copies, but proposals and edits must target the editable source of truth
5. Report the relationship to the user (e.g., "`~/.codex/AGENTS.md` is a generated copy of `~/.dotfiles/etc/claude/CLAUDE.md`; audit may inspect the copy, edits must target the source")

## Audit Criteria

Evaluate the file against each criterion below. For each, assign a verdict: **PASS**, **WARN**, or **FAIL**.

### Evidence-Based Guardrails

Use this evidence to prioritize recommendations:

- LLM-generated context files reduced success rate on average while increasing cost by ~20-23%.
- Agents strongly follow tool mentions in context files; naming a tool can materially increase tool usage.
- Codebase overview sections are often redundant and did not consistently reduce time-to-relevant-files.
- Critical rules are easier to recover when they are front-loaded or briefly restated at the end than when they are buried mid-file.

Therefore, prefer **minimal, repository-specific requirements** over broad guidance.

### 1. Density (heuristic, not a hard threshold)

Count lines that contain actual instructions (exclude blank lines, comments, headers). Every line competes for the agent's limited instruction-following budget.

- **PASS**: The file is compact and mostly limited to non-inferable, high-value requirements.
- **WARN**: The file has noticeable bloat, repetition, or low-value instructions that should probably be trimmed.
- **FAIL**: The file is overloaded enough that retrieval, compliance, or execution cost is likely being harmed.

### 2. Inferability

Flag any instruction that the agent can infer from the codebase itself:

- Directory structure descriptions (agent can run `rtk ls` / `rtk find`)
- Full codebase overviews that mostly restate discoverable paths/files
- Code style rules already enforced by linters (eslint, prettier, rustfmt, etc.)
- Dependency lists (agent can read package.json, Cargo.toml, etc.)
- Build/test commands that are standard for the framework (e.g., `npm test` for a Node project with no custom config)

Each flagged line is a candidate for removal.

### 3. Staleness

Check for instructions that reference:

- Files, directories, or commands that no longer exist
- Tools, libraries, or frameworks not present in the project
- Workflows that contradict current project structure
- Skills referenced in the file that are not installed

Verify by actually checking the filesystem — do not guess.

### 4. Actionability

Every instruction must be something the agent can act on. Flag:

- Vague guidance ("be careful with...", "keep in mind...")
- Aspirational statements ("we strive to...", "ideally...")
- Context without directive ("this project uses X" without "therefore do Y")
- Blanket "always do X" directives (full test suite, full lint/format, broad exploration) unless explicitly required by repo policy

### 5. Redundancy

Flag instructions that duplicate:

- What is already in a skill's SKILL.md
- What is already in another instruction file in the hierarchy (global vs project)
- What is stated multiple times in different words within the same file
- What is already captured in README/docs/CI scripts without adding repository-specific constraints

### 6. Requirement Cost Pressure

Context-file instructions should avoid adding unnecessary execution burden.

Flag lines that force extra work without clear repository-specific benefit:

- Generic mandatory tool directives (e.g., "always use uv/pytest/ruff") with no project-specific reason
- Long mandatory checklists that add broad exploration/testing unrelated to task scope
- Multiple overlapping directives that likely increase steps/tokens without improving correctness

Verdict guideline:

- **PASS**: All mandatory/tool-specific directives are repository-specific and justified
- **WARN**: 1-3 low-value mandatory directives remain
- **FAIL**: 4+ low-value mandatory directives or checklist-heavy file behavior

### 7. Structure

Check for:

- Section protection comments (`<!-- Do not restructure or delete sections -->`)
- Maintenance notes (when to update this file)
- Clear section boundaries
- Critical rules placed near the top; if restated, keep the final recap to 3 lines or fewer
- Symlink consistency (if CLAUDE.md exists alongside AGENTS.md, is it a symlink or a separate file with divergent content?)

## Process

### Step 1: Read and Analyze

1. Resolve the source-of-truth relationship for the target file
2. Read the target file and the editable source if it is different
3. If the file is in a project, also read:
   - Available skills by inspecting the skills directories or manifests that actually exist in the current environment; do not assume `.claude-plugin` or `rtk ls`
   - Project structure (top-level files and directories)
   - README/docs and CI workflows to detect documentation and command redundancy
   - Linter configs (`.eslintrc*`, `.prettierrc*`, `rustfmt.toml`, etc.)
   - Relevant global instruction files that actually exist in the current environment (for example `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, or an identified managed source) to check for redundancy across levels
   - Other instruction files in the same directory or managed set (check for divergent copies vs intentional generated copies)
4. Count instruction lines (exclude blanks, comments, section headers)
5. Determine whether the user asked for audit-only findings or for rewrite/apply work

### Step 2: Score Each Criterion

For each of the 7 criteria, provide:

- **Verdict**: PASS / WARN / FAIL
- **Evidence**: Specific lines or findings
- **Recommendation**: What to change (if not PASS)

If the request is audit-only, independent review, or findings-only: report the findings and stop here. Do not draft a rewrite or apply edits unless the user asks for changes.

### Step 3: Propose Rewrite

Only do this step when the user asked for changes or explicitly approved a rewrite. WARN/FAIL means a rewrite may be proposed; it does not mean a rewrite must be produced.

If any criterion is WARN or FAIL and changes were requested:

1. Draft a revised version of the file
   - Keep only minimal requirements that are non-inferable and repository-specific
   - Remove generic tool mandates unless backed by repository constraints
   - Replace broad codebase overviews with only non-obvious navigation hints
   - Move non-negotiable rules to the top; if needed, add a short final recap instead of repeating them throughout the file
   - If the audited file is a generated copy, draft changes against the editable source of truth instead
2. Show a diff summary: what was removed, what was added, what was reworded, and which file is the correct edit target
3. Present the rewrite options to the user:
   - If AskUserQuestionTool is available, present options for:
     - Apply the full rewrite
     - Apply selectively (user picks which changes)
     - Keep current version
   - If AskUserQuestionTool is unavailable, ask in a single message using QID labels and require one of:
     - `Q1: APPLY_FULL`
     - `Q1: APPLY_SELECTIVE(<concise selection>)`
     - `Q1: KEEP_CURRENT`

If all criteria PASS: report the audit results and confirm no changes needed.

### Step 4: Apply Changes

Only do this step after explicit user approval to change the file.

If the user approves changes:

1. Apply the approved edits to the editable source of truth, not to a generated copy or symlink path
2. If managed copies exist, rebuild or resync them using the project's normal mechanism instead of hand-editing the copies
3. Verify the updated file still meets all criteria (re-run the count)
4. Report the final line count, any remaining warnings, and which copies were refreshed

## Anti-Patterns to Watch For

Do NOT introduce these when rewriting:

- **Catch-all sections** like "Important Context" or "General Notes" — these become dumping grounds
- **Instructing the agent on how to think** — focus on what to do, not how to reason
- **Over-compression** that loses meaning — each line must still be independently clear
- **Moving essential instructions to comments** — HTML comments are for maintenance notes, not instructions
- **Editing the wrong layer** — changing a generated copy when the real edit target is a managed source file
- **Unmanaged divergent copies** — multiple instruction files drifting without a clear source-of-truth relationship
- **Tool-list cargo culting** — listing many tools/commands as mandatory without repository-specific necessity
- **Directory tree dumps** — long path enumerations that are easily discoverable by the agent
- **Buried non-negotiables** — placing the most important rules only in the middle of a long file
- **Repetition sprawl** — repeating the same critical rule in many places instead of one short final recap
