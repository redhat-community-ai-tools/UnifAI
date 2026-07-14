from enum import Enum


class ResourceCategory(str, Enum):
    """Categories of resources in blueprints."""
    LLM = "llms"
    TOOL = "tools"
    RETRIEVER = "retrievers"
    CONDITION = "conditions"
    PROVIDER = "providers"
    NODE = "nodes"
    
    @classmethod
    def plan_categories(cls) -> frozenset:
        """Categories that appear in the final blueprint (plan-referenced)."""
        return frozenset({cls.NODE, cls.CONDITION})

    def is_plan_category(self) -> bool:
        """Check if this category is plan-referenced."""
        return self in self.plan_categories()

    @classmethod
    def builtin_disabled_categories(cls) -> frozenset:
        """Categories that cannot be created as built-in resources."""
        return frozenset({cls.RETRIEVER})


class ResourceOwnership(str, Enum):
    """Ownership classification for resources."""
    BUILTIN = "builtin"
    CUSTOM = "custom"


class ResourceVisibility(str, Enum):
    """Visibility state for built-in resources."""
    DRAFT = "draft"
    PUBLIC = "public"


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


class AuthStatus(str, Enum):
    """Action-level auth status returned to the UI."""
    AUTHENTICATED = "authenticated"
    CHALLENGE = "challenge"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


class AuthErrorCode(str, Enum):
    """Machine-readable error codes for auth action failures."""
    MISSING_USER_ID = "missing_user_id"
    MISSING_SERVER_ID = "missing_server_identifier"
    MISSING_SCHEME_TYPE = "missing_scheme_type"
    AUTH_SERVICE_UNAVAILABLE = "auth_service_unavailable"
    INITIATION_FAILED = "initiation_failed"
    STRATEGY_NOT_FOUND = "strategy_not_found"
    UNKNOWN = "unknown_error"


class SystemNodeType(str, Enum):
    """Node types that stay inline in blueprints (never saved as resources)."""
    USER_QUESTION = "user_question_node"
    FINAL_ANSWER = "final_answer_node"
    
    @classmethod
    def values(cls) -> frozenset:
        """All system node type values as strings."""
        return frozenset(e.value for e in cls)