#!/usr/bin/env python3
"""Add a bundle version to an olm.template.basic catalog template.

Usage: catalog_add.py TEMPLATE PACKAGE VERSION BUNDLE_IMAGE CHANNELS
The bundle is appended to every channel of CHANNELS (comma-separated, created if missing) and replaces the current
head of that channel, so OLM upgrades installed operators along the channel. Re-adding a version is a no-op.
"""
import sys
from pathlib import Path

import yaml


def main(template: str, package: str, version: str, image: str, channels: str) -> None:
    path = Path(template)
    doc = yaml.safe_load(path.read_text()) if path.exists() else None
    if not doc:
        doc = {"schema": "olm.template.basic", "entries": [
            {"schema": "olm.package", "name": package, "defaultChannel": channels.split(",")[0]}]}
    entries = doc["entries"]
    name = f"{package}.v{version}"
    if not any(e.get("schema") == "olm.bundle" and e.get("image") == image for e in entries):
        entries.append({"schema": "olm.bundle", "image": image})
    for channel in channels.split(","):
        ch = next((e for e in entries if e.get("schema") == "olm.channel" and e.get("name") == channel), None)
        if ch is None:
            ch = {"schema": "olm.channel", "package": package, "name": channel, "entries": []}
            entries.append(ch)
        if any(e["name"] == name for e in ch["entries"]):
            continue
        entry = {"name": name}
        if ch["entries"]:
            entry["replaces"] = ch["entries"][-1]["name"]
        ch["entries"].append(entry)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    print(f"{name} added to {channels}")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
