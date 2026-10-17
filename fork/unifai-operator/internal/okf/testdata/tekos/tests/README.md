# Tekos Contract Tests (ADR-0504)

Per-agent, repo-side, static contract suites - run by
`python3 platform/okf/run_agent_contract_tests.py` from the repository
root (a blocking lint-chain step; test files are `test_*.py` under the
three subdirectories, each executable standalone).

Three-layer boundary (ADR-0504): **schema/structural** checks are
platform-wide and live in `platform/supply-chain/` +
`platform/okf/schema/` - never duplicated here; **contract** checks
(this directory) are Tekos-specific and need only repository files - no
cluster, no credentials, no model calls; **behavioral** checks stay in
`evaluations/tekos/` (ADR-0027/ADR-0028, the shared ADR-0342 runner).

- `contract/` - bundle-level self-consistency (declared tools/domains
  exist in policy with non-empty group intersections; ADR-0503 matrix
  and deployment snapshot are current)
- `tasks/` - per-task assertions (live_read_tool within allowed_tools,
  primary_task declared, ADR-0512 project_required marks well-formed)
- `prompts/` - prompt lint (required OKF frontmatter, referenced by a
  task, golden-format checks where a task defines one)

**Blocking rule (ADR-0504):** Tekos is not exempt from this structure
requirement. `contract/`, `tasks/` and `prompts/` must contain real, green
tests before Tekos can be promoted to Stage 2 -
`platform/templates/agent/PROMOTION.md` step 4 is explicit: empty stub
directories are not Stage 2. Filling these suites is owned by whichever
work promotes Tekos, but the requirement itself blocks promotion, not
just documents an aspiration. Tekos's only historical exception from the
promotion checklist is the deployment mechanism (plain manifests instead
of the `AIAgent` CR, per PROMOTION.md step 2 / ADR-0350's coexistence
proof) - never this tests-content requirement.
