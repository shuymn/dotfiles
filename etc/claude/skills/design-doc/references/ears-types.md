<!-- do not edit: generated from skills/src/design-doc/references/ears-types.md; edit source and rebuild -->

# EARS Requirement Types

Easy Approach to Requirements Syntax (EARS) provides 5 structured sentence patterns for writing unambiguous, testable requirements.

## The 5 EARS Types

### 1. Ubiquitous

Requirements that **always** hold, with no triggering event or condition.

- **Syntax**: `The <system> shall <action>.`
- **Example**: `The system shall encrypt all data at rest using AES-256.`
- **Use when**: The behavior is unconditional and continuous.

### 2. Event-Driven

Requirements triggered by a **specific event**.

- **Syntax**: `When <trigger>, the <system> shall <action>.`
- **Example**: `When the user submits the login form, the system shall validate credentials within 2 seconds.`
- **Use when**: The behavior occurs in response to a discrete event.

### 3. Unwanted (Fail-Closed)

Requirements that handle **error conditions or forbidden states**.

- **Syntax**: `If <unwanted condition>, then the <system> shall <action>.`
- **Example**: `If the API key is expired, then the system shall reject the request with HTTP 401.`
- **Use when**: The behavior is a safety net or error-handling path.

### 4. State-Driven

Requirements active **while a condition holds**.

- **Syntax**: `While <state>, the <system> shall <action>.`
- **Example**: `While the system is in maintenance mode, the system shall return HTTP 503 for all API requests.`
- **Use when**: The behavior persists as long as a state is active.

### 5. Optional (Feature-Gated)

Requirements that apply only **when a feature or configuration is enabled**.

- **Syntax**: `Where <feature inclusion>, the <system> shall <action>.`
- **Example**: `Where audit logging is enabled, the system shall record all admin actions to the audit log.`
- **Use when**: The behavior depends on a configurable feature flag or deployment option.

## Selection Decision Table

| Condition | EARS Type |
|-----------|-----------|
| Always true, no trigger, no state | Ubiquitous |
| Happens in response to a discrete event | Event-Driven |
| Handles error, failure, or forbidden state | Unwanted |
| Active while a condition persists | State-Driven |
| Depends on feature flag or configuration | Optional |

## Anti-Patterns

### Ubiquitous Overuse

**Problem**: Defaulting to Ubiquitous when a more specific type applies. This hides triggers, conditions, and failure modes.

**Symptoms**:
- AC describes behavior that only happens after a user action → should be **Event-Driven**
- AC describes error handling → should be **Unwanted**
- AC describes behavior during a specific mode → should be **State-Driven**

**Rule**: Choose Ubiquitous only after confirming none of the other 4 types apply. If the requirement mentions "when", "if", "while", "where", or any conditional language, it is NOT Ubiquitous.

### Mixing Types

**Problem**: Combining multiple EARS patterns in a single AC.

**Fix**: Split into separate ACs, each with a single EARS type.

### Vague Actions

**Problem**: Using unmeasurable verbs like "handle", "manage", "process" in the `<action>` slot.

**Fix**: Replace with concrete, observable, testable actions (return specific status code, write specific record, emit specific event).
