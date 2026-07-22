# Severity Classification Rubric

This rubric is the shared source of truth for both Judge agents and the Severity
Critic. All severity assignments in the pipeline MUST be consistent with these
definitions.

## 🔴 Critical — System Invariant Violation

A finding is Critical ONLY if it meets ALL of these criteria:

| Dimension | Threshold |
|-----------|-----------|
| **Invariant** | Breaks a documented MUST-level architectural invariant (dependency rule, domain purity, data integrity contract) |
| **Blast radius** | Affects 5+ components, or is system-wide (composition root, shared port, core domain model) |
| **Failure mode** | Silent data corruption, exploitable security vulnerability, or cascading system failure |
| **Detection** | Cannot be caught by unit tests alone — requires integration/E2E testing or manual inspection |
| **Reversibility** | Fixing after deployment requires a migration, breaking API change, or data repair |

**Canonical examples:**
- Domain layer importing a concrete adapter (`from adapters.mongo import MongoRepo`)
- Hardcoded secret or credential in source code
- Cross-service repository access (Service A directly using Service B's repository)
- Dependency direction reversal in composition root wiring
- Injection vulnerability (unsanitized user input reaching shell/SQL/eval)

**NOT Critical (common over-classifications):**
- A thick endpoint → Major (wrong layer, but blast radius is 1 endpoint)
- Missing port ABC for a new adapter → Major (incomplete change, not a runtime failure)
- Business logic in wrong service → Major (misplacement, contained blast radius)
- Swallowed exception → Major (bad practice, but not silent data corruption)

---

## 🟠 Major — Architectural Degradation

A finding is Major if it meets AT LEAST 2 of these 5 criteria:

| Dimension | Threshold |
|-----------|-----------|
| **Rule violated** | Breaks a SHOULD-level engineering standard or a named pattern (SRP, OCP, endpoint thinness, Identity pattern) |
| **Blast radius** | Affects 2-4 other components or creates coupling between bounded contexts |
| **Failure mode** | Incorrect behavior in specific execution paths, or blocks future extensibility |
| **Detection** | Discoverable by targeted tests or careful code review |
| **Reversibility** | Fixable via internal refactoring without external API/schema changes |

**Canonical examples:**
- Business logic inside a controller/endpoint (Endpoint Thinness)
- Service method accepting `user_id: str` where `Identity` is the established pattern
- Application layer importing concrete adapter implementation
- Duplicated business logic introduced by this PR (not pre-existing)
- Missing authorization check on a new endpoint
- SRP violation: class with 10+ public methods in two unrelated clusters
- Catch blocks that swallow exceptions without logging or rethrowing
- Error handled in the wrong layer

**NOT Major (should be Warning or Info):**
- Following an existing convention that happens to violate a rule → INFO (established pattern)
- Duplicated structural/helper/utility code → Warning
- Naming inconsistency → Warning (alignment issue)
- Issue that pre-existed this PR → INFO (tech debt, regardless of inherent severity)
- Logic in test code that shortcuts architecture → Warning

---

## 🟡 Warning — Quality Concern (Non-Blocking)

A finding is Warning if:

| Dimension | Threshold |
|-----------|-----------|
| **Rule violated** | Deviates from convention or best practice, but doesn't break architecture |
| **Blast radius** | Contained to 0-1 components; no cross-boundary impact |
| **Failure mode** | No runtime failure — maintenance burden, readability, or minor inconsistency |
| **Detection** | Obvious to any developer reading the code |
| **Reversibility** | Trivially fixable at any time with zero risk |

**Canonical examples:**
- Naming inconsistency with existing codebase patterns
- Duplicated structural/utility code (not business logic)
- Generic catch-all exception where specific handling is possible
- Unclaimed responsibility (no component's boundaries explicitly claim it)
- Test code with minor architectural shortcuts
- Trivial mapping logic in an endpoint (cosmetic thickness)
- Minor helper placed in a slightly wrong location

---

## 🔵 Info — Observation (Non-Blocking, Zero Penalty)

A finding is Info if ANY of these apply:
- Provenance is `[PRE]` (pre-existed this PR — tech debt)
- Follows an established codebase convention (even if that convention is suboptimal)
- Is a pragmatic workaround with clear justification
- Is purely cosmetic or stylistic
- Is a consolidation/refactoring opportunity for future work
- Is tech debt that should be tracked but not block this PR
- Duplicates another finding's root cause

---

## Decision Tree (Quick Reference)

```
Is provenance [PRE]? ───YES───→ 🔵 INFO (tech debt)
       │ NO
       ▼
Established convention? ───YES───→ 🔵 INFO (established pattern)
       │ NO
       ▼
Cites specific file:line? ───NO───→ 🟡 WARNING (insufficient evidence)
       │ YES
       ▼
ALL 5 Critical criteria met? ───YES───→ 🔴 CRITICAL
       │ NO
       ▼
≥2 Major criteria met? ───YES───→ 🟠 MAJOR
       │ NO
       ▼
🟡 WARNING
```
