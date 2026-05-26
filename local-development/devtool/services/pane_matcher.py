"""Match tmux pane contents to known services."""

from __future__ import annotations

import re

from devtool.domain.models import ServiceInfo


def match_panes_to_services(
    services: list[ServiceInfo],
    pane_contents: dict[str, str],
) -> dict[str, str]:
    """Match services to tmux pane refs by scanning pane content for
    service directory names or launch commands."""
    mapping: dict[str, str] = {}
    used_panes: set[str] = set()

    for svc in services:
        svc_dir = str(svc.directory)
        for pane_ref, content in pane_contents.items():
            if pane_ref in used_panes:
                continue
            if re.search(rf"\b{re.escape(svc_dir)}\b", content) or \
               re.search(rf"\b{re.escape(svc.name)}\b", content):
                mapping[svc.name] = pane_ref
                used_panes.add(pane_ref)
                break
    return mapping
