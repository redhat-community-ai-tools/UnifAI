from typing import ClassVar, Dict, Type
from pydantic import RootModel, model_serializer, SerializerFunctionWrapHandler, SerializationInfo
from mas.core.enums import ResourceCategory


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

    @classmethod
    def external(cls, rid: str) -> "Ref":
        """
        Create an external reference to a saved resource.
        
        Example:
            NodeRef.external("abc123")  # → NodeRef("$ref:abc123")
        """
        return cls(f"{cls.REF_PREFIX}{rid}")
    
    def to_external(self, new_rid: str | None = None) -> "Ref":
        """
        Create external ref with same type.
        
        Args:
            new_rid: New resource ID. If None, uses current ref.
            
        Example:
            node_ref.to_external("abc123")  # → NodeRef("$ref:abc123")
            node_ref.to_external()  # → NodeRef("$ref:current_id")
        """
        rid = new_rid if new_rid is not None else self.ref
        return type(self).external(rid)
    
    @staticmethod
    def make_external(rid: str) -> str:
        """
        Convert bare rid to external format string.
        
        Example:
            Ref.make_external("abc123")  # → "$ref:abc123"
        """
        return f"{Ref.REF_PREFIX}{rid}"

    @classmethod
    def for_category(cls, category: ResourceCategory) -> Type["Ref"]:
        """
        Get the Ref subclass for a given ResourceCategory.
        
        Example:
            Ref.for_category(ResourceCategory.LLM)  # Returns LLMRef
            Ref.for_category(ResourceCategory.NODE)  # Returns NodeRef
        """
        mapping = cls.category_mapping()
        if category not in mapping:
            return cls  # Fallback to base Ref
        return mapping[category]

    @classmethod
    def category_mapping(cls) -> Dict[ResourceCategory, Type["Ref"]]:
        """
        Build mapping from ResourceCategory to Ref subclass.
        
        Automatically discovers all Ref subclasses via __subclasses__().
        Zero maintenance - always in sync with defined subclasses.
        """
        return {
            subclass._category: subclass
            for subclass in cls.__subclasses__()
            if hasattr(subclass, '_category')
        }

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




class SandboxRef(Ref):
    """Reference to a Sandbox resource (execution environment for agents)."""
    _category: ClassVar[ResourceCategory] = ResourceCategory.SANDBOX

    model_config = {
        "json_schema_extra": {
            "category": ResourceCategory.SANDBOX.value,
            "description": "Reference to a Sandbox execution environment",
            "examples": ["$ref:openshell-sandbox-1", "my-sandbox"]
        }
    }
