#!/usr/bin/env python3
"""Render the fork's helm tree: copy helm/ and deep-merge fork overlays over helm/values/*.yaml.

Upstream files are never edited, so syncing with upstream stays conflict-free.
Usage: render_values.py OUT_DIR  (env: REGISTRY, IMAGE_PREFIX, IMAGE_TAG + every ${VAR} used by overlays)
"""
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

LOG = logging.getLogger("render_values")
ROOT = Path(__file__).resolve().parent.parent
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand(text: str) -> str:
    missing = {m for m in VAR_RE.findall(text) if m not in os.environ}
    if missing:
        raise SystemExit(f"missing environment variable(s): {', '.join(sorted(missing))}")
    return VAR_RE.sub(lambda m: os.environ[m.group(1)], text)


def deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def set_path(doc: dict[str, Any], dotted: str, value: dict[str, Any]) -> None:
    node = doc
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node.setdefault(parts[-1], {}).update(value)


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(expand(path.read_text())) or {}


def main(out: Path) -> None:
    for var in ("REGISTRY", "IMAGE_PREFIX", "IMAGE_TAG"):
        if not os.environ.get(var):
            raise SystemExit(f"{var} must be set")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "helm", out)
    images = yaml.safe_load((ROOT / "fork/images.yaml").read_text())
    values_dir = out / "values"
    for target in sorted(values_dir.glob("*.yaml")):
        doc = yaml.safe_load(target.read_text()) or {}
        overlay = ROOT / "fork/values" / target.name
        if overlay.exists():
            deep_merge(doc, load(overlay))
        spec = images.get(target.name)
        if spec:
            repo = f"{os.environ['REGISTRY']}/{os.environ['IMAGE_PREFIX']}-{spec['component']}"
            for dotted in spec["paths"]:
                set_path(doc, dotted, {"repository": repo, "tag": os.environ["IMAGE_TAG"]})
        target.write_text(yaml.safe_dump(doc, sort_keys=False))
        LOG.info("rendered %s", target.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
