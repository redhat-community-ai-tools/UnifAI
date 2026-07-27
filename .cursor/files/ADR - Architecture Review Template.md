# Architecture Design Review (ADR)

**Feature Name:** [Enter Name and Jira link]

**Author:** [Name] | **Date:** [Date] | **Priority:** [Low/Med/High]

---

## 1. Executive Summary

| Section | Details |
| :--- | :--- |
| **Problem Statement** | *Describe the pain point this feature addresses (2-3 sentences).* |
| **High-Level Solution** | *Summarize the technical approach (2-3 sentences).* |
| **Success Metrics** | *How do we measure success? (e.g., Latency < 500ms, 95% AI accuracy).* |

---

## 2. Affected Components

*Identifying the blast radius before coding starts.*

| Layer | Component | Action (New/Modified) | File Path |
| :--- | :--- | :--- | :--- |
| Domain | | | |
| Application | | | |
| Adapter — UI / Frontend | | | |
| Adapter — API / Inbound | | | |
| Adapter — Outbound | | | |
| Database | *New tables, columns, indices* | | |
| Config / Infra | *New env vars, secrets, Helm values* | | |

---

## 3. Technical Design

*For each affected component:*

- **Purpose**: what it does
- **Interfaces / Ports**: signatures with type hints
- **Dependencies**: what it depends on
- **Key logic**: pseudocode or bullet-point flow (not full implementation)

### 3a. Architecture & AI Strategy

*Complete this section only if the feature involves LLM / AI components. Remove if not applicable.*

| Component | Design Details |
| :--- | :--- |
| **LLM / Model** | *Which model? (e.g., Gemini 1.5 Pro, GPT-4o). Why this one?* |
| **Context Strategy** | *How is the prompt built? (e.g., RAG, few-shot, system instructions).* |
| **Output Validation** | *How do we catch hallucinations or bad formatting?* |
| **Provider Compatibility** | *Known provider-specific constraints (required fields, streaming behavior, retry).* |

---

## 4. Data Flow

*Describe the request/response flow through the layers, from adapter entry to domain logic and back.*

---

## 5. Risk & Reliability

### 5a. Edge Cases & Failure Modes

| Risk / Edge Case | Mitigation |
| :--- | :--- |
| *Known edge cases and how they are handled* | |
| *Migration or backward-compatibility risks* | |
| *Performance considerations* | |

### 5b. External Dependency Failure Modes

*For every external dependency (MCP server, OAuth provider, Redis, external API):*

| Dependency | Failure Scenario (401 / 503 / timeout) | Behavior (silent / noisy) | Degradation Path |
| :--- | :--- | :--- | :--- |
| | | | |

### 5c. Local Development & Partial-Access Deployment

*For every external dependency:*

| Dependency | Local Dev Strategy (mock / stub / container / bypass) | Deployment Without This Dependency (feature flag / fallback adapter / conditional wiring) |
| :--- | :--- | :--- |
| | | |

### 5d. AI-Specific Risks

*Complete this section only if the feature involves LLM / AI components. Remove if not applicable.*

| Risk | Mitigation Plan |
| :--- | :--- |
| **LLM Failure** | *Fallback if provider is down or rate-limited.* |
| **Data Privacy** | *How PII/sensitive data is protected from the model.* |
| **Cost Control** | *Estimated token usage per user/session.* |
| **Performance** | *Handling long inference times (streaming, async, timeout).* |

---

## 6. Open Questions

*List anything that needs clarification before implementation begins.*

- [ ] ...

---

## 7. Reviewer Feedback

<!-- This section is populated by the Design Reviewer (Phase 2). Do not fill manually. -->

### Verdict: **[PENDING]**

<!-- One of: APPROVE / NEEDS REVISION / REJECT -->

### Critical Findings

<!-- Issues that must be fixed before proceeding. -->

### Architectural Violations

<!-- Hexagonal architecture violations with layer, issue, and fix. -->

### Efficiency Concerns

<!-- Performance or scalability problems with alternatives. -->

### Duplication & Reusability Issues

<!-- Existing components that should be reused. -->

### Risks to Existing System

<!-- Breaking changes, side effects, migration concerns. -->

### Local Dev & Partial-Access Deployment Findings

<!-- Missing local-dev or partial-access deployment strategies. -->

### Recommended Improvements

<!-- Concrete suggestions to improve the design. -->

### Revision Items

<!-- If verdict is not APPROVE, list every item the Designer must address. -->

- [ ] ...
