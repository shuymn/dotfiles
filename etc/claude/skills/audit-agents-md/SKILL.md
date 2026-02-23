---
name: audit-agents-md
description: Audits and refines a CLAUDE.md or AGENTS.md file for instruction density, staleness, and effectiveness. Use when reviewing or improving an agent instruction file against best practices.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Audit Agent Instruction Files

Audit a CLAUDE.md or AGENTS.md file against established best practices for agent instruction files, then propose concrete improvements.

## Background

Agent instruction files go by different names depending on the tool:

- **AGENTS.md** — tool-agnostic convention, the canonical source of truth
- **CLAUDE.md** — Claude Code specific (often a symlink to AGENTS.md)
- **COPILOT.md**, **CURSOR.md**, etc. — other tool-specific variants

A common setup is `AGENTS.md` as the real file with `CLAUDE.md` symlinked to it. This skill handles all of these transparently.

## When to Use

- Periodic review of instruction file quality
- After significant project changes (new skills, architecture shifts, tool changes)
- When agent behavior suggests instructions are being ignored or misinterpreted
- When the file has grown beyond ~30 lines of instructions

## Arguments

- Default (no args): auto-discovers the instruction file in the current project root. Checks for `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md` in that order. Follows symlinks to find the canonical file.
- Path argument: audits the specified file (e.g., `/audit-agents-md ~/.claude/CLAUDE.md`)

## Symlink Awareness

Before auditing, resolve the file's symlink chain:

1. Check if the target is a symlink (`readlink` / `ls -la`)
2. If it is, identify the canonical (real) file
3. Audit and edit the **canonical file**, not the symlink
4. Report the symlink relationship to the user (e.g., "CLAUDE.md → AGENTS.md; editing AGENTS.md")

## Audit Criteria

Evaluate the file against each criterion below. For each, assign a verdict: **PASS**, **WARN**, or **FAIL**.

### 1. Density (target: 20-30 instruction lines)

Count lines that contain actual instructions (exclude blank lines, comments, headers). Every line competes for the agent's limited instruction-following budget.

- **PASS**: ≤30 instruction lines
- **WARN**: 31-50 instruction lines
- **FAIL**: >50 instruction lines

### 2. Inferability

Flag any instruction that the agent can infer from the codebase itself:

- Directory structure descriptions (agent can run `ls` / `find`)
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

### 5. Redundancy

Flag instructions that duplicate:

- What is already in a skill's SKILL.md
- What is already in another instruction file in the hierarchy (global vs project)
- What is stated multiple times in different words within the same file

### 6. Structure

Check for:

- Section protection comments (`<!-- Do not restructure or delete sections -->`)
- Maintenance notes (when to update this file)
- Clear section boundaries
- Symlink consistency (if CLAUDE.md exists alongside AGENTS.md, is it a symlink or a separate file with divergent content?)

## Process

### Step 1: Read and Analyze

1. Resolve symlinks and identify the canonical file to edit
2. Read the target file
3. If the file is in a project, also read:
   - Available skills (`ls` the skills directory if a `.claude-plugin` exists)
   - Project structure (top-level files and directories)
   - Linter configs (`.eslintrc*`, `.prettierrc*`, `rustfmt.toml`, etc.)
   - Global instruction file (`~/.claude/CLAUDE.md` or `~/.claude/AGENTS.md`) to check for redundancy across levels
   - Other agent instruction files in the same directory (check for divergent copies vs proper symlinks)
4. Count instruction lines (exclude blanks, comments, section headers)

### Step 2: Score Each Criterion

For each of the 6 criteria, provide:

- **Verdict**: PASS / WARN / FAIL
- **Evidence**: Specific lines or findings
- **Recommendation**: What to change (if not PASS)

### Step 3: Propose Rewrite

If any criterion is WARN or FAIL:

1. Draft a revised version of the file
2. Show a diff summary: what was removed, what was added, what was reworded
3. Present to the user via AskUserQuestionTool with options:
   - Apply the full rewrite
   - Apply selectively (user picks which changes)
   - Keep current version

If all criteria PASS: report the audit results and confirm no changes needed.

### Step 4: Apply Changes

If the user approves changes:

1. Apply the approved edits to the **canonical file** (not the symlink)
2. Verify the updated file still meets all criteria (re-run the count)
3. Report the final line count and any remaining warnings

## Anti-Patterns to Watch For

Do NOT introduce these when rewriting:

- **Catch-all sections** like "Important Context" or "General Notes" — these become dumping grounds
- **Instructing the agent on how to think** — focus on what to do, not how to reason
- **Over-compression** that loses meaning — each line must still be independently clear
- **Moving essential instructions to comments** — HTML comments are for maintenance notes, not instructions
- **Divergent copies** — if both AGENTS.md and CLAUDE.md exist as separate files with different content, flag this and recommend consolidating to one canonical file with symlinks
