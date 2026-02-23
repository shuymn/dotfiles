# Commit Examples and Scenarios

## Examples of Meaningful Units

**Good (separate commits):**
- `fix(auth): handle null user sessions`
- `refactor(auth): extract session validation logic`
- `feat(auth): add remember me option`

**Bad (bundled together):**
- `fix(auth): handle null sessions and add remember me option and refactor validation`

## When Uncertain About Grouping — Example Prompt

```
I see changes to both authentication and user profile code. I'm unsure if these should be:
1. One commit (if profile changes depend on auth changes)
2. Two commits (if they're independent improvements)

The changes are:
- auth.js: Added session timeout handling
- profile.js: Added avatar upload validation

How would you like me to group these changes?
```

## Common Scenarios Requiring Separate Commits

**Refactoring + Feature:**
- COMMIT 1: Refactor existing code (no behavior change)
- COMMIT 2: Add new feature using refactored structure

**Bug Fix + Test:**
- COMMIT 1: Add failing test that demonstrates the bug
- COMMIT 2: Fix the bug (test now passes)

**Multiple Bug Fixes:**
- COMMIT 1: Fix null pointer in user service
- COMMIT 2: Fix race condition in cache manager
- COMMIT 3: Fix memory leak in data processor

**Style + Logic Changes:**
- COMMIT 1: Fix business logic error
- COMMIT 2: Format/lint the affected files

## Patch-Based Partial Staging

When a file contains multiple logical changes, stage partial changes via editable patch:
1. Export the full diff for target files:
   - `git diff -- <target-file> > /tmp/partial-stage.patch`
   - Or multiple files: `git diff -- <file1> <file2> > /tmp/partial-stage.patch`
2. Keep a backup of the original patch:
   - `cp /tmp/partial-stage.patch /tmp/partial-stage.full.patch`
3. Edit `/tmp/partial-stage.patch` and remove hunks unrelated to the current logical unit
4. Validate before applying:
   - `git apply --check --cached /tmp/partial-stage.patch`
5. Apply patch to index only (working tree remains unchanged):
   - `git apply --cached /tmp/partial-stage.patch`
6. Verify split is correct:
   - `git diff --cached`
   - `git diff`
7. If check/apply fails, STOP and ask user how to proceed
