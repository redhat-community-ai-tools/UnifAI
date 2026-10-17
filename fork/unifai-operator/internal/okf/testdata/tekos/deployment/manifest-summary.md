<!-- GENERATED FILE (ADR-0503/WP-45) - do not edit. Source: helm
template gitops/charts/tekos. Regenerate with: python3 platform/okf/generate_deployment_snapshot.py -->

# Tekos rendered deployment surface

Every object `gitops/charts/tekos` renders (raw-manifest chart - not CR-managed; see `README.md` in this directory for what that means for this agent):

| Kind | Name | Container images |
|---|---|---|
| NetworkPolicy | `tekos-bff` | — |
| ServiceAccount | `tekos-frontend` | — |
| ServiceAccount | `tekos-bff` | — |
| Service | `tekos-frontend` | — |
| Service | `tekos-bff` | — |
| Deployment | `tekos-frontend` | `image-registry.openshift-image-registry.svc:5000/zuno-ai-build/agent-frontend:latest` |
| Deployment | `tekos-bff` | `image-registry.openshift-image-registry.svc:5000/zuno-ai-build/agent-bff:latest` |
| ExternalSecret | `tekos-bff-admin-secret` | — |
| ExternalSecret | `tekos-frontend-secrets` | — |
| Route | `tekos-frontend` | — |
