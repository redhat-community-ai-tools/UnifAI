from enum import Enum


class ResourceCategory(str, Enum):
    """Categories of resources in blueprints."""
    LLM = "llms"
    TOOL = "tools"
    RETRIEVER = "retrievers"
    CONDITION = "conditions"
    PROVIDER = "providers"
    NODE = "nodes"
    AUTH = "auths"
    SANDBOX = "sandboxes"

    @classmethod
    def plan_categories(cls) -> frozenset:
        """Categories that appear in the final blueprint (plan-referenced)."""
        return frozenset({cls.NODE, cls.CONDITION})

    @classmethod
    def hidden_categories(cls) -> frozenset:
        """Categories hidden from the UI catalog."""
        return frozenset({cls.AUTH})

    def is_plan_category(self) -> bool:
        """Check if this category is plan-referenced."""
        return self in self.plan_categories()

    def is_hidden(self) -> bool:
        """Check if this category is hidden from the UI."""
        return self in self.hidden_categories()


class SchemeType(str, Enum):
    """Authentication scheme discriminators."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"


class ProtocolType(str, Enum):
    """Auth protocol discriminators returned by detection."""
    OAUTH2 = "oauth2"
    SAML = "saml"


class ChallengeType(str, Enum):
    """AuthChallenge discriminators sent to the UI."""
    CONSENT = "consent"
    COLLECT = "collect"
    DEVICE = "device"


class SystemNodeType(str, Enum):
    """Node types that stay inline in blueprints (never saved as resources)."""
    USER_QUESTION = "user_question_node"
    FINAL_ANSWER = "final_answer_node"
    
    @classmethod
    def values(cls) -> frozenset:
        """All system node type values as strings."""
        return frozenset(e.value for e in cls)