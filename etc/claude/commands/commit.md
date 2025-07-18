---
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Read
description: Create meaningful git commits by analyzing changes and committing in logical units
---

# Commit in Meaningful Units

## Context

### Repository State
- Status overview: !`git status --short`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

### Change Analysis
- **Unstaged changes**: !`git diff --stat` (summary) | !`git diff` (full)
- **Staged changes**: !`git diff --cached --stat` (summary) | !`git diff --cached` (full)

## Your Task

Create git commits where each commit represents a single logical change that can be understood and potentially reverted independently.

**⚠️ CRITICAL: Always verify actual git state with live commands. Do not trust the initial context about staging status, as it may be stale or incorrect.**

### 1. How to Create Meaningful Commits

**Identify a Single Logical Change:**
- Review all modifications using `git status` and `git diff`
- Group changes that:
  - Implement one feature together
  - Fix one specific bug
  - Refactor one component
  - Update related documentation
- Keep different concerns separate (don't mix features with unrelated refactoring)

**Stage Only That Change:**
- Use `git add <files>` to stage complete files
- Use `git add -p` for partial file staging when needed
- Verify staged changes: `git diff --cached`

**Ensure Self-Contained Commits:**
- Each commit should leave the codebase in a working state
- Include all files necessary for the change to function
- Don't include unrelated changes

### 2. Commit Message Format
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

### 3. Execution Process

1. **Check current state**
   ```bash
   git status
   git diff --staged --name-only    # See what's already staged
   ```

2. **For each logical unit of work**:
   - Review changes:
     ```bash
     git diff                      # Unstaged changes
     git diff <file>              # Specific file changes
     ```
   - Stage related files:
     ```bash
     git add <file1> <file2>      # Stage specific files
     # OR
     git add -p                   # Interactive staging for partial changes
     ```
   - Verify staged content:
     ```bash
     git diff --cached            # Review what will be committed
     ```
   - Check commit message length:
     ```bash
     echo -n "feat(scope): description" | wc -c
     ```
   - Commit with descriptive message:
     ```bash
     git commit -m "type(scope): subject

     Detailed explanation if needed"
     ```

3. **After each commit**:
   ```bash
   git log --oneline -1             # Verify the commit
   git status                       # Check remaining changes
   ```

### 4. Common Scenarios

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

### 5. What NOT to Do
- Don't commit all changes at once just because they were made together
- Don't mix unrelated changes in one commit
- Don't commit broken code (each commit should leave the project working)
- Don't use vague messages like "updates" or "fixes"
- Don't commit generated files unless necessary
- Don't trust initial context over actual git state - always verify with live commands

### 6. Final Steps
After creating commits:
- Review commit history: `git log --oneline`
- Ensure each commit message clearly describes its purpose
- Verify the project works after each commit (if feasible)

### 7. Handling Commit Hook Errors
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
- Focus on clarity and future maintainability
- If a commit-msg hook fails, always prompt the user with the error and ask for guidance