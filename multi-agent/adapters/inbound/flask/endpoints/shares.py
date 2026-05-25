import logging

from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.core.identity import IdentityType
from mas.sharing.models import ShareItemKind, ShareStatus
from mas.sharing.service import ShareService
from inbound.flask.decorators import (
    with_identity,
    with_authenticated_user,
)

logger = logging.getLogger(__name__)

shares_bp = Blueprint("shares", __name__)


@shares_bp.route("/share.create", methods=["POST"])
@with_authenticated_user
@from_body({
    "recipient_user_id": fields.Str(data_key="recipientUserId", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
    "message": fields.Str(required=False),
    "sender_type": fields.Str(data_key="senderType", required=False, load_default="user"),
    "sender_display_name": fields.Str(data_key="senderDisplayName", required=False),
    "sender_identity_id": fields.Str(data_key="senderIdentityId", required=False),
    "auto_accept": fields.Bool(data_key="autoAccept", required=False, load_default=False),
})
def create_share(
    authenticated_user,
    recipient_user_id,
    item_kind,
    item_id,
    message=None,
    sender_type="user",
    sender_display_name=None,
    sender_identity_id=None,
    auto_accept=False,
):
    """Create share invitation."""
    try:
        identity_provider = current_app.container.identity_provider
        sender_type_norm = str(sender_type or "user").strip().lower()
        claimed_owner = str(sender_identity_id or "").strip()
        if sender_type_norm == "team":
            if not claimed_owner:
                return jsonify(
                    {"error": "senderIdentityId (team id) is required when senderType is team"},
                ), 400
            if not identity_provider.is_member(authenticated_user, claimed_owner):
                return jsonify({"error": "Not authorized to share as this team"}), 403
            effective_sender_id = claimed_owner
        else:
            if claimed_owner and claimed_owner.casefold() != authenticated_user.casefold():
                return jsonify(
                    {"error": "senderIdentityId must match the authenticated user for personal shares"},
                ), 403
            effective_sender_id = authenticated_user

        # Validate item_kind
        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        recipient_raw = str(recipient_user_id).strip()

        directory = current_app.container.directory_provider
        if directory and recipient_raw.casefold() != authenticated_user.casefold():
            resolved = directory.get_user(recipient_raw)
            if not resolved:
                return jsonify({"error": f"Recipient '{recipient_raw}' not found in directory"}), 400

        # Auto-accept self-copy: persist recipient as the canonical auth header value so
        # accept_invite(..., recipient_user_id=X-Authenticated-User) always matches.
        recipient_effective = (
            authenticated_user
            if (auto_accept and recipient_raw.casefold() == authenticated_user.casefold())
            else recipient_raw
        )

        # For team shares the resource may be owned by either the user or the team.
        authorized_owner_ids = (
            {authenticated_user, effective_sender_id}
            if sender_type_norm == "team"
            else {effective_sender_id}
        )

        svc = current_app.container.share_service
        share_id = svc.create_invite(
            sender_user_id=effective_sender_id,
            recipient_user_id=recipient_effective,
            item_kind=kind,
            item_id=item_id,
            message=message,
            sender_type=sender_type,
            sender_display_name=sender_display_name,
            authorized_owner_ids=authorized_owner_ids,
        )

        response = {
            "status": "success",
            "share_id": share_id
        }
        if auto_accept:
            result = svc.accept_invite(share_id, recipient_user_id=recipient_effective)
            response["result"] = result.model_dump(mode="json")
            response["auto_accepted"] = True

        return jsonify(response), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.accept", methods=["POST"])
@with_authenticated_user
@from_body({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def accept_share(authenticated_user, share_id):
    """Accept share invitation."""
    try:
        svc = current_app.container.share_service
        result = svc.accept_invite(share_id, recipient_user_id=authenticated_user)

        return jsonify({
            "status": "success",
            "result": result.model_dump(mode="json")
        }), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.decline", methods=["POST"])
@with_authenticated_user
@from_body({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def decline_share(authenticated_user, share_id):
    """Decline share invitation."""
    try:
        svc = current_app.container.share_service
        svc.decline_invite(share_id, recipient_user_id=authenticated_user)

        return jsonify({"status": "success"}), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.to_team", methods=["POST"])
@with_authenticated_user
@from_body({
    "team_name": fields.Str(data_key="teamName", required=True),
    "item_kind": fields.Str(data_key="itemKind", required=True),
    "item_id": fields.Str(data_key="itemId", required=True),
    "sender_team_id": fields.Str(data_key="senderTeamId", required=False, load_default=None),
})
def share_to_team(authenticated_user, team_name, item_kind, item_id, sender_team_id=None):
    """Share item directly to a team workspace.

    When the resource is owned by a team (rather than the calling user personally),
    pass ``senderTeamId`` with the owning team's id. The caller must be a member of
    that team; the team id is then used as the effective sender so that ownership
    validation against the resource passes correctly.
    """
    try:
        identity_provider = current_app.container.identity_provider

        # Resolve the destination team and verify the caller is a member.
        dest_team_id = identity_provider.resolve_team_id(authenticated_user, team_name)
        if dest_team_id is None:
            return jsonify({"error": "Not authorized to share to this team"}), 403

        # Determine effective sender: team-owned resource or personal resource.
        if sender_team_id:
            sender_team_id = str(sender_team_id).strip()
            if not identity_provider.is_member(authenticated_user, sender_team_id):
                return jsonify({"error": "Not authorized to share as this team"}), 403
            effective_sender_id = sender_team_id
        else:
            effective_sender_id = authenticated_user

        try:
            kind = ShareItemKind(item_kind)
        except ValueError:
            return jsonify({"error": "Invalid itemKind. Must be 'resource' or 'blueprint'"}), 400

        # Build the full authorized ownership pool: includes the authenticated user
        # plus all teams they belong to.  When an explicit senderTeamId is provided
        # it is guaranteed to be in the pool (already validated above).  When it is
        # omitted we still auto-include every team the user is a member of so that
        # team-owned resources are shareable without requiring the caller to name
        # the source team explicitly.
        authorized_owner_ids = {authenticated_user}
        if sender_team_id:
            authorized_owner_ids.add(sender_team_id)
        elif identity_provider.requires_authentication:
            team_ids = identity_provider.get_team_ids(authenticated_user)
            if team_ids:
                authorized_owner_ids.update(team_ids)
            else:
                logger.warning(
                    "Could not fetch teams for %s during share_to_team; "
                    "ownership pool limited to the authenticated user",
                    authenticated_user,
                )

        svc = current_app.container.share_service
        result = svc.share_to_team(
            sender_user_id=effective_sender_id,
            team_name=dest_team_id,
            item_kind=kind,
            item_id=item_id,
            authorized_owner_ids=authorized_owner_ids,
        )

        return jsonify({
            "status": "success",
            "result": result.model_dump(mode="json")
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.cancel", methods=["POST"])
@with_authenticated_user
@from_body({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def cancel_share(authenticated_user, share_id):
    """Cancel share invitation."""
    try:
        svc = current_app.container.share_service
        svc.cancel_invite(share_id, sender_user_id=authenticated_user)

        return jsonify({"status": "success"}), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/shares.list", methods=["GET"])
@with_identity
@from_query({
    "direction": fields.Str(required=False, load_default="received"),
    "status": fields.Str(required=False),
    "skip": fields.Int(required=False, load_default=0),
    "limit": fields.Int(required=False, load_default=100),
})
def list_shares(identity, direction="received", status=None, skip=0, limit=100):
    """List share invitations."""
    try:
        status_enum = None
        if status:
            try:
                status_enum = ShareStatus(status)
            except ValueError:
                return jsonify({"error": "Invalid status"}), 400

        svc = current_app.container.share_service

        if direction == "received":
            invites = svc.list_received_invites(identity, status_enum, skip, limit)
        elif direction == "sent":
            invites = svc.list_sent_invites(identity, status_enum, skip, limit)
        else:
            return jsonify({"error": "Direction must be 'received' or 'sent'"}), 400

        def serialize_invite(invite):
            payload = invite.model_dump(mode="json")
            payload["sender_user_id"] = invite.sender_identity.id
            payload["sender_display_name"] = invite.sender_identity.display_name
            payload["recipient_user_id"] = invite.recipient_identity.id
            payload["recipient_display_name"] = invite.recipient_identity.display_name
            return payload

        return jsonify({
            "invites": [serialize_invite(invite) for invite in invites],
            "count": len(invites)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shares_bp.route("/share.get", methods=["GET"])
@with_authenticated_user
@from_query({
    "share_id": fields.Str(data_key="shareId", required=True),
})
def get_share(authenticated_user, share_id):
    """Get share invitation details."""
    try:
        svc = current_app.container.share_service
        invite = svc.get_invite(share_id)

        # Check authorization: sender (user or team member), or recipient
        identity_provider = current_app.container.identity_provider
        sender_ok = (
            invite.sender_identity.type == IdentityType.TEAM
            and identity_provider.is_member(authenticated_user, invite.sender_identity.id)
        ) or ShareService._principal_matches_identity(invite.sender_identity, authenticated_user)
        recipient_ok = ShareService._principal_matches_identity(
            invite.recipient_identity, authenticated_user
        )
        if not (sender_ok or recipient_ok):
            return jsonify({"error": "Not authorized to view this invitation"}), 403

        payload = invite.model_dump(mode="json")
        payload["sender_user_id"] = invite.sender_identity.id
        payload["sender_display_name"] = invite.sender_identity.display_name
        payload["recipient_user_id"] = invite.recipient_identity.id
        payload["recipient_display_name"] = invite.recipient_identity.display_name
        return jsonify(payload), 200

    except KeyError:
        return jsonify({"error": "Share invitation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
