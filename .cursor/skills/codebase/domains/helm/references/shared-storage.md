# Shared Storage (Helm)

Cross-cutting PVC patterns used by UnifAI charts.

## Owns

- Platform-wide shared volume charts under `helm/shared-resources/`
- Module shared-storage charts (rag / multiagent)
- Consumer volume / volumeMount blocks that attach those claims

## Does NOT own

- Deploy pipeline stage ordering (`ci/pipeline-deploy.groovy`) — referenced only as the enforcer of fresh-install order
- Application-level logging / file I/O configuration inside services

## Recipe

For adding or extending a shared PVC: `../recipes/add-shared-pvc.md`

## Established Patterns

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Platform PVC in `shared-resources`; mounts in other helmfiles | Platform shared-storage charts + consumer values | Cross-helmfile `needs:` unsupported; CI orders fresh installs |
| Hardcoded consumer `claimName` = default producer name | Consumer chart values | Values files are not cross-templated |
| Module PVC chart co-located with consumers | Module helmfiles (rag, multiagent) | One apply creates and mounts |

## Boundaries

- Producer chart defines PVC metadata and size/class
- Consumer charts only reference `claimName` + mountPath (and optional `subPathExpr`)
- Renames require coordinated producer + all consumer updates
