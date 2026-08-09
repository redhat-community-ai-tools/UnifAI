from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from mas.resources.models import Resource


class ResourceError(RuntimeError):
    """Shared base for resource-domain errors.

    Provides the ``__str__``/``__repr__`` implementations that every
    subclass used to duplicate: ``str()`` returns the message stored by
    ``super().__init__(msg)``, and ``repr()`` mirrors ``str()`` for
    log-friendliness.
    """

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class ResourceInUseError(ResourceError):
    def __init__(self, *, by_blueprints: list[str], by_resources: list[str]):
        self.by_blueprints = by_blueprints
        self.by_resources = by_resources

        parts = []
        if by_blueprints:
            parts.append(f"blueprints={', '.join(by_blueprints)}")
        if by_resources:
            parts.append(f"resources={', '.join(by_resources)}")

        msg = "Resource still in use"
        if parts:
            msg += " by " + " and ".join(parts)

        super().__init__(msg)


class BuiltInWriteProtectedError(ResourceError):
    """Raised when a caller attempts to modify or delete a built-in system resource."""

    def __init__(self) -> None:
        super().__init__(
            "Built-in system resources cannot be modified or deleted."
        )


class ResourceAccessDeniedError(ResourceError):
    """Raised when a caller tries to mutate a resource owned by a different identity."""

    def __init__(self, rid: str) -> None:
        self.rid = rid
        super().__init__(
            f"You do not have permission to modify resource '{rid}'."
        )


class BuiltinDependentsPublicError(ResourceError):
    """Raised when demoting a built-in would strand a public built-in that
    still references it (e.g. an "available to all" agent using an LLM,
    provider, or tool that would suddenly become invisible to end users).
    """

    def __init__(self, *, resource_name: str, category: str, dependents: List["Resource"]) -> None:
        self.resource_name = resource_name
        self.category = category
        self.dependents = dependents

        names = ", ".join(f"'{d.name}'" for d in dependents)
        singular_category = category[:-1] if category.endswith("s") else category

        super().__init__(
            f"To make '{resource_name}' unavailable to all, the following "
            f"resources that use it must be made unavailable to all as well: "
            f"{names}. Alternatively, change the {singular_category} used by "
            f"those resources."
        )


class ResourceLockedError(ResourceError):
    """Raised when a mutation targets a built-in resource whose admin edit
    lock is currently held by a different admin."""

    def __init__(self, locked_by_user_id: str, locked_by_display_name: str = "") -> None:
        self.locked_by_user_id = locked_by_user_id
        self.locked_by_display_name = locked_by_display_name or locked_by_user_id
        super().__init__(
            f"Resource is currently locked for editing by {self.locked_by_display_name}."
        )


class BuiltinConfigUnavailableError(ResourceError):
    """Raised when a built-in overlay write is attempted without a configured repo."""

    def __init__(self) -> None:
        super().__init__(
            "Built-in user configuration storage is not available."
        )
