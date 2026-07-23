class ResourceInUseError(RuntimeError):
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

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class BuiltInWriteProtectedError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Built-in system resources cannot be modified or deleted."
        )

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class ResourceAccessDeniedError(RuntimeError):
    """Raised when a caller tries to mutate a resource owned by a different identity."""

    def __init__(self, rid: str) -> None:
        self.rid = rid
        super().__init__(
            f"You do not have permission to modify resource '{rid}'."
        )

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class BuiltinDependentsPublicError(RuntimeError):
    """Raised when demoting a built-in would strand a public built-in that
    still references it (e.g. an "available to all" agent using an LLM,
    provider, or tool that would suddenly become invisible to end users).
    """

    def __init__(self, *, resource_name: str, category: str, dependents: list) -> None:
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

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class BuiltinConfigUnavailableError(RuntimeError):
    """Raised when a built-in overlay write is attempted without a configured repo."""

    def __init__(self) -> None:
        super().__init__(
            "Built-in user configuration storage is not available."
        )

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()
