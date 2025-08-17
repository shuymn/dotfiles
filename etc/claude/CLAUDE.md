## Requirements Interpretation Rules

### Handling Ambiguous Requirements

- **No Guessing**: Always ask questions about unclear points
- **Confirmation Priority**: Confirm with "Is my understanding that ○○ correct?"
- **Minimal Execution**: Execute only what is explicitly requested

### Prohibited Actions Checklist

- [ ] Adding unrequested features
- [ ] Unauthorized refactoring
- [ ] Implementation based on assumptions
- [ ] "While we're at it" work
- [ ] Expansive interpretation from good intentions

### Self-Check Before Execution

1. Was this explicitly requested? → If NO, don't execute
2. Does the interpretation include assumptions? → If YES, ask questions
3. Am I trying to do something "while we're at it"? → If YES, stop

### Bad Example vs Good Example

#### ❌ Bad Example

User: "Create a login function"
Claude: Security is important too, so I implemented two-factor authentication as well!

#### ✅ Good Example

User: "Create a login function"
Claude: Let me confirm about the login function:

- Is email/password authentication acceptable?
- Are there any session management requirements?
- Is it possible to use existing authentication gems?

## Development Quality Standards

### Hardcoded Values

- **Never use hardcoded values**: Always use configuration files, environment variables, or constants
- **Pre-commit check**: Review all code for hardcoded values before suggesting commits
- **Dynamic over static**: Prefer parameterized solutions over fixed values

### Prohibited Development Practices

**Never compromise code quality to bypass errors:**

- [ ] Relaxing conditions just to pass tests or type checks
- [ ] Skipping tests or using inappropriate mocks to avoid real issues
- [ ] Hardcoding expected outputs or responses
- [ ] Ignoring, suppressing, or hiding error messages
- [ ] Applying temporary fixes that defer problems

**Always address root causes**: When encountering errors, investigate and fix the underlying issue rather than working around it.
