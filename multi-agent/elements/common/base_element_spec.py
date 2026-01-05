from abc import ABC
from typing import (
    ClassVar,
    List,
    Optional,
    Type,
    get_origin,
    get_args,
    Union,
    Set,
    Dict,
    Any,
)
from pydantic import BaseModel
from core.enums import ResourceCategory
from elements.common.base_factory import BaseFactory
from elements.common.validator import ElementValidator
from graph.state.graph_state import Channel


class BaseElementSpec(ABC):
    """
    Static compile‑time contract for every element spec.
    Subclasses must fill in all *required* ClassVars; optional ones
    can be omitted or overwritten.
    """

    # ── required metadata ────────────────────────────────────────────────
    category: ClassVar[ResourceCategory]
    type_key: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    config_schema: ClassVar[Type[BaseModel]]
    factory_cls: ClassVar[Type[BaseFactory]]
    dependencies: ClassVar[List[ResourceCategory]] = []
    reads: ClassVar[Set[Channel]] = set()
    writes: ClassVar[Set[Channel]] = set()
    # ── optional metadata ------------------------------------------------
    version: ClassVar[str] = "1.0.0"
    tags: ClassVar[List[str]] = []
    hints: ClassVar[List[Any]] = []
    
    # ── optional validator ------------------------------------------------
    validator_cls: ClassVar[Optional[Type[ElementValidator]]] = None

    # ─────────────────────────────────────────────────────────────────────
    # compile‑time validation
    # ─────────────────────────────────────────────────────────────────────
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        missing = [
            name
            for name in cls._collect_required_attrs()
            if getattr(cls, name, None) is None
        ]
        if missing:
            raise TypeError(
                f"{cls.__name__} is missing required spec attributes: {missing}"
            )

    # ─────────────────────────────────────────────────────────────────────
    # helper lives *inside* the class
    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def _collect_required_attrs(cls) -> set[str]:
        """
        Return names of every attribute declared on *BaseElementSpec* that is
        required (i.e. no default value and not annotated as Optional[...]).

        We intentionally inspect `BaseElementSpec` (the contract) rather than
        `cls` (the concrete subclass) so the rule set is stable.
        """
        base = BaseElementSpec  # alias for readability
        required: set[str] = set()

        for name, anno in base.__annotations__.items():
            # Default provided → optional
            if name in base.__dict__:
                continue

            # Optional[...] or Union[..., None] → optional
            origin = get_origin(anno)
            if origin is Union and type(None) in get_args(anno):
                continue

            required.add(name)

        return required

    # ─────────────────────────────────────────────────────────────────────
    # nice repr for debugging
    # ─────────────────────────────────────────────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"{self.__class__.__name__}"
            f"(category={self.category.name}, type_key='{self.type_key}')"
        )
