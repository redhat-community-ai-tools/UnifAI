"""Source-type-agnostic search: /api/sources/query.match?sourceType=CONFLUENCE.

The document and Slack endpoints each search one collection; this one searches the
collection of any registered source type with the same access rules (own sources plus
shared sources of the caller's groups) and the same response shape.
"""
import logging

from flask import Blueprint, g, jsonify
from global_utils.helpers.apiargs import from_query
from webargs import fields

from bootstrap.app_container import retrieval_service
from config.app_config import AppConfig
from infrastructure.http.auth import rag_require_session
from infrastructure.http.bearer_auth import rag_require_bearer
from infrastructure.http.caller_groups import caller_groups

logger = logging.getLogger(__name__)

sources_bp = Blueprint("sources", __name__)

SEARCHABLE_SOURCE_TYPES = frozenset({"DOCUMENT", "SLACK", "CONFLUENCE", "WEB"})


@sources_bp.route("/query.match", methods=["GET"])
@rag_require_session
@from_query({
    "query": fields.Str(required=True),
    "source_type": fields.Str(required=True, data_key="sourceType"),
    "top_k_results": fields.Int(required=False, load_default=15),
    "doc_ids": fields.List(fields.Str(), required=False, load_default=None, data_key="docIds"),
    "tags": fields.List(fields.Str(), required=False, load_default=None),
})
def query_match(query, source_type, top_k_results, doc_ids, tags):
    kind = (source_type or "").upper()
    if kind not in SEARCHABLE_SOURCE_TYPES:
        return jsonify({"error": f"unknown sourceType {source_type!r}"}), 400
    try:
        cfg = AppConfig.get_instance()
        results = retrieval_service(kind).search(
            query=query,
            limit=top_k_results,
            owner_id=g.user_id,
            caller_groups=caller_groups(cfg.oidc_issuer_url, cfg.oidc_verify_tls),
            doc_ids=doc_ids,
            tags=tags,
        )
        return jsonify({"matches": results}), 200
    except Exception as e:  # noqa: BLE001 - same contract as /api/docs/query.match
        logger.error(f"Failed to query {kind} sources: {e}")
        return jsonify({"error": str(e)}), 500


@sources_bp.route("/query.bearer", methods=["GET"])
@rag_require_bearer
@from_query({
    "query": fields.Str(required=True),
    "source_type": fields.Str(required=True, data_key="sourceType"),
    "top_k_results": fields.Int(required=False, load_default=15),
    "doc_ids": fields.List(fields.Str(), required=False, load_default=None, data_key="docIds"),
    "tags": fields.List(fields.Str(), required=False, load_default=None),
})
def query_bearer(query, source_type, top_k_results, doc_ids, tags):
    """Same search and access rules as /query.match for a caller that holds only the user's token (no session,
    no internal secret): the user and the groups come from the verified token."""
    kind = (source_type or "").upper()
    if kind not in SEARCHABLE_SOURCE_TYPES:
        return jsonify({"error": f"unknown sourceType {source_type!r}"}), 400
    try:
        results = retrieval_service(kind).search(
            query=query,
            limit=top_k_results,
            owner_id=g.user_id,
            caller_groups=g.bearer_groups,
            doc_ids=doc_ids,
            tags=tags,
        )
        return jsonify({"matches": results}), 200
    except Exception as e:  # noqa: BLE001 - same contract as /query.match
        logger.error(f"Failed to query {kind} sources: {e}")
        return jsonify({"error": str(e)}), 500
