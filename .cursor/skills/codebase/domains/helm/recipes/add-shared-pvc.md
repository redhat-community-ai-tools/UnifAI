# Recipe: Add or Extend a Shared PVC

Use when introducing a new shared volume or wiring additional consumers to an existing claim.

## Choose Placement

| Kind | Put PVC chart in | Consumers |
|------|------------------|-----------|
| Platform-wide (many modules) | `helm/shared-resources/` + release in `shared-resources.yaml.gotmpl` | Each consumer module’s chart `values.yaml` |
| Module-local | Same module helmfile as consumers | Sibling releases in that helmfile |

## Checklist

| Must | Why |
|------|-----|
| PVC `accessModes` / storage class match the workload | Wrong mode breaks multi-pod or single-writer assumptions |
| Default PVC name treated as the cross-chart contract | Consumers hardcode `claimName` |
| Every consumer mount updated if the PVC name changes | Drift leaves pods Pending |
| Env vars used in `subPathExpr` stay in sync with image tag defaults (e.g. `default .Chart.AppVersion`) | Empty or mismatched expansion breaks mount paths |
| Platform PVCs deployed with shared infra on fresh install | Deploy pipeline prepends `shared-resources` on `FRESH_INSTALL` |

## Reviewer Checklist

| Check | Expected |
|-------|----------|
| Placement matches platform-wide vs module-local table above | Wrong helmfile couples unrelated modules or splits a single apply |
| Producer PVC name equals every consumer `claimName` | Scheduling requires an existing claim |
| Consumer values do not assume producer keys from `shared-resource-values.yaml` | Those values are not loaded by other helmfiles |

| DO NOT flag | Why |
|-------------|-----|
| Missing helmfile `needs:` from an app module to a `shared-resources` PVC | Cross-helmfile `needs:` is unsupported; fresh-install order is enforced in CI |
| Hardcoded `claimName` equal to the producer’s default PVC name | Established cross-chart contract; values are not shared across helmfiles |
| Module shared-storage release listed alongside its consumers in one helmfile | Same pattern as existing rag / multiagent charts |
