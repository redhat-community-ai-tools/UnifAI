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
    def __init__(self):
        super().__init__(
            "Built-in system resources cannot be modified or deleted."
        )

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class ResourceAccessDeniedError(RuntimeError):
    """Raised when a caller tries to mutate a resource owned by a different identity."""

    def __init__(self, rid: str):
        self.rid = rid
        super().__init__(
            f"You do not have permission to modify resource '{rid}'."
        )

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()


class BuiltinConfigUnavailableError(RuntimeError):
    """Raised when a built-in overlay write is attempted without a configured repo."""

    def __init__(self):
        super().__init__(
            "Built-in user configuration storage is not available."
        )

    def __str__(self) -> str:
        return self.args[0]

    def __repr__(self) -> str:
        return self.__str__()
