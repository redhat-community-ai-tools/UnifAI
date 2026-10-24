#!/usr/bin/env python3
"""Write the SLSA v1 provenance predicate of an image built by a GitHub Actions workflow.

Fork-only (fork/fork-only-paths). Used by .github/workflows/publish-images.yml, which attaches
the result to the image digest with `cosign attest --type slsaprovenance1`; zuno-demo's
platform/supply-chain/verify_unifai_images.py (ADR-0586) requires that attestation, signed by the
same workflow identity as the image signature.

The predicate says which workflow, on which ref, from which commit, built the image: everything
comes from the variables GitHub sets for the run, nothing from the repository's content.

    python3 fork/ci/slsa_provenance.py --component ui --out provenance.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict

BUILD_TYPE = "https://actions.github.io/buildtypes/workflow/v1"
REQUIRED = ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_REF",
            "GITHUB_RUN_ID", "GITHUB_EVENT_NAME")


def predicate(env: Dict[str, str], component: str) -> dict:
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        raise SystemExit(f"not running in GitHub Actions: missing {', '.join(missing)}")
    server, repo = env["GITHUB_SERVER_URL"], env["GITHUB_REPOSITORY"]
    # GITHUB_WORKFLOW_REF is "<owner>/<repo>/<path>@<ref>": the workflow file is the path part.
    workflow_path = env["GITHUB_WORKFLOW_REF"].split("@", 1)[0].split("/", 2)[2]
    attempt = env.get("GITHUB_RUN_ATTEMPT", "1")
    return {
        "buildDefinition": {
            "buildType": BUILD_TYPE,
            "externalParameters": {
                "workflow": {"ref": env["GITHUB_REF"], "repository": f"{server}/{repo}", "path": workflow_path},
                "component": component,
            },
            "internalParameters": {"github": {"event_name": env["GITHUB_EVENT_NAME"],
                                              "runner_environment": env.get("RUNNER_ENVIRONMENT", "")}},
            "resolvedDependencies": [{"uri": f"git+{server}/{repo}@{env['GITHUB_REF']}",
                                      "digest": {"gitCommit": env["GITHUB_SHA"]}}],
        },
        "runDetails": {
            "builder": {"id": f"{server}/{env['GITHUB_WORKFLOW_REF']}"},
            "metadata": {"invocationId": f"{server}/{repo}/actions/runs/{env['GITHUB_RUN_ID']}/attempts/{attempt}"},
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--component", required=True, help="rag, multiagent, backend, identity or ui")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(predicate(dict(os.environ), args.component), fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
