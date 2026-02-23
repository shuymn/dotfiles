---
name: triage-review
description: Fetches PR review comments from AI reviewers, verifies accuracy, and applies valid fixes. Use when the user wants to process AI code review comments, apply AI reviewer suggestions, or verify and implement automated code review feedback. Works with GitHub PRs and uses web search to verify AI claims before applying changes.
allowed-tools: [Bash, Read, TodoWrite, Grep, Glob, Task, WebSearch]
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
   Issue: [Brief description in Japanese]
   Verification: [What was confirmed via search]
   Fix: [Exact change to apply]
   Source: [Documentation/CVE/Benchmark URL]
   ```

5. **Implementation Process**
   - Read current file content
   - Apply verified changes ONE topic at a time
   - After each topic fix:
     1. Save the modified files

6. **Final Report in Japanese**
   ```markdown
   ## AI レビュー検証・修正レポート

   ### ✅ 検証済み・適用した修正
   1. **[File]**: [What was fixed]
      - 根拠: [Verification source/URL]
      - 修正内容: [Brief description]

   ### ⚠️ 部分的に検証・条件付き適用
   1. **[File]**: [What was conditionally fixed]
      - 検証結果: [Mixed findings]
      - 判断理由: [Why applied or not]

   ### ❌ 誤り・未適用の提案
   1. **[Suggestion]**: [Why it was incorrect]
      - 検証結果: [What search revealed]

   ### 検証サマリー
   - AI提案総数: X件
   - 検証済み修正: Y件
   - 誤った提案: Z件
   ```

## Important Notes
- ALWAYS verify AI suggestions before applying
- Prioritize official documentation over blog posts
- Check publication dates to avoid outdated advice
- If unable to verify, mark as "unverified" and skip
- Document all verification sources for transparency
- Be especially careful with security-related changes
- When in doubt, search multiple sources
- **Use AskUserQuestionTool** when you need clarification on:
  - Whether to apply a partially verified suggestion
  - How to prioritize conflicting recommendations
  - Whether a security-related change should be applied
