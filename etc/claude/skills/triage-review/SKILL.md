---
name: triage-review
description: "Processes AI reviewer feedback and applies only verified fixes. Works in two modes: (1) fetches comments from a PR URL or current branch, (2) processes feedback pasted directly into the conversation. Trigger when the user wants to bulk-process or apply AI review suggestions — from a GitHub PR or pasted text. Do NOT trigger for single questions about what a bot said, or general code review discussion."
allowed-tools: [Bash, Read, Grep, Glob, WebSearch]
---

# Apply Verified Fixes from AI Review Comments

## Not in Scope

- Comments from human reviewers — this skill processes AI-generated suggestions only.
- Evaluating overall PR quality or proposing improvements beyond what AI reviewers raised.
- Applying suggestions that cannot be verified through web search.

## Input Mode Detection

Before fetching anything, determine where the feedback is coming from:

- **Direct input**: The user has pasted review comments or a list of suggestions into the conversation. Use these directly — skip all `gh api` calls. The text may or may not name a specific bot; focus on extracting actionable technical suggestions. If suggestions reference specific files or line numbers, confirm those paths exist locally before applying fixes.
- **PR reference**: A PR URL or number was given → proceed to Setup below.
- **Current branch**: No argument and no pasted content → infer PR from current branch via Setup below.

## Setup: Resolve PR Target

Arguments may be a PR URL, PR number, or empty (use current branch's PR).

```bash
# If a URL like https://github.com/owner/repo/pull/123 was given:
OWNER=<parsed>; REPO=<parsed>; PR_NUM=<parsed>

# If a number was given:
OWNER=$(gh repo view --json owner -q .owner.login); REPO=$(gh repo view --json name -q .name); PR_NUM=<given>

# If no argument:
OWNER=$(gh repo view --json owner -q .owner.login)
REPO=$(gh repo view --json name -q .name)
PR_NUM=$(gh pr view --json number -q .number 2>/dev/null)
```

Gather PR info using `gh api` (works for any repo, not just the current one):

```bash
# PR metadata
gh api repos/$OWNER/$REPO/pulls/$PR_NUM --jq '{title,state,body}'

# Changed files
gh api repos/$OWNER/$REPO/pulls/$PR_NUM/files --jq '.[].filename'

# General PR comments (issue-level)
gh api repos/$OWNER/$REPO/issues/$PR_NUM/comments \
  --jq '.[] | "[\(.user.login)] \(.body)"'

# Review-level comments (overall approval/request changes)
gh api repos/$OWNER/$REPO/pulls/$PR_NUM/reviews \
  --jq '.[] | "[\(.user.login)] \(.state): \(.body)"'

# Inline review thread comments (line-specific suggestions — most common for bots)
gh api repos/$OWNER/$REPO/pulls/$PR_NUM/comments \
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

For each AI comment, perform fact-checking:

a) **Extract Technical Claims**
   - API usage recommendations
   - Security vulnerability claims
   - Performance optimization suggestions
   - Best practice recommendations

b) **Verify Using Web Search**
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
     - ✅ Apply if: Multiple reliable sources confirm, or the suggestion is directionally correct even if not the absolute best option (e.g., "use bcrypt instead of MD5" is valid even if Argon2id is now preferred)
     - ⚠️ Review carefully if: Results differ between sources, OR the claim is a contested style preference / best practice with reasonable community support (e.g., adopted by major ESLint configs or style guides)
     - ❌ Skip only if: The claim is **factually wrong** — an API that no longer exists, a false CVE, a non-existent method, or a verifiably incorrect technical statement. Style preferences and debatable best practices belong in ⚠️, not ❌.

### 3. Categorize Verified Suggestions

**✅ Verified & Apply**:
- Confirmed security vulnerabilities
- Documented API misuse
- Proven performance issues
- Official best practices (including suggestions that are directionally correct even if a newer alternative exists — add a note rather than downgrading the verdict)

**⚠️ Partially Verified**:
- Mixed opinions in community
- Context-dependent improvements
- Style preferences with reasonable backing (major style guides, popular linting configs)
- Suggestions that are valid but not the newest best-in-class option

**❌ Incorrect/Unverified**:
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
Verification: [What was confirmed via search]
Fix: [Exact change to apply]
Source: [Documentation/CVE/Benchmark URL]
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
   - Evidence: [Verification source/URL]
   - Change: [Brief description]

### Partially Verified
1. **[File]**: [What was conditionally fixed]
   - Findings: [Mixed findings]
   - Rationale: [Why applied or not]

### Incorrect / Not Applied
1. **[Suggestion]**: [Why it was incorrect]
   - Findings: [What search revealed]

### Summary
- Total AI suggestions: X
- Verified fixes applied: Y
- Incorrect suggestions: Z
```

## Important Notes
- Prioritize official documentation over blog posts; check publication dates to avoid outdated advice
- If a claim cannot be verified but is also not contradicted by any source, mark as ⚠️ rather than ❌ — absence of evidence is not evidence of incorrectness. Reserve ❌ for claims that are actively disproven.
- **Use AskUserQuestionTool** when you need clarification on:
  - Whether to apply a partially verified suggestion
  - How to prioritize conflicting recommendations
  - Whether a security-related change should be applied
  - If AskUserQuestionTool is unavailable and multiple independent clarifications are needed, ask in a single message using QID labels (`Q1`, `Q2`, ...); require `QID: <answer>` responses and allow `QID: OTHER(<concise detail>)` when no option fits
