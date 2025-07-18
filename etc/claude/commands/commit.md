---
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Read
description: Create meaningful git commits by analyzing changes and committing in logical units
---

# Commit in Meaningful Units

## Context

### Current Git Status
- Working directory status: !`git status --short`
- Current branch: !`git branch --show-current`
- Unstaged changes: !`git diff --stat`
- Staged changes: !`git diff --cached --stat`
- Recent commits: !`git log --oneline -10`

### Detailed Change Analysis
- Unstaged file changes: !`git diff --name-status`
- Staged file changes: !`git diff --cached --name-status`
- Full unstaged diff: !`git diff`
- Full staged diff: !`git diff --cached`

## Your Task

Create git commits that follow the principle of "meaningful units" - each commit should represent a single logical change that can be understood and potentially reverted independently.

**⚠️ CRITICAL: Always verify actual git state with live commands. Do not trust the initial context about staging status, as it may be stale or incorrect. Run `git diff --staged --name-only` to see what's actually staged.**

### 1. Analyze All Changes
- Review all modified files and their changes
- Identify logical groupings of changes that belong together
- Look for:
  - Related functionality changes
  - Changes that depend on each other
  - Changes to the same feature or component
  - Separate concerns (e.g., refactoring vs. new features)

### 2. Commit Guidelines
- **One logical change per commit**: Each commit should do one thing well
- **Self-contained**: The codebase should work after each commit
- **Clear purpose**: Anyone reading the commit should understand why it exists
- **Atomic**: Include all files necessary for the change, but no more

### 3. Commit Message Format
Follow conventional commit format:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Subject Line Rules:**
- **Maximum 50 characters** for the entire first line
- Use imperative mood ("add" not "adds" or "added")
- Don't end with a period
- Be concise but descriptive

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring without changing functionality
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates, etc.
- `build`: Changes to build system or dependencies
- `ci`: Changes to CI configuration

**Examples (note character count):**
- `feat(auth): add OAuth2 support` (30 chars)
- `fix(api): handle null response in user endpoint` (48 chars)
- `refactor(utils): extract validation logic` (42 chars)
- `docs(readme): update install instructions` (42 chars)

**If message exceeds 50 characters:**
- Shorten the scope or remove it entirely
- Use abbreviations where clear
- Move details to the body
- Example: `feat: add OAuth2 authentication for user login` → `feat(auth): add OAuth2 login`

**To check character count before committing:**
```bash
# Count characters in a commit message
echo "feat(auth): add OAuth2 authentication support" | wc -c
# Output: 46 (includes newline, so actual is 45)

# Or use this for exact count without newline
echo -n "feat(auth): add OAuth2 authentication support" | wc -c
# Output: 45

# Check the last commit's first line length
git log -1 --pretty=%s | wc -c
```

### 4. Execution Process

**IMPORTANT: Always verify actual git state before committing**

1. **Review all changes** to understand the full scope
2. **Verify staging state** with `git diff --staged --name-only`
   - If no files are staged, report: "No files are staged for commit"
   - Never assume files are staged based on initial context
3. **If staging is needed**:
   - Explicitly show which files need staging
   - Ask user: "These files need to be staged: [list]. Should I stage them?"
   - Only stage after user confirmation
4. **Group related changes** into logical units
5. **For each logical unit**:
   - Verify what's actually staged: `git diff --staged --name-only`
   - Show user: "These files will be committed: [list]"
   - Create a descriptive commit message
   - Attempt commit: `git commit -m "<message>"`
   - If commit fails, handle the error appropriately
6. **Verify each commit** represents a meaningful, atomic change
7. **Continue until all changes are committed**

### 5. Common Scenarios

**Multiple features touched:**
- Commit each feature separately
- If changes are intertwined, consider if they truly belong together

**Bug fix with refactoring:**
- First commit: The bug fix
- Second commit: The refactoring

**Adding a feature with tests:**
- Can be one commit if tests are specific to the feature
- Separate if tests are general improvements

**Configuration and code changes:**
- Usually separate commits unless configuration is required for the code

### 6. What NOT to Do
- Don't commit all changes at once just because they were made together
- Don't mix unrelated changes in one commit
- Don't commit broken code (each commit should leave the project working)
- Don't use vague messages like "updates" or "fixes"
- Don't commit generated files unless necessary
- **Don't trust initial context over actual git state** - always verify with git commands
- **Don't assume files are staged** - check with `git diff --staged --name-only`
- **Don't auto-stage files without user permission** - this can override deliberate choices

### 7. Final Steps
After creating commits:
- Review commit history: `git log --oneline`
- Ensure each commit message clearly describes its purpose
- Verify the project works after each commit (if feasible)

### 8. Handling Commit Hook Errors
If a commit fails due to a commit-msg hook:
- **Read the error message carefully** - hooks often provide specific guidance
- **Show the full error to the user** and ask how they want to proceed
- Common hook requirements:
  - Specific commit message format
  - Issue/ticket number references
  - Message length restrictions
  - Conventional commit format validation
- **Do not bypass the hook** - it's there for a reason
- Ask the user if they want to:
  - Modify the commit message to meet requirements
  - Get more information about the hook requirements
  - Abort the commit

## Important Notes
- If there are no changes to commit, notify the user
- If changes are too intertwined to separate meaningfully, explain why and suggest alternatives
- Always ensure commits maintain a working state of the codebase
- Focus on clarity and future maintainability
- **If a commit-msg hook fails, always prompt the user with the error and ask for guidance**