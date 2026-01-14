from typing import ClassVar
from pydantic import RootModel, model_serializer, SerializerFunctionWrapHandler, SerializationInfo
from core.enums import ResourceCategory


class Ref(RootModel[str]):
    """
    Base class for resource references.
    
    A wrapper around a single string that may be:
      - a bare ID, e.g. "abcd-1234"
      - an external ref, e.g. "$ref:abcd-1234"

    All subclasses MUST define _category to specify which resource
    category they reference. This is enforced at class definition time.
    """
    REF_PREFIX: ClassVar[str] = "$ref:"
    _category: ClassVar[ResourceCategory]

    def __init_subclass__(cls, **kwargs):
        """Enforce that all Ref subclasses define _category."""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '_category') or cls._category is None:
            raise TypeError(
                f"Ref subclass '{cls.__name__}' must define '_category'. "
                f"Example: _category: ClassVar[ResourceCategory] = ResourceCategory.YOUR_CATEGORY"
            )

    @property
    def ref(self) -> str:
        """The ID without the $ref: prefix."""
        raw = self.root
        if raw.startswith(self.REF_PREFIX):
            return raw[len(self.REF_PREFIX):]
        return raw

    def is_external_ref(self) -> bool:
        return self.root.startswith(self.REF_PREFIX)

    def is_inline(self) -> bool:
        return not self.is_external_ref()

    def get_category(self) -> ResourceCategory:
        """Get the resource category this ref points to."""
        return self._category

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> str:
        """
        For 'json' output: return raw self.root (preserve $ref:)
        For 'python' output: return self.ref (strip $ref:)
        """
        if info.mode == "json":
            return self.root
        return self.ref


class LLMRef(Ref):
    """Reference to an LLM resource."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.LLM

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.LLM.value,
            "description": "Reference to an LLM resource",
            "examples": ["$ref:gpt-4-turbo", "openai-gpt4"]
        }
    }


class NodeRef(Ref):
    """Reference to a Node resource."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.NODE

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.NODE.value,
            "description": "Reference to a Node resource",
            "examples": ["$ref:custom-agent-1", "data-processor"]
        }
    }


class RetrieverRef(Ref):
    """Reference to a Retriever resource."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.RETRIEVER

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.RETRIEVER.value,
            "description": "Reference to a Retriever resource",
            "examples": ["$ref:docs-retriever", "slack-search"]
        }
    }


class ToolRef(Ref):
    """Reference to a Tool resource."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.TOOL

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.TOOL.value,
            "description": "Reference to a Tool resource",
            "examples": ["$ref:jira-tool", "slack-messenger"]
        }
    }


class ProviderRef(Ref):
    """Reference to a Provider resource."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.PROVIDER

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.PROVIDER.value,
            "description": "Reference to a Provider resource",
            "examples": ["$ref:mcp-server", "api-provider"]
        }
    }


class ConditionRef(Ref):
    """Reference to a Condition resource."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.CONDITION.value,
            "description": "Reference to a Condition resource",
            "examples": ["$ref:threshold-check", "route-condition"]
        }
    }
