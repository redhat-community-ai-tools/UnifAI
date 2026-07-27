"""
Template seeder — loads YAML fixtures into MongoDB.

Scan all YAML files in run/fixtures/templates/. For each file:
  - If template_id is NOT already in MongoDB → insert.
  - If it EXISTS (including soft-deleted) → skip (preserves admin edits/deletions).

Run via:  python scripts/seed_templates.py
"""
import logging
from pathlib import Path
from datetime import datetime, timezone

import yaml

from mas.blueprints.models.blueprint import BlueprintDraft
from mas.templates.models.template import (
    Template,
    PlaceholderMeta,
    TemplateMetadata,
)
from mas.templates.repository.repository import TemplateRepository

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent / "templates"


def seed_templates(repository: TemplateRepository) -> int:
    """
    Load YAML template fixtures into the database.

    Returns the number of templates inserted (skips already-existing ones).
    """
    if not FIXTURES_DIR.is_dir():
        logger.info("No fixtures directory found at %s — skipping seed.", FIXTURES_DIR)
        return 0

    yaml_files = sorted(FIXTURES_DIR.glob("*.yml")) + sorted(FIXTURES_DIR.glob("*.yaml"))
    if not yaml_files:
        logger.info("No YAML fixtures found in %s", FIXTURES_DIR)
        return 0

    inserted = 0
    for path in yaml_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)

            if not isinstance(raw, dict):
                logger.warning("Skipping %s — top-level YAML must be a mapping.", path.name)
                continue

            template_id = raw.get("template_id")
            if not template_id:
                logger.warning("Skipping %s — missing 'template_id' at top level.", path.name)
                continue

            if repository.exists(template_id, include_deleted=True):
                logger.info("Template '%s' already exists — skipping.", template_id)
                continue

            now = datetime.now(timezone.utc)
            template = Template(
                template_id=template_id,
                draft=BlueprintDraft(**raw["draft"]),
                placeholders=PlaceholderMeta(**raw.get("placeholders", {})),
                metadata=TemplateMetadata(**raw.get("metadata", {})),
                created_at=now,
                updated_at=now,
            )

            repository.save(template)
            inserted += 1
            logger.info("Seeded template '%s' from %s", template_id, path.name)

        except Exception:
            logger.exception("Failed to seed template from %s", path.name)

    logger.info("Template seeding complete: %d inserted, %d skipped.",
                inserted, len(yaml_files) - inserted)
    return inserted
