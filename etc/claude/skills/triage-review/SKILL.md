---
name: triage-review
description: Fetches PR review comments from AI reviewers (Copilot, Google Code Assist, etc.), verifies their accuracy against official sources, and applies only validated fixes. Use when the user wants to process AI code review comments, handle bot review suggestions, or triage automated review feedback on a pull request.
allowed-tools: [Bash, Read, Grep, Glob, WebSearch]
---

# Apply Verified Fixes from AI Review Comments

## Context

### Current State
- Current branch: `git branch --show-current`
- Uncommitted changes: `git status --porcelain`
- PR number (if exists): `gh pr view --json number --jq '.number' 2>/dev/null || echo "No PR found"`
- PR URL: `gh pr view --json url --jq '.url' 2>/dev/null || echo ""`

### PR Information (if PR exists)
- PR title: `gh pr view --json title --jq '.title' 2>/dev/null || echo ""`
- PR state: `gh pr view --json state --jq '.state' 2>/dev/null || echo ""`
- Changed files in PR: `gh pr view --json files --jq '.files[].path' 2>/dev/null || echo ""`

### Review Comments
- All PR comments: `gh pr view --json comments --jq '.comments[] | "[\(.author.login)] \(.body)"' 2>/dev/null || echo "No comments"`
- Review threads: `gh pr view --json reviews --jq '.reviews[] | "[\(.author.login)] \(.state): \(.body)"' 2>/dev/null || echo "No reviews"`

## Your task

1. **Identify AI Reviewers**
   - Look for comments from: google-code-assist, github-copilot, copilot[bot], google-code-assist[bot]
   - Extract all suggestions from AI reviewers

2. **Verify Each AI Suggestion**
   For each AI comment, perform fact-checking:

   a) **Extract Technical Claims**
      - API usage recommendations
      - Security vulnerability claims
      - Performance optimization suggestions
      - Best practice recommendations

    b) **Verify Using Web Search**
      Use the agent's available Web Search Tool(s) with the SAME query to cross-verify information:

      - **Search Strategy**:
        1. Send identical queries to all available web search tools
        2. Compare results across tools and sources
        3. Look for consensus or discrepancies
        4. Prioritize information that appears in multiple reliable sources
        5. If only one web search tool is available, cross-check with multiple independent sources

      - **Verification Process**:
        - API/Method validation: Search "[language] [method_name] documentation" across available tool(s)
        - Security claims: Search "[vulnerability] CVE [year]" and compare findings
        - Performance claims: Search "[technique] benchmark comparison" and compare sources
        - Best practices: Search "[technology] official best practices" and verify consistency

      - **Cross-Verification Examples**:
        ```
        Query: "React useEffect cleanup function best practice"
        → Compare whether multiple sources return similar official React documentation

        Query: "Log4j CVE-2021-44228 vulnerability details"
        → Verify whether multiple sources confirm the same security issue

        Query: "Python list comprehension vs for loop performance"
        → Check whether benchmark conclusions align across sources
        ```

      - **Decision Criteria**:
        - ✅ Apply if: Multiple reliable sources confirm the same information
        - ⚠️ Review carefully if: Results differ between tools/sources
        - ❌ Skip if: No reliable source can verify the claim

3. **Categorize Verified Suggestions**
   After verification, classify each suggestion:

   **✅ Verified & Apply**:
   - Confirmed security vulnerabilities
   - Documented API misuse
   - Proven performance issues
   - Official best practices

   **⚠️ Partially Verified**:
   - Mixed opinions in community
   - Context-dependent improvements
   - Style preferences with some backing

   **❌ Incorrect/Unverified**:
   - Outdated recommendations
   - Non-existent APIs/methods
   - False security claims
   - Subjective preferences without backing

4. **Apply Only Verified Fixes**
   For each verified suggestion:
   ```
   File: [filename]
   Line: [line number or range]
   Issue: [Brief description]
   Verification: [What was confirmed via search]
   Fix: [Exact change to apply]
   Source: [Documentation/CVE/Benchmark URL]
   ```

5. **Implementation Process**
   - Read current file content
   - Apply verified changes ONE topic at a time
   - After each topic fix:
     1. Save the modified files

6. **Final Report** (use the user's language)
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
- If unable to verify a claim, mark as "unverified" and skip — false positives from AI reviewers are common
- **Use AskUserQuestionTool** when you need clarification on:
  - Whether to apply a partially verified suggestion
  - How to prioritize conflicting recommendations
  - Whether a security-related change should be applied
