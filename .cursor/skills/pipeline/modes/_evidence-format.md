# Evidence Pack Format

This is the contract between the Scout agent (producer) and Judge agents (consumers). The Scout MUST output in this exact structure. Judges expect these sections and use them as pre-verified data.

## Provenance Tags

Every finding row that references a file:line MUST include a provenance tag:

- `[NEW]` — line was added or modified in this PR (appears as `+` in the unified diff)
- `[PRE]` — line pre-existed before this PR (not touched in the diff)
- `[SCO]` — file was scope-expanded (not in the original diff), provenance unknown

These tags are critical for Judges to enforce Severity Calibration: only MAJOR/CRITICAL if this diff specifically introduces the problem.

## Schema

```markdown
## Evidence Pack

### Scope
- **Files in scope**: [list each file with its domain assignment, or "no domain" for unmatched]
- **Domains resolved**: [list of domain keys that were loaded]
- **Excluded files**: [machine-generated files that were skipped]

### Diff Summary
[The unified diff output from `git diff origin/<base>...HEAD`]

Token budget rules:
- If total diff is ≤5K tokens: include full unified diff verbatim
- If total diff is >5K tokens: for each file, include full diff if that file's hunks are <100 lines;
  for larger files, include only `@@` hunk headers + first 3 and last 3 lines of each hunk
- Always exclude machine-generated files from the diff output

This section enables Judges to see exactly which lines are `+` (added) and `-` (removed) in this PR.

### Domain Context (per resolved domain)

#### {domain-key}
- **Routing**: [endpoint groups, URL prefixes]
- **Port wiring**: [which ports exist, what adapters implement them]
- **Boundaries**: [what this domain owns vs. does NOT own]
- **Established Patterns** (suppression list): [patterns pre-approved by convention — judges must NOT flag these as violations]
- **Recipe suppressions**: [any "DO NOT flag" items from loaded recipes]

### Import Analysis

| File | Import Statement | Source Layer | Target Layer | Direction Issue | Prov |
|------|-----------------|-------------|-------------|----------------|------|

- Direction Issue: "OK" if dependency flows inward, or "Domain → Adapter" if it violates direction.
- Prov: `[NEW]`, `[PRE]`, or `[SCO]` per the Provenance Tags section above.

### Port/Adapter Wiring

| Port (ABC) | Location | Concrete Adapter | Adapter Location | Injection Site |
|------------|----------|-----------------|------------------|----------------|

### Dead Code Candidates

| File:Line | Type | Reason | Prov |
|-----------|------|--------|------|

Type: one of `unused_import`, `unused_variable`, `unused_parameter`, `commented_code`, `unreachable_branch`

### Security Scan

| File:Line | Pattern | Risk | Prov |
|-----------|---------|------|------|

Pattern: what was matched (e.g., "hardcoded API key", "unsanitized input to subprocess")

### Duplication Candidates

| New/Changed File | Existing File | Overlap Description | Lines |
|-----------------|---------------|---------------------|-------|

### Sibling Contract Alignment

| Group | Field A (file) | Field B (file) | Same Concept? | Majority Convention | Prov |
|-------|---------------|---------------|---------------|---------------------|------|

Group: the namespace/package containing the sibling actions (e.g. `actions/auth/`).
"Same Concept?" is confirmed when one field's value is assigned to a parameter named like the other.

### Composition Roots

[Relevant excerpts from bootstrap/container files showing how ports are wired to concrete adapters for the scoped domains. Include only bindings relevant to scoped files.]
```

## Rules for Producers (Scout)

1. Every section header MUST be present. If a section has no findings, write "None found." under it.
2. Cap total output at ~15K tokens. Summarize domain context if needed.
3. Do NOT include severity assessments, recommendations, or opinions.
4. Import Analysis must cover ALL changed/added Python files — do not skip any.
5. The Diff Summary follows the token budget rules in the schema above.
6. Every finding row MUST include a Prov tag. Use the unified diff to determine `[NEW]` vs `[PRE]`.

## Rules for Consumers (Judges)

1. Treat evidence pack data as pre-verified. You do NOT need to re-read files already covered.
2. If the evidence pack lacks data for a specific dimension you need, read the file directly.
3. Established Patterns and Recipe suppressions from the pack are binding — do NOT flag them as violations.
4. The Import Analysis "Direction Issue" column is a mechanical classification. Apply judgment to determine if flagged items are true violations or acceptable (e.g., utility imports, type-only imports).
5. **Provenance enforcement**: Findings tagged `[PRE]` MUST be classified as INFO (tech debt) — they cannot be MAJOR or CRITICAL. Only `[NEW]` findings can receive blocking severity. `[SCO]` findings require the Judge to verify provenance before assigning severity.
