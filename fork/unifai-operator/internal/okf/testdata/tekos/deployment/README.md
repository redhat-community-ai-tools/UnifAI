# Tekos Deployment

Real deployment surface (ADR-0503/WP-45; formerly a one-line stub):

- **Chart:** `gitops/charts/tekos/` — a **raw-manifest chart**
  (Deployment/Service/Route/ServiceAccount/NetworkPolicy/ExternalSecret
  per side). Tekos is deliberately NOT CR-managed: it is the ADR-0350/
  ADR-0308 coexistence proof that plain manifests and operator-managed
  agents live side by side, and migrating it remains a non-goal while
  that proof stands.
- **Applications:** `gitops/apps/api/application-d0.yaml` /
  `application-d1.yaml` (named `zuno-api-*` — "api" predates the
  per-agent naming convention), sync-wave `-103`, target namespace
  `zuno-ai-run` (ADR-0329).
- **Snapshot:** [`manifest-summary.md`](manifest-summary.md) — the
  generated, CI-checked list of every object the chart renders.
  Regenerate after any chart change:
  `python3 platform/okf/generate_deployment_snapshot.py`
  (drift fails the lint chain's ADR-0503 step).

`gitops/` remains the sole applied source (ADR-0022) — this directory
mirrors it for review, never the reverse.
