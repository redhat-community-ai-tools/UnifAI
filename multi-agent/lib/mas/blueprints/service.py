import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from mas.blueprints.models.blueprint import BlueprintSpec, BlueprintDraft, BlueprintDocument, BlueprintSummary
from mas.blueprints.repository.repository import BlueprintRepository
from mas.blueprints.resolver import BlueprintResolver, check_inline_entries
from mas.blueprints.collector import BlueprintConfigCollector
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    BlueprintAccessDeniedError,
    BlueprintSaveError,
    BlueprintDuplicateNameError,
    BlueprintMetadataError,
    InvalidMetadataKeysError,
    PromptShortcutsValidationError,
)
from mas.blueprints.models.prompt_shortcuts import PromptShortcuts
from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
from mas.core.ref import RefWalker
from mas.elements.common.card import ElementCard
from mas.elements.common.validator import ValidationContext, ElementValidationResult
from mas.catalog.card_service import ElementCardService
from mas.validation.models import BlueprintValidationResult
from mas.validation.service import ElementValidationService

logger = logging.getLogger(__name__)

_VALID_METADATA_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


# Metadata keys that API clients may set; everything else is server-managed.
CLIENT_SETTABLE_METADATA_KEYS = frozenset({"usageScope", "display"})
_USAGE_SCOPES = frozenset({"public", "private"})

# Descriptive sheet of a blueprint (public fields only). Anything else is refused, so a prompt, a tool list or
# an access group can never be stored here by accident.
DISPLAY_TEXT_FIELDS = {
    "agent": 100, "title": 200, "description": 2000, "displayName": 100, "tileDescription": 300, "maintainer": 200,
    "state": 40, "classification": 40,
}
_DISPLAY_TASK_FIELDS = {"name": 100, "title": 200}
_DISPLAY_ICON = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_DISPLAY_COLOR = re.compile(r"^(#[0-9a-fA-F]{6}|[a-zA-Z]{3,30})$")
_RAW_HTML = re.compile(r"<\s*[a-zA-Z/!]")
_DISPLAY_MAX_TASKS = 20


def _display_text(field: str, value: Any, limit: int) -> None:
    if not isinstance(value, str) or len(value) > limit or _RAW_HTML.search(value):
        raise InvalidMetadataKeysError([f"display.{field}"])


def validate_display(display: Any) -> None:
    """Check a descriptive sheet: known fields only, bounded plain text (no raw HTML), icon and color from
    allowlisted shapes, a bounded task list."""
    if not isinstance(display, dict):
        raise InvalidMetadataKeysError(["display"])
    allowed = set(DISPLAY_TEXT_FIELDS) | {"icon", "color", "tasks"}
    unknown = [f"display.{k}" for k in display if k not in allowed]
    if unknown:
        raise InvalidMetadataKeysError(unknown)
    for field, limit in DISPLAY_TEXT_FIELDS.items():
        if field in display:
            _display_text(field, display[field], limit)
    if "icon" in display and not (isinstance(display["icon"], str) and _DISPLAY_ICON.match(display["icon"])):
        raise InvalidMetadataKeysError(["display.icon"])
    if "color" in display and not (isinstance(display["color"], str) and _DISPLAY_COLOR.match(display["color"])):
        raise InvalidMetadataKeysError(["display.color"])
    tasks = display.get("tasks", [])
    if not isinstance(tasks, list) or len(tasks) > _DISPLAY_MAX_TASKS:
        raise InvalidMetadataKeysError(["display.tasks"])
    for task in tasks:
        if not isinstance(task, dict):
            raise InvalidMetadataKeysError(["display.tasks"])
        extra = [f"display.tasks.{k}" for k in task if k not in _DISPLAY_TASK_FIELDS]
        if extra:
            raise InvalidMetadataKeysError(extra)
        for field, limit in _DISPLAY_TASK_FIELDS.items():
            if field in task:
                _display_text(f"tasks.{field}", task[field], limit)
PUBLIC_VIEW_MAX_SHORTCUTS = 3


def validate_client_metadata(metadata: Dict[str, Any]) -> None:
    """Restrict client-supplied metadata to the allowed keys and values."""
    validate_metadata_keys(metadata)
    unknown = [k for k in metadata if k not in CLIENT_SETTABLE_METADATA_KEYS]
    if unknown:
        raise InvalidMetadataKeysError(unknown)
    scope = metadata.get("usageScope")
    if "usageScope" in metadata and scope not in _USAGE_SCOPES:
        raise InvalidMetadataKeysError(["usageScope"])
    if "display" in metadata:
        validate_display(metadata["display"])


def validate_metadata_keys(metadata: Dict[str, Any]) -> None:
    """Reject metadata keys that would corrupt Mongo dot-notation paths or clash with operators."""
    bad = [k for k in metadata if not _VALID_METADATA_KEY.match(k)]
    if bad:
        logger.info("Rejected metadata keys: %s", bad)
        raise InvalidMetadataKeysError(bad)


class BlueprintService:
    def __init__(
        self,
        repo: BlueprintRepository,
        resolver: BlueprintResolver,
        validation_service: ElementValidationService = None,
        card_service: ElementCardService = None,
        auth_service=None,
    ):
        self._repo = repo
        self._resolver = resolver
        self._validation_service = validation_service
        self._card_service = card_service
        self._auth_service = auth_service
        self._config_collector = BlueprintConfigCollector()

    # ────────── Write ──────────
    def save_draft(self, *, identity: Identity, draft_dict: dict,
                   metadata: Optional[Dict[str, Any]] = None,
                   skip_name_check: bool = False) -> str:
        if metadata:
            validate_metadata_keys(metadata)
        draft_bp = BlueprintDraft(**draft_dict)
        check_inline_entries(draft_bp)
        if not skip_name_check and self._repo.name_exists_for_identity(identity, draft_bp.name):
            raise BlueprintDuplicateNameError(draft_bp.name)
        rid_refs = list(RefWalker.external_rids(draft_bp))
        return self._repo.save(identity=identity, spec=draft_bp,
                               rid_refs=rid_refs, metadata=metadata or {})

    # ────────── Single-blueprint reads (ID is globally unique) ──────────
    def load_draft(self, blueprint_id: str) -> BlueprintDraft:
        doc = self._repo.load(blueprint_id)
        return BlueprintDraft.from_stored_dict(doc.spec_dict)

    def get_blueprint_draft_doc(self, blueprint_id: str) -> BlueprintDocument:
        """Get blueprint document with metadata for sharing operations."""
        return self._repo.load(blueprint_id)

    def update_draft(self, *, blueprint_id: str, draft_dict: dict,
                     identity: Identity) -> bool:
        try:
            doc = self._repo.load(blueprint_id)
        except KeyError as exc:
            raise BlueprintNotFoundError(blueprint_id) from exc
        if doc.identity.type != identity.type or doc.identity.id != identity.id:
            raise BlueprintAccessDeniedError(blueprint_id, identity.id)

        if "prompt_shortcuts" not in draft_dict:
            existing = PromptShortcuts.from_spec(doc.spec_dict)
            if not existing.is_empty:
                draft_dict = {**draft_dict, "prompt_shortcuts": existing.to_storage()}

        draft = BlueprintDraft(**draft_dict)
        check_inline_entries(draft)
        new_name = draft.name
        old_name = doc.spec_dict.get("name")
        if new_name != old_name and self._repo.name_exists_for_identity(
            identity, new_name, exclude_blueprint_id=blueprint_id,
        ):
            raise BlueprintDuplicateNameError(new_name)

        rid_refs = list(RefWalker.external_rids(draft))
        return self._repo.update(
            blueprint_id=blueprint_id, spec=draft, rid_refs=rid_refs,
        )

    def load_resolved(
        self, blueprint_id: str, caller: CallerScope = CallerScope(),
    ) -> BlueprintSpec:
        """Resolve a saved blueprint's refs into an executable spec.

        ``caller.identity`` should be the session/caller owner so built-in
        resources resolve with that identity's ``builtin_user_configs``
        overlay applied. Without it, built-ins resolve to their raw
        defaults.
        """
        return self._resolver.resolve(self.load_draft(blueprint_id), caller=caller)

    def load_resolved_tolerant(
        self, blueprint_id: str, caller: CallerScope = CallerScope(),
    ) -> Tuple[BlueprintSpec, Dict[str, str]]:
        """Like ``load_resolved``, but reports broken external refs instead of raising.

        Used by validation, where a stale/deleted referenced resource should
        show up as a failing element rather than crash the whole request.
        """
        return self._resolver.resolve_tolerant(self.load_draft(blueprint_id), caller=caller)

    def load_draft_from_dict(self, draft_dict: dict) -> BlueprintDraft:
        """Load a BlueprintDraft from a dictionary without saving to database.

        Used for re-hydrating an already-*stored* ``spec_dict`` (e.g. sharing/
        cloning an existing blueprint), so — like ``load_draft`` — it tolerates
        legacy fields no longer in the schema rather than rejecting them.
        """
        return BlueprintDraft.from_stored_dict(draft_dict)

    def resolve_draft_dict(
        self, draft_dict: dict, caller: CallerScope = CallerScope(),
    ) -> BlueprintSpec:
        """Resolve a draft dictionary directly to BlueprintSpec without saving to database."""
        return self._resolver.resolve(BlueprintDraft(**draft_dict), caller=caller)

    def to_dict(self, blueprint_id: str) -> Dict[str, Any]:
        """Draft -> JSON-serialisable dict (no meta)."""
        return self.load_draft(blueprint_id).model_dump(mode="json")

    def exists(self, blueprint_id: str) -> bool:
        return self._repo.exists(blueprint_id)

    def name_exists_for_identity(
        self, identity: Identity, name: str,
        *, exclude_blueprint_id: str | None = None,
    ) -> bool:
        return self._repo.name_exists_for_identity(
            identity, name, exclude_blueprint_id=exclude_blueprint_id,
        )

    def delete(self, blueprint_id: str) -> bool:
        return self._repo.delete(blueprint_id)

    # ────────── Object-level access ──────────
    @staticmethod
    def _is_owner(doc: BlueprintDocument, identity: Identity) -> bool:
        return doc.identity.type == identity.type and doc.identity.id == identity.id

    @staticmethod
    def _is_public(doc: BlueprintDocument) -> bool:
        return (doc.metadata or {}).get("usageScope") == "public"

    def get_accessible_doc(
        self, blueprint_id: str, identity: Identity, *, allow_public: bool = False,
    ) -> BlueprintDocument:
        """Load a blueprint the caller may use.

        Access is granted to the owning identity (user or team) and, when
        ``allow_public`` is set, to anyone for a blueprint whose usageScope is
        public. Raises ``BlueprintAccessDeniedError`` otherwise and
        ``BlueprintNotFoundError`` when the blueprint does not exist.
        """
        try:
            doc = self._repo.load(blueprint_id)
        except KeyError as exc:
            raise BlueprintNotFoundError(blueprint_id) from exc
        if self._is_owner(doc, identity):
            return doc
        if allow_public and self._is_public(doc):
            return doc
        raise BlueprintAccessDeniedError(blueprint_id, identity.id)

    def get_info_for(self, blueprint_id: str, identity: Identity) -> Dict[str, Any]:
        """Blueprint info for the caller: full document for the owner,
        a minimal view (name, shortcuts, scope) for a public blueprint."""
        doc = self.get_accessible_doc(blueprint_id, identity, allow_public=True)
        if self._is_owner(doc, identity):
            return doc.model_dump(mode="json")
        spec = doc.spec_dict or {}
        shortcuts = spec.get("prompt_shortcuts") or []
        return {
            "blueprint_id": doc.blueprint_id,
            "user_id": doc.identity.id if doc.identity.is_user else "",
            "spec_dict": {
                "name": spec.get("name", ""),
                "prompt_shortcuts": shortcuts[:PUBLIC_VIEW_MAX_SHORTCUTS],
            },
            "metadata": {"usageScope": "public"},
        }

    def delete_owned(self, blueprint_id: str, identity: Identity) -> bool:
        """Delete a blueprint owned by ``identity``."""
        self.get_accessible_doc(blueprint_id, identity)
        return self._repo.delete(blueprint_id)

    def load_many(self, blueprint_ids: List[str]) -> List[BlueprintDocument]:
        """Load multiple blueprint documents by their IDs in a single operation."""
        return self._repo.load_many(blueprint_ids)

    # ────────── Bulk listing / counting (optionally per identity) ──────────
    def list_ids(self, *, identity: Optional[Identity] = None, **pg) -> List[str]:
        return self._repo.list_ids(identity=identity, **pg)

    def list_summaries(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[BlueprintSummary]:
        """Return lightweight blueprint summaries (no full spec)."""
        return self._repo.list_summaries(identity=identity, **pg)

    def list_draft_dicts(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[Dict[str, Any]]:
        """
        Return pure-dict drafts (as saved) in one DB round-trip.
        """
        docs = self._repo.list_docs(identity=identity, **pg)
        return [doc.spec_dict for doc in docs]

    def list_draft_docs(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[BlueprintDocument]:
        """
        Return blueprint documents (as saved) in one DB round-trip.
        """
        return self._repo.list_docs(identity=identity, **pg)

    def _resolve_doc(
        self, doc: BlueprintDocument, caller: CallerScope = CallerScope(),
    ) -> BlueprintDocument:
        """Resolve a single document's spec_dict from draft to fully resolved form.

        Uses tolerant resolution — same rationale as ``validate_blueprint``:
        a stale/deleted referenced resource shouldn't make the whole document
        unviewable. The broken ref is simply left out of the resolved spec's
        resource lists (the referencing element's own config still carries
        the dangling ``$ref:...``, which is exactly how ``blueprint.validate``
        surfaces it as a failing/unvalidated element); only logged here.
        """
        draft = BlueprintDraft.from_stored_dict(doc.spec_dict)
        spec, broken_refs = self._resolver.resolve_tolerant(draft, caller=caller)
        if broken_refs:
            logger.warning(
                "Blueprint '%s' has broken resource ref(s), resolved with gaps — %s",
                doc.blueprint_id, broken_refs,
            )
        resolved_dict = spec.model_dump(mode="json")
        shortcuts = draft.model_dump(mode="json").get("prompt_shortcuts")
        if shortcuts is not None:
            resolved_dict["prompt_shortcuts"] = shortcuts
        return doc.model_copy(update={"spec_dict": resolved_dict})

    def list_resolved_docs(
            self, *, caller: CallerScope = CallerScope(), **pg
    ) -> List[BlueprintDocument]:
        """
        Return documents with resolved spec_dict instead of draft spec_dict.

        ``caller.identity`` is used both to scope the listing (via the
        repository) and to resolve each document's built-in overlays.
        """
        docs = self._repo.list_docs(identity=caller.identity, **pg)
        resolved_docs = []

        for doc in docs:
            try:
                resolved_docs.append(self._resolve_doc(doc, caller=caller))
            except (KeyError, ValidationError) as e:
                logger.warning(
                    "Skipping blueprint '%s': resolution failed — %s",
                    doc.blueprint_id, e,
                )
                continue

        return resolved_docs

    def get_resolved_doc(
        self, blueprint_id: str, caller: CallerScope = CallerScope(),
    ) -> BlueprintDocument:
        """
        Return a single document with its spec_dict resolved.

        Raises:
            BlueprintNotFoundError: If the blueprint does not exist.

        Note: refs to resources that no longer exist (or, for a non-admin
        caller, a draft built-in) do NOT raise — see
        ``_resolve_doc``/``resolve_tolerant``. The document still resolves;
        the reference is simply omitted from the resolved spec's resource
        lists rather than the dangling ``$ref:...`` being left in place.
        """
        if not self.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)
        try:
            doc = self._repo.load(blueprint_id)
        except KeyError as exc:
            raise BlueprintNotFoundError(blueprint_id) from exc
        return self._resolve_doc(doc, caller=caller)

    def count(self, *, identity: Optional[Identity] = None) -> int:
        return self._repo.count(identity=identity)

    @staticmethod
    def get_draft_schema() -> Dict[str, Any]:
        """
        Return the JSON schema of the BlueprintDraft model.
        """
        return BlueprintDraft.model_json_schema()

    # ────────── Prompt Shortcuts ──────────
    def set_prompt_shortcuts(self, blueprint_id: str, prompts: list[dict],
                             *, identity: Identity) -> PromptShortcuts:
        try:
            doc = self._repo.load(blueprint_id)
        except KeyError as exc:
            raise BlueprintNotFoundError(blueprint_id) from exc
        if doc.identity.type != identity.type or doc.identity.id != identity.id:
            raise BlueprintAccessDeniedError(blueprint_id, identity.id)
        try:
            shortcuts = PromptShortcuts.parse(prompts)
        except PromptShortcutsValidationError as exc:
            raise PromptShortcutsValidationError(
                exc.message, blueprint_id=blueprint_id,
            ) from exc
        if not self._repo.set_prompt_shortcuts(blueprint_id=blueprint_id, shortcuts=shortcuts):
            raise BlueprintNotFoundError(blueprint_id)
        return shortcuts

    def get_prompt_shortcuts(self, blueprint_id: str, *, identity: Identity) -> PromptShortcuts:
        try:
            doc = self._repo.load(blueprint_id)
        except KeyError as exc:
            raise BlueprintNotFoundError(blueprint_id) from exc
        if doc.identity.type != identity.type or doc.identity.id != identity.id:
            raise BlueprintAccessDeniedError(blueprint_id, identity.id)
        return PromptShortcuts.from_spec(doc.spec_dict)

    # ────────── Blueprint Metadata ──────────
    def set_metadata_owned(
        self, blueprint_id: str, metadata: Dict[str, Any], identity: Identity,
    ) -> bool:
        """Set client-settable metadata keys on a blueprint owned by ``identity``."""
        validate_client_metadata(metadata)
        self.get_accessible_doc(blueprint_id, identity)
        return self.set_metadata(blueprint_id, metadata)

    def set_metadata(self, blueprint_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Merge keys into a blueprint's metadata (key-level upsert, not full replace).
        """
        validate_metadata_keys(metadata)
        if not self.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)

        try:
            return self._repo.set_metadata(blueprint_id=blueprint_id, metadata=metadata)
        except Exception as e:
            raise BlueprintMetadataError(blueprint_id, f"Failed to update metadata: {str(e)}")

    # ────────── Validation ──────────
    def validate_blueprint(
        self,
        blueprint_id: str,
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> BlueprintValidationResult:
        """
        Validate all elements in a saved blueprint.
        
        Args:
            blueprint_id: Blueprint ID to validate
            caller: Caller identity/admin status, used to resolve built-in overlays
            user_id: Logged-in user (for auth-aware validators)
            timeout_seconds: Timeout for network checks
            
        Returns:
            BlueprintValidationResult with all element results
            
        Raises:
            RuntimeError: If validation service not configured
            KeyError: If the blueprint itself does not exist

        Note: refs to resources that no longer exist do NOT raise — they
        show up as failing elements in the returned result instead.
        """
        self._ensure_validation_service()
        spec, broken_refs = self.load_resolved_tolerant(blueprint_id, caller=caller)
        return self._validate_spec(
            spec, blueprint_id, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
            broken_refs=broken_refs,
        )

    def validate_draft(
        self,
        draft_dict: dict,
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> BlueprintValidationResult:
        """
        Validate a blueprint draft before saving.

        This validates a blueprint YAML/JSON without requiring it to be saved first.
        Useful for UI validation before creating a blueprint.
        """
        self._ensure_validation_service()
        draft = BlueprintDraft(**draft_dict)
        spec, broken_refs = self._resolver.resolve_tolerant(draft, caller=caller)
        return self._validate_spec(
            spec, "draft", timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
            broken_refs=broken_refs,
        )

    # ────────── Card Building ──────────
    def get_blueprint_cards(
        self,
        blueprint_id: str,
        caller: CallerScope = CallerScope(),
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for all elements in a saved blueprint.
        """
        self._ensure_card_service()
        spec = self.load_resolved(blueprint_id, caller=caller)
        return self._build_cards_from_spec(spec)

    def get_draft_cards(
        self,
        draft_dict: dict,
        caller: CallerScope = CallerScope(),
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for a blueprint draft.
        """
        self._ensure_card_service()
        spec = self.resolve_draft_dict(draft_dict, caller=caller)
        return self._build_cards_from_spec(spec)

    # ────────── Helpers ──────────
    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if self._validation_service is None:
            raise RuntimeError("ValidationService not configured")

    def _ensure_card_service(self) -> None:
        """Raise if card service not configured."""
        if self._card_service is None:
            raise RuntimeError("CardService not configured")

    def _validate_spec(
        self,
        spec: BlueprintSpec,
        blueprint_id: str,
        timeout_seconds: float,
        user_id: str = "",
        credential_user_id: str = "",
        broken_refs: Optional[Dict[str, str]] = None,
    ) -> BlueprintValidationResult:
        """Collect configs from spec, validate, and build result.

        ``broken_refs`` (rid -> reason) are refs that couldn't be resolved;
        each is reported as its own failing element result.
        """
        configs = self._config_collector.collect(spec)
        context = ValidationContext(
            timeout_seconds=timeout_seconds,
            user_id=user_id,
            credential_user_id=credential_user_id,
            auth_service=self._auth_service,
        )
        results = self._validation_service.validate_ordered(configs, context)
        for rid, reason in (broken_refs or {}).items():
            results[rid] = ElementValidationResult.create_error(rid=rid, error=reason)
        return BlueprintValidationResult(
            blueprint_id=blueprint_id,
            is_valid=all(r.is_valid for r in results.values()),
            element_results=results,
        )

    def _build_cards_from_spec(
        self,
        spec: BlueprintSpec,
    ) -> Dict[str, ElementCard]:
        """Collect configs from spec and build cards."""
        configs = self._config_collector.collect(spec)
        return self._card_service.build_all_cards(configs)
