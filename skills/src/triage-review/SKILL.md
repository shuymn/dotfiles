---
name: triage-review
description: "Processes AI reviewer feedback and applies only verified fixes. Works in two modes: (1) fetches comments from a PR URL or current branch, (2) processes feedback pasted directly into the conversation. Trigger when the user wants to bulk-process or apply AI review suggestions — from a GitHub PR or pasted text. Do NOT trigger for single questions about what a bot said, or general code review discussion."
allowed-tools: [Bash, Read, Grep, Glob, WebSearch]
---

# Apply Verified Fixes from AI Review Comments

## Not in Scope

- Comments from human reviewers — this skill processes AI-generated suggestions only.
- Evaluating overall PR quality or proposing improvements beyond what AI reviewers raised.

## Input Mode Detection

Before fetching anything, determine where the feedback is coming from:

- **Direct input**: The user has pasted review comments or a list of suggestions into the conversation. Use these directly — skip all `gh api` calls. The text may or may not name a specific bot; focus on extracting actionable technical suggestions. If suggestions reference specific files or line numbers, confirm those paths exist locally before applying fixes.
- **PR reference**: A PR URL or number was given → proceed to Setup below.
- **Current branch**: No argument and no pasted content → infer PR from current branch via Setup below.

## Setup: Resolve PR Target

Arguments may be a PR URL, PR number, or empty (use current branch's PR).

- If a URL like `https://github.com/owner/repo/pull/123` was given, resolve `<owner>`, `<repo>`, and `<pr_num>` from the URL.
- If a number was given, resolve `<owner>` and `<repo>` from `gh repo view`, then use the provided PR number as `<pr_num>`.
- If no argument was given, resolve `<owner>` and `<repo>` from `gh repo view`, then resolve `<pr_num>` from `gh pr view`.

Gather PR info using `gh api` (works for any repo, not just the current one). Substitute concrete values directly into each command:

```bash
# PR metadata
gh api repos/<owner>/<repo>/pulls/<pr_num> --jq '{title,state,body}'

# Changed files
gh api repos/<owner>/<repo>/pulls/<pr_num>/files --jq '.[].filename'

# General PR comments (issue-level)
gh api repos/<owner>/<repo>/issues/<pr_num>/comments \
  --jq '.[] | "[\(.user.login)] \(.body)"'

# Review-level comments (overall approval/request changes)
gh api repos/<owner>/<repo>/pulls/<pr_num>/reviews \
  --jq '.[] | "[\(.user.login)] \(.state): \(.body)"'

# Inline review thread comments (line-specific suggestions — most common for bots)
gh api repos/<owner>/<repo>/pulls/<pr_num>/comments \
  --jq '.[] | "[\(.user.login)] \(.path):\(.line // .original_line): \(.body)"'
```

## Your task

### 0. Early exit check

If no comments exist from any AI reviewer, report "No AI reviewer comments found" and stop.

### 1. Identify AI Reviewers

Look for comments from:
`Copilot`, `copilot[bot]`, `copilot-pull-request-reviewer[bot]`, `github-copilot`,
`gemini-code-assist[bot]`, `google-code-assist`, `google-code-assist[bot]`,
`chatgpt-codex-connector[bot]`, `devin-ai-integration[bot]`

Extract all suggestions from these reviewers. If multiple bots commented, process each bot's suggestions as a group.

### 2. Verify Each AI Suggestion

For each AI comment, perform fact-checking. Choose the lightest verification path that can prove or disprove the suggestion:

a) **Extract Technical Claims**
   - API usage recommendations
   - Security vulnerability claims
   - Performance optimization suggestions
   - Best practice recommendations

b) **Choose Verification Path**

   - **Local verification**: Use repo-local evidence when the suggestion is about current implementation behavior, file paths, symbol existence, config shape, dependency usage, test expectations, or contract mismatches that can be confirmed from the checked-out codebase.
   - **Web verification**: Use available Web Search tool(s) when the suggestion depends on external facts such as official API behavior, version compatibility, CVEs, benchmark claims, or ecosystem best practices.
   - **Hybrid verification**: Use both local and web evidence when the suggestion spans repo behavior and external facts, such as framework misuse in this codebase, outdated API usage, or a security claim tied to a library version in the repo.

c) **Run Verification**

   - **Local verification process**:
     - Read the referenced files and nearby code paths before changing anything
     - Confirm symbol existence, imports, configuration keys, and call sites
     - Check dependency and version declarations when relevant
     - Use existing tests, reproducible commands, or contract/diff evidence when available
     - Treat direct local contradiction as evidence against the suggestion

   - **Web verification process**:
     Use available Web Search tool(s) with the SAME query to cross-verify:

   - **Search Strategy**:
     1. Send identical queries to all available web search tools
     2. Compare results across tools and sources
     3. Look for consensus or discrepancies
     4. Prioritize information that appears in multiple reliable sources

   - **Verification Process**:
     - API/Method validation: Search "[language] [method_name] documentation"
     - Security claims: Search "[vulnerability] CVE [year]"
     - Performance claims: Search "[technique] benchmark comparison"
     - Best practices: Search "[technology] official best practices"

   - **Decision Criteria**:
     - ✅ Apply if: local evidence confirms the issue, web evidence confirms the claim, or hybrid evidence shows the suggestion is materially correct for this repo. Directionally correct suggestions may still qualify with a note.
     - ⚠️ Review carefully if: results differ between local and external evidence, sources disagree, or the claim is a context-dependent style or best-practice recommendation with reasonable support.
     - ❌ Skip only if: the suggestion is contradicted by strong local evidence, disproven by reliable external evidence, or is a factually incorrect technical statement. Lack of web evidence alone is not enough to reject a repo-local claim.

### 3. Categorize Verified Suggestions

**✅ Verified & Apply**:
- Confirmed by repo-local evidence
- Confirmed security vulnerabilities
- Documented API misuse
- Proven performance issues
- Official best practices (including suggestions that are directionally correct even if a newer alternative exists — add a note rather than downgrading the verdict)

**⚠️ Partially Verified**:
- Repo evidence is incomplete or points to a context-dependent fix
- Mixed opinions in community
- Context-dependent improvements
- Style preferences with reasonable backing (major style guides, popular linting configs)
- Suggestions that are valid but not the newest best-in-class option

**❌ Incorrect/Unverified**:
- Repo-local evidence directly contradicts the claim
- APIs or methods that genuinely no longer exist in the target version
- False CVE/security claims that cannot be verified
- Factually incorrect technical statements (e.g., "this function was removed" when it wasn't)
- Do NOT use ❌ for contested style preferences or best practices that have legitimate community backing

### 4. Apply Only Verified Fixes

For each verified suggestion, document before applying:
```
File: [filename]
Line: [line number or range]
Issue: [Brief description]
Verification: [What local evidence and/or external evidence confirmed]
Fix: [Exact change to apply]
Source: [file path, test/command output, and/or documentation/CVE/Benchmark URL]
```

### 5. Implementation Process

- Read the current file content before editing
- Apply verified changes ONE topic at a time
- After each change: save the file, confirm the edit looks correct
- Do not batch multiple unrelated fixes into one edit

### 6. Final Report (use the user's language)

```markdown
## AI Review Verification Report

### Verified & Applied
1. **[File]**: [What was fixed]
   - Evidence: [Local evidence and/or verification source/URL]
   - Change: [Brief description]

### Partially Verified
1. **[File]**: [What was conditionally fixed]
   - Findings: [Local evidence and/or mixed external findings]
   - Rationale: [Why applied or not]

### Incorrect / Not Applied
1. **[Suggestion]**: [Why it was incorrect]
   - Findings: [What local evidence and/or search revealed]

### Summary
- Total AI suggestions: X
- Verified fixes applied: Y
- Incorrect suggestions: Z
```

## Important Notes
- Prefer the strongest available evidence for the claim: direct repo-local reproduction or contradiction beats speculation, and official external documentation beats secondary summaries.
- Prioritize official documentation over blog posts; check publication dates to avoid outdated advice
- If a claim cannot be verified but is also not contradicted by strong local or external evidence, mark as ⚠️ rather than ❌ — absence of web evidence is not enough to reject a repo-local claim.
- **Use AskUserQuestionTool** when you need clarification on:
  - Whether to apply a partially verified suggestion
  - How to prioritize conflicting recommendations
  - Whether a security-related change should be applied
  - If AskUserQuestionTool is unavailable and multiple independent clarifications are needed, ask in a single message using QID labels (`Q1`, `Q2`, ...); require `QID: <answer>` responses and allow `QID: OTHER(<concise detail>)` when no option fits
