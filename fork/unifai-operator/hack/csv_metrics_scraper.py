#!/usr/bin/env python3
"""Add the metrics scraper ServiceAccount to the clusterPermissions of a ClusterServiceVersion.

Usage: csv_metrics_scraper.py CSV SERVICE_ACCOUNT
OLM creates the ServiceAccounts of clusterPermissions and binds their rules in the install namespace, which a bundle
cannot do otherwise (a ClusterRoleBinding manifest needs the namespace of its subject). The user-workload Prometheus
scrapes /metrics with this account's token (config/prometheus/monitor.yaml). Re-running is a no-op.
"""
import sys
from pathlib import Path

import yaml

RULES = [{"nonResourceURLs": ["/metrics"], "verbs": ["get"]}]


def _str(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    # Keep multi-line strings (description, alm-examples) as blocks, like operator-sdk writes them.
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


yaml.SafeDumper.add_representer(str, _str)


def main(csv: str, account: str) -> None:
    path = Path(csv)
    doc = yaml.safe_load(path.read_text())
    perms = doc["spec"]["install"]["spec"].setdefault("clusterPermissions", [])
    perms[:] = [p for p in perms if p.get("serviceAccountName") != account]
    perms.append({"serviceAccountName": account, "rules": RULES})
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=1000))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
