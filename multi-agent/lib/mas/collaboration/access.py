"""Session access rule shared by the collaboration service and the HTTP layer."""
from mas.core.identity import IdentityType
from mas.core.identity.ports import IdentityProvider
from mas.session.domain.session_record import SessionRecord
from mas.session.repository.repository import SessionRepository


def check_session_access(
    session_repo: SessionRepository,
    identity_provider: IdentityProvider,
    user_id: str,
    session_id: str,
) -> SessionRecord:
    """Verify the user owns (or is a team member of) the session.

    Returns the session record on success.
    Raises ``KeyError`` if the session does not exist.
    Raises ``PermissionError`` if the user does not have access.
    """
    record = session_repo.fetch(session_id)
    if record.identity.type == IdentityType.TEAM:
        if not identity_provider.is_member(user_id, record.identity.id):
            raise PermissionError("Access denied")
    elif user_id.casefold() != record.identity.id.casefold():
        raise PermissionError("Access denied")
    return record
