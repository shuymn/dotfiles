<!-- do not edit: generated from skills/src/adversarial-verify/references/attack-vectors.md; edit source and rebuild -->

# Attack Vectors Reference

Structured attack strategies for adversarial verification. Select categories relevant to the change area — do not blindly apply all categories.

Vectors marked `[required]` define the minimum coverage baseline within a selected category. Non-required vectors are still applicable and should be probed when relevant; the tag does not grant skip permission. Tier-specific coverage obligations (how many `[required]` vectors must be covered) are defined in SKILL.md Step 4.

## 1. Input Boundary Attacks

Target: Input validation, parsing, and type handling.

- **Empty/null values** [required]: Pass empty strings, null, undefined, zero-length arrays where inputs are expected.
- **Boundary values**: Integer overflow/underflow, max-length strings, deeply nested structures.
- **Type coercion**: Pass wrong types (string where number expected, object where array expected).
- **Unicode edge cases**: Zero-width characters, RTL override, homoglyph substitution, emoji in identifiers.
- **Injection** [required]: SQL injection, command injection, path traversal sequences, template injection, header injection. Tools: semgrep, sqlmap.

## 2. Error Handling Attacks

Target: Failure paths, recovery logic, and resilience.

- **Network failures**: Simulate timeout, connection reset, DNS failure, partial response.
- **Resource exhaustion**: Disk full, memory pressure, file descriptor limits, connection pool exhaustion.
- **Invalid state transitions** [required]: Call methods in wrong order, re-initialize after teardown, use after close.
- **Retry storms**: Trigger conditions that cause unbounded retries or exponential backoff failures.

## 3. Security Boundary Attacks

Target: Authentication, authorization, and data protection.

- **Authentication bypass** [required]: Missing auth checks, token manipulation, session fixation, credential stuffing paths.
- **Privilege escalation**: Access resources of other users/roles, horizontal and vertical escalation.
- **Path traversal**: `../` sequences, absolute paths, symlink following, null byte injection in paths.
- **Sensitive data exposure**: Error messages leaking internals, logs containing secrets, debug endpoints, stack traces in production responses.

## 4. Concurrency & Race Condition Attacks

Target: Parallel execution, shared state, and timing.

- **TOCTOU (Time-of-Check-Time-of-Use)** [required]: Race between validation and use of a resource. Tools: ThreadSanitizer, go test -race.
- **Double submission**: Duplicate requests within a short window (idempotency violations).
- **Deadlock provocation**: Acquire locks in reversed order, hold locks across async boundaries.
- **Optimistic locking violations**: Concurrent updates to the same resource without conflict detection.

## 5. State & Data Integrity Attacks

Target: Data consistency, persistence, and caching.

- **Partial failure** [required]: Crash or error midway through a multi-step operation (atomicity violations). Tools: toxiproxy, kill -9 during operation.
- **Data corruption**: Malformed data in storage, truncated writes, encoding mismatches.
- **Migration safety**: Data created before migration vs. after — schema compatibility, rollback safety.
- **Cache poisoning**: Stale cache entries, cache key collisions, inconsistent cache invalidation.

## 6. Rollback & Recovery Attacks

Target: Feature flags, configuration changes, and graceful degradation.

- **Feature flag toggling**: Rapid on/off cycling, partial rollout states, flag dependency chains.
- **Configuration changes**: Invalid config values, missing required config, config hot-reload race conditions.
- **Dependency failures**: Downstream service unavailable, upstream API version mismatch, certificate expiry.
- **Graceful degradation** [required]: Verify fallback paths work when primary path fails, ensure degradation is observable.

## Recommended Tools

When automated tools are available in the project, use them alongside manual probes to increase coverage depth. Tool availability is checked via `command -v`; skip unavailable tools without blocking.

| Category | Tool / Framework | When to Use |
|----------|-----------------|-------------|
| 1. Input Boundary | Hypothesis (Python), fast-check (JS/TS) | Property-based testing for input validation |
| 1. Input Boundary | sqlmap, semgrep | Injection detection (SQL, command, template) |
| 2. Error Handling | toxiproxy, Chaos Monkey | Network failure simulation and resilience testing |
| 3. Security Boundary | OWASP ZAP, semgrep | Automated security scanning and static analysis |
| 4. Concurrency | ThreadSanitizer (C/C++/Go), `go test -race` | Race condition and data race detection |
| 5. State & Data Integrity | schema-diff, pg_dump diff | Migration safety and data consistency verification |
| 6. Rollback & Recovery | Feature flag SDKs with audit logging | Toggle state tracking and rollback verification |

## Selection Guidance

Match attack categories to the **semantic characteristics** of the change, not to fixed labels. The table below provides common mappings as starting points — adapt based on actual defect impact in your domain.

| Change Characteristic | Recommended Categories |
|----------------------|----------------------|
| Accepts external/user input or crosses trust boundary | 1 (Input Boundary), 3 (Security Boundary) |
| Handles money, metering, or irreversible transactions | 1 (Input Boundary), 4 (Concurrency), 5 (State & Data Integrity) |
| Protects secrets, credentials, or personally identifiable data | 1 (Input Boundary), 3 (Security Boundary), 5 (State & Data Integrity) |
| Modifies persistent storage schema or data format | 1 (Input Boundary), 5 (State & Data Integrity), 6 (Rollback & Recovery) |
| Defines or changes a contractual interface (API, protocol, event schema) | 1 (Input Boundary), 2 (Error Handling), 4 (Concurrency) |
| Manages shared mutable state or coordination | 4 (Concurrency), 5 (State & Data Integrity), 6 (Rollback & Recovery) |
| Communicates with external services or third-party systems | 2 (Error Handling), 4 (Concurrency), 6 (Rollback & Recovery) |
| Controls feature flags, runtime configuration, or deployment toggles | 2 (Error Handling), 5 (State & Data Integrity), 6 (Rollback & Recovery) |

Refer to the Change Rationale's `Defect Impact` and `Blast Radius` to determine category priority — prioritize categories whose attack surface overlaps with the stated defect impact and blast radius.

## Project-Specific Vectors

<!-- Populated automatically when adversarial-verify discovers vulnerabilities (FAIL→fix→PASS cycle). -->
<!-- Format: - **[Category]: [Vector Name]**: [Description and attack method]. Source: Task N, YYYY-MM-DD. -->
